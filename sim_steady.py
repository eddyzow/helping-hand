"""Try the steady skill (skills/steady.py) on two simulated SO-101 arms in MuJoCo: a leader moved by
a shaky hand and a follower that picks up a brick. No hardware.

    python keypad/geometry_dash/fetch_so101_model.py   # once: downloads the arm model
    python sim_steady.py                               # one pick-up, 3 degree 5 Hz tremor, filter on; saves a video
    python sim_steady.py --no-filter                   # the same hand with the filter off
    python sim_steady.py --shake 4.5 --hz 6 --seed 2   # a different tremor
    python sim_steady.py --compare                     # tremor sizes x filter on/off, several tries each, and a
                                                       # side-by-side video of the same hand without and with the filter
    python sim_steady.py --view                        # live window instead of a video (mjpython on macOS)

On a machine with no screen, set MUJOCO_GL=osmesa (or egl) before running.

What happens. The "hand" is a script: hover over a 2x2 Duplo, come down, close, lift, carry 12 cm,
set it down, let go. A tremor is added on top of every joint and the trigger. The leader arm is
placed exactly where the hand puts it at every physics step, the way a real leader goes where the
hand moves it; its readings are rounded to the real encoder's 0.088 degrees. The real skill then
runs unchanged: it reads the leader, filters, and commands the follower, whose motors, jaws and
the brick are simulated with physics.

What this shows: whether the filter keeps a shaky hand from knocking, missing or dropping the brick.
What it does not show: anything about the real arms. The scripted hand does not watch the follower
and wait for it as a person would, the model's servos are stronger and more exact than the real
ones, and both arms here are the follower model (the real leader has a handle, not jaws).
"""
import argparse
import json
import math
import random
import subprocess
import time

import cv2
import mujoco
import numpy as np

import core.arm
import sim
from core.arm import HZ, JOINTS, MockArm
from skills import steady

BRICK, TARGET = (0.20, 0.04), (0.20, -0.08)   # where the brick starts and where the hand carries it, metres
LEADER_AT = (0.0, -0.46)                      # the leader's base, to the follower's right, out of its reach
READY_S = 8.0     # the hand waits this long over the brick: the skill first homes the follower and glides it there
FOLLOW_S = 23.0   # how long the skill follows; the scripted pick-up takes 15.5 s
POSES = sim.OUT / "sim_steady_poses"
ENCODER_DEG = 360 / 4096
TRIGGER_SHAKE = 2.0   # the trigger finger's tremor, in gripper units (0 to 100) per degree of tremor at the wrist
FILM = (640, 480)
FILM_FROM = 4.5   # the video skips the first seconds, where the follower only leaves home and the hand waits


def build():
    """One model: the follower at the origin with the brick, and a second arm as the leader."""
    sim.PIECES[:] = [("brick", "2x2", sim.RED, BRICK[0], BRICK[1], 0)]
    eye, look = np.array([0.80, -0.20, 0.46]), np.array([0.10, -0.21, 0.07])
    forward = (look - eye) / np.linalg.norm(look - eye)
    right = np.cross(forward, [0, 0, 1]) / np.linalg.norm(np.cross(forward, [0, 0, 1]))
    up = np.cross(right, forward)
    sim.EXTRA = (f'<geom name="target" type="cylinder" size="0.024 0.0004" pos="{TARGET[0]} {TARGET[1]} 0.0004" '
                 f'rgba="0.15 0.6 0.35 0.7" contype="0" conaffinity="0"/>'
                 f'<camera name="both" pos="{eye[0]} {eye[1]} {eye[2]}" fovy="42" '
                 f'xyaxes="{right[0]} {right[1]} {right[2]} {up[0]} {up[1]} {up[2]}"/>')
    spec = mujoco.MjSpec.from_string(sim.scene_xml())
    spec.option.timestep = 1 / HZ / 16  # a whole number of physics steps in each tick of the skill
    spec.add_texture(name="sky", type=mujoco.mjtTexture.mjTEXTURE_SKYBOX, builtin=mujoco.mjtBuiltin.mjBUILTIN_FLAT,
                     rgb1=[0.93, 0.93, 0.91], rgb2=[0.93, 0.93, 0.91], width=32, height=192)  # a plain backdrop, not black
    frame = spec.worldbody.add_frame(pos=[LEADER_AT[0], LEADER_AT[1], 0])
    spec.attach(mujoco.MjSpec.from_file(str(sim.MODEL / "so101.xml")), prefix="leader_", frame=frame)
    model = spec.compile()
    root = model.body("leader_base").id
    for geom in range(model.ngeom):
        if model.body_rootid[model.geom_bodyid[geom]] == root:
            model.geom_contype[geom] = model.geom_conaffinity[geom] = 0  # the leader touches nothing
            if model.geom_group[geom] != 3:  # tint it, so the two arms are easy to tell apart
                model.geom_matid[geom] = -1
                model.geom_rgba[geom] = [0.95, 0.60, 0.25, 1]
    return model


def hand_script(model, shake_deg: float, hz: float, seed: int):
    """joints(t) in team units: the pick-up a steady hand would make, plus the tremor."""
    hover = lambda xy: sim.solve_grasp(model, xy[0], xy[1], sim.CLEAR_Z)
    down = lambda xy, z=sim.GRASP_Z: sim.solve_grasp(model, xy[0], xy[1], z)
    grip = lambda joints, value: joints[:5] + [value]
    steps = [  # (seconds to get there, joints)
        (READY_S, grip(hover(BRICK), 100)),
        (2.0, grip(down(BRICK), 100)), (0.8, grip(down(BRICK), 100)),
        (0.8, grip(down(BRICK), 5)), (0.6, grip(down(BRICK), 5)),
        (1.5, grip(hover(BRICK), 5)), (0.5, grip(hover(BRICK), 5)),
        (2.0, grip(hover(TARGET), 5)), (0.5, grip(hover(TARGET), 5)),
        (1.5, grip(down(TARGET, sim.GRASP_Z + 0.003), 5)), (0.5, grip(down(TARGET, sim.GRASP_Z + 0.003), 5)),
        (0.8, grip(down(TARGET, sim.GRASP_Z + 0.003), 100)), (0.5, grip(down(TARGET, sim.GRASP_Z + 0.003), 100)),
        (1.5, grip(hover(TARGET), 100)), (2.0, grip(hover(TARGET), 100)),
    ]
    rng = random.Random(seed)
    phase, swell = rng.uniform(0, 2 * math.pi), rng.uniform(0, 2 * math.pi)

    def joints(t: float) -> list[float]:
        start, pose = 0.0, steps[0][1]
        for seconds, target in steps:
            if t < start + seconds:
                part = (t - start) / seconds
                ease = part * part * (3 - 2 * part)  # starts and stops gently, as a hand does
                pose = [a + (b - a) * ease for a, b in zip(pose, target)]
                break
            start, pose = start + seconds, target
        else:
            pose = list(pose)
        size = shake_deg * (0.8 + 0.2 * math.sin(2 * math.pi * 0.3 * t + swell))  # a tremor swells and fades a little
        for joint, (share, offset) in enumerate(steady.SHAKE):
            pose[joint] += size * share * math.sin(2 * math.pi * hz * t + offset + phase)
        pose[5] += TRIGGER_SHAKE * size * math.sin(2 * math.pi * hz * t + phase + 1.0)  # the trigger finger shakes too
        return pose

    return joints


_renderers = {}


def _renderer(model):
    """One renderer for the whole program: a second one alongside the first produced noise with osmesa."""
    if id(model) not in _renderers:
        _renderers[id(model)] = mujoco.Renderer(model, FILM[1], FILM[0])
    return _renderers[id(model)]


class Pair(MockArm):
    """The follower, as the arm the skill is given. Every write also moves simulated time on, and the
    leader is put where the hand is at each physics step."""

    def __init__(self, model, hand, film: int = 0, view: bool = False):
        """film: 0 for no video, 1 to film every tick, 2 every second tick, and so on."""
        super().__init__()
        self.halt = sim._NoWait()
        self.model, self.data, self.hand = model, mujoco.MjData(model), hand
        self.grip = None
        ids = lambda prefix: ([model.joint(prefix + j).qposadr[0] for j in JOINTS],
                              [model.joint(prefix + j).dofadr[0] for j in JOINTS],
                              [model.actuator(prefix + j).id for j in JOINTS])
        self.q, self.v, self.u = ids("")
        self.leader_q, self.leader_v, self.leader_u = ids("leader_")
        self.low, self.high = model.actuator_ctrlrange[self.u].T
        home = sim.to_radians(sim.HOME_DEG)
        self.data.qpos[self.q] = home
        self.data.ctrl[self.u] = home
        self.renderer, self.film_every = (_renderer(model) if film else None), film
        self.frames, self.log, self.window = [], [], None
        self._leader()
        mujoco.mj_forward(model, self.data)
        if view:
            from mujoco import viewer

            self.window = viewer.launch_passive(model, self.data)
            self.window.cam.lookat[:] = [0.12, -0.21, 0.08]
            self.window.cam.distance, self.window.cam.azimuth, self.window.cam.elevation = 0.95, 180, -25

    def _leader(self) -> None:
        q = np.clip(sim.to_radians(self.hand(self.data.time)), self.low, self.high)
        self.data.qpos[self.leader_q], self.data.qvel[self.leader_v], self.data.ctrl[self.leader_u] = q, 0, q

    def leader_reading(self) -> list[float]:
        """What the leader's encoders would report now."""
        joints = self.hand(self.data.time)
        return [round(v / ENCODER_DEG) * ENCODER_DEG for v in joints[:5]] + [round(joints[5], 1)]

    def _read(self) -> list[float]:
        joints = sim.to_team_units(self.data.qpos[self.q])
        if self.grip is not None:
            joints[5] = self.grip
        return joints

    def _write(self, joints: list[float]) -> None:
        self.grip = joints[5]
        self.data.ctrl[self.u] = np.clip(sim.to_radians(joints), self.low, self.high)
        for _ in range(16):
            self._leader()
            mujoco.mj_step(self.model, self.data)
        self._leader()
        mujoco.mj_forward(self.model, self.data)
        self.log.append((self.data.time, self.data.site("leader_gripperframe").xpos.copy(),
                         self.data.site("gripperframe").xpos.copy(), self.data.body("brick").xpos.copy()))
        if self.window:
            self.window.sync()
            time.sleep(1 / HZ)
        elif self.renderer and self.data.time >= FILM_FROM and len(self.log) % self.film_every == 0:
            self.renderer.update_scene(self.data, camera="both")
            self.frames.append(cv2.cvtColor(self.renderer.render(), cv2.COLOR_RGB2BGR))


class Leader:
    def __init__(self, pair: Pair):
        self.pair = pair

    def get_action(self) -> dict:
        return {f"{name}.pos": value for name, value in zip(JOINTS, self.pair.leader_reading())}

    def disconnect(self) -> None:
        pass


def _smooth(points: np.ndarray) -> np.ndarray:
    """A 0.4 s centred average: two whole swings of a 5 Hz tremor, so the tremor averages out."""
    half = round(0.2 * HZ)
    weights = np.ones(2 * half + 1)
    weights[[0, -1]] = 0.5
    weights /= weights.sum()
    return np.stack([np.convolve(points[:, axis], weights, mode="valid") for axis in range(3)], axis=1)


def trial(model, shake_deg: float, hz: float, use_filter: bool, seed: int, film: int = 0, view=False) -> dict:
    """One pick-up. Returns what happened to the brick and how much each gripper tip shook."""
    pair = Pair(model, hand_script(model, shake_deg, hz, seed), film, view)
    steady.clock = lambda: pair.data.time
    steady.open_leader = lambda arm: Leader(pair)
    result = steady.run(pair, {"seconds": FOLLOW_S, "filter": use_filter}, pair.halt)
    times = np.array([row[0] for row in pair.log])
    hand, tip, brick = (np.array([row[i] for row in pair.log]) for i in (1, 2, 3))
    hand = hand - [LEADER_AT[0], LEADER_AT[1], 0]  # as if the leader stood where the follower does
    work = (times >= READY_S) & (times <= READY_S + 15.5)
    half = round(0.2 * HZ)
    inner = work[half:len(times) - half]
    shake = lambda path: float(np.sqrt(np.mean(np.sum((path[half:len(path) - half] - _smooth(path))[inner] ** 2, axis=1))))
    smooth_hand, smooth_tip = _smooth(hand)[inner], _smooth(tip)[inner]
    lags = [float(np.mean(np.linalg.norm(smooth_hand[:len(smooth_hand) - d] - smooth_tip[d:], axis=1))) for d in range(31)]
    before_grip = np.searchsorted(times, READY_S + 2.8)
    rest = brick[0]
    return {
        "skill_ok": result["ok"], "report": result.get("report", result["reason"]),
        "knocked_mm": 1000 * float(np.linalg.norm(brick[before_grip][:2] - rest[:2])),
        "lifted_mm": 1000 * float(brick[:, 2].max() - rest[2]),
        "off_target_mm": 1000 * float(np.linalg.norm(brick[-1][:2] - TARGET)),
        "placed": bool(np.linalg.norm(brick[-1][:2] - TARGET) < 0.02 and brick[:, 2].max() - rest[2] > 0.02
                       and abs(brick[-1][2] - rest[2]) < 0.004),
        "hand_shake_mm": 1000 * shake(hand), "tip_shake_mm": 1000 * shake(tip),
        "lag_s": int(np.argmin(lags)) / HZ, "frames": pair.frames, "window": pair.window,
    }


def save_video(path, panels: list[tuple[str, list]], fps: float) -> None:
    """One or more runs side by side, each with its caption, as an H.264 mp4 (needs ffmpeg) or else mp4v."""
    count = min(len(frames) for _, frames in panels)
    width, height = FILM[0] * len(panels), FILM[1]
    try:
        out = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "bgr24",
                                "-s", f"{width}x{height}", "-r", str(fps), "-i", "-", "-pix_fmt", "yuv420p",
                                "-c:v", "libx264", "-crf", "23", str(path)], stdin=subprocess.PIPE)
        write, close = out.stdin.write, lambda: (out.stdin.close(), out.wait())
    except FileNotFoundError:
        out = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"mp4v"), fps, (width, height))
        write, close = lambda data: out.write(np.frombuffer(data, np.uint8).reshape(height, width, 3)), out.release
    for index in range(count):
        row = []
        for caption, frames in panels:
            frame = frames[index].copy()
            cv2.rectangle(frame, (0, 0), (FILM[0], 34), (255, 255, 255), -1)
            cv2.putText(frame, caption, (10, 24), cv2.FONT_HERSHEY_SIMPLEX, 0.62, (20, 20, 20), 2, cv2.LINE_AA)
            cv2.putText(frame, "leader: moved by the shaky hand", (12, FILM[1] - 34), cv2.FONT_HERSHEY_SIMPLEX, 0.45,
                        (20, 20, 20), 1, cv2.LINE_AA)
            cv2.putText(frame, "follower: picks up the brick", (FILM[0] - 232, FILM[1] - 34), cv2.FONT_HERSHEY_SIMPLEX,
                        0.45, (20, 20, 20), 1, cv2.LINE_AA)
            row.append(frame)
        write(np.hstack(row).tobytes())
    close()


def describe(run: dict) -> str:
    return (f"{'PLACED' if run['placed'] else 'FAILED'}: lifted {run['lifted_mm']:.0f} mm, ended {run['off_target_mm']:.0f} mm "
            f"from the target, knocked {run['knocked_mm']:.0f} mm before the grasp. Hand tip shook {run['hand_shake_mm']:.1f} mm, "
            f"follower tip {run['tip_shake_mm']:.1f} mm; the follower trailed the hand by {run['lag_s']:.2f} s.")


def main() -> None:
    parser = argparse.ArgumentParser(description="The steady skill on two simulated arms.")
    parser.add_argument("--shake", type=float, default=3.0, help="tremor size in degrees at the wrist (default 3)")
    parser.add_argument("--hz", type=float, default=5.0, help="tremor rate (default 5)")
    parser.add_argument("--seed", type=int, default=1, help="which moment of the tremor the pick-up starts at")
    parser.add_argument("--no-filter", action="store_true", help="send the hand's motion unfiltered")
    parser.add_argument("--compare", action="store_true", help="a table over tremor sizes, filter off and on")
    parser.add_argument("--tries", type=int, default=6, help="pick-ups per row of the --compare table")
    parser.add_argument("--view", action="store_true", help="live window, no video")
    parser.add_argument("--film-every", type=int, default=1, help="film every Nth tick; 2 halves the rendering time")
    args = parser.parse_args()
    if not (sim.MODEL / "so101.xml").exists():
        raise SystemExit("No arm model. Run: python keypad/geometry_dash/fetch_so101_model.py")
    sim.OUT.mkdir(exist_ok=True)
    POSES.mkdir(parents=True, exist_ok=True)
    (POSES / "home.json").write_text(json.dumps({f"{j}.pos": v for j, v in zip(JOINTS, sim.HOME_DEG)}))
    core.arm.POSES = POSES  # the skill's home is the simulated arm's, never the real poses/ folder
    model = build()

    if not args.compare:
        run = trial(model, args.shake, args.hz, not args.no_filter, args.seed, 0 if args.view else args.film_every, args.view)
        print(describe(run))
        print("The skill said:", run["report"])
        if run["frames"]:
            save_video(sim.OUT / "sim_steady.mp4", [("Tremor filter OFF" if args.no_filter else "Tremor filter ON", run["frames"])],
                       HZ / args.film_every)
            print("Video:", sim.OUT / "sim_steady.mp4")
        while run["window"] and run["window"].is_running():
            time.sleep(0.2)
        return

    rows = []
    print(f"{args.tries} pick-ups per row, each starting at a different moment of a {args.hz:g} Hz tremor.\n")
    print(f"{'tremor':>8} {'filter':>7} {'placed':>8} {'hand tip shake':>15} {'follower tip shake':>19} {'trails by':>10}")
    for shake_deg in (0.0, 1.5, 3.0, 4.5):
        for use_filter in (False, True):
            runs = [trial(model, shake_deg, args.hz, use_filter, seed) for seed in range(1, args.tries + 1)]
            mean = lambda key: sum(run[key] for run in runs) / len(runs)
            placed = sum(run["placed"] for run in runs)
            rows.append({"shake_deg": shake_deg, "filter": use_filter, "placed": placed, "tries": len(runs),
                         "hand_shake_mm": mean("hand_shake_mm"), "tip_shake_mm": mean("tip_shake_mm"), "lag_s": mean("lag_s"),
                         "runs": [{k: v for k, v in run.items() if k not in ("frames", "window")} for run in runs]})
            print(f"{shake_deg:>6.1f}°  {'on' if use_filter else 'off':>7} {placed:>5} of {len(runs)} {mean('hand_shake_mm'):>12.1f} mm "
                  f"{mean('tip_shake_mm'):>16.1f} mm {mean('lag_s'):>8.2f} s", flush=True)
    (sim.OUT / "sim_steady.json").write_text(json.dumps({"hz": args.hz, "rows": rows}, indent=1))
    off = trial(model, args.shake, args.hz, False, args.seed, args.film_every)
    on = trial(model, args.shake, args.hz, True, args.seed, args.film_every)
    save_video(sim.OUT / "sim_steady.mp4", [(f"No filter: {args.shake:g} deg tremor", off["frames"]),
                                           ("Tremor filter on: same hand", on["frames"])], HZ / args.film_every)
    print(f"\nFilmed, {args.shake:g}° tremor, the same hand twice:\n  filter off: {describe(off)}\n  filter on:  {describe(on)}")
    print("Table:", sim.OUT / "sim_steady.json", " Video:", sim.OUT / "sim_steady.mp4")


if __name__ == "__main__":
    main()
