"""Try skills on a simulated SO-101 in MuJoCo, with no arm attached.

    python keypad/geometry_dash/fetch_so101_model.py     # once: downloads the arm model
    python sim.py "pick up the red brick"                # camera -> finder -> fetch, end to end
    python sim.py --at 0.5 0.5                           # fetch at a grid position, no AI calls
    python sim.py --skill wave                           # any skill in skills/
    mjpython sim.py --view "pick up the red brick"       # live window (macOS needs mjpython)

Writes outputs/sim.mp4 (side view) and outputs/sim_top.jpg (what the camera saw).

What this is good for: the logic, the order of moves, reach, and whether a grasp holds.
What it is not: proof for the real arm. Its poses are made here by inverse kinematics, not
taught by hand, and the real arm's calibration zero differs from the model's (Daniel's taught
home has the elbow at 127 degrees; the model stops at 97).
"""
import importlib
import json
import math
import sys
import threading
from pathlib import Path

import cv2
import mujoco
import numpy as np

import core.arm
from core.arm import HZ, JOINTS, MockArm

HERE = Path(__file__).parent
MODEL = HERE / "keypad" / "geometry_dash" / "robotstudio_so101"
OUT = HERE / "outputs"
SIM_POSES = OUT / "sim_poses"
WIDTH, HEIGHT = 1280, 960
TOP_CAMERA = {"pos": (0.25, 0.0, 0.50), "fovy": 45.0}  # looks straight down; image up is away from the arm

# the taught grid, in metres on the table: x is away from the arm, y is to its left
# Pointing straight down, this model reaches about 12 to 30 cm from its base and lifts about 5 cm.
FAR, NEAR, LEFT, RIGHT = 0.27, 0.15, 0.09, -0.09
GRASP_Z, CLEAR_Z = 0.012, 0.055  # gripper tip height when closing on a brick, and when carrying
GRID_N = 5           # taught points per side. With 3, blending was 7 mm off between points and grasps failed.
GRIP_OFFSET = 0.004  # the model's reference point is one jaw's tip; the brick sits this far toward the other.
                     # Measured here: a 32 mm brick is carried at 0 to 8 mm and dropped at -10 or +16.
HOME_DEG = [95, -95, 90, 70, 0, 20]      # folded to the side, out of the camera's view
HANDOVER_DEG = [-50, -30, 30, 50, 0, 0]  # held out to the front right

# name, colour, half sizes in metres (Duplo 2x2 is 32 x 32 x 24 mm), x, y, turn in degrees
BRICKS = [
    ("red_square", "0.85 0.1 0.1 1", (0.016, 0.016, 0.012), 0.20, 0.05, 0),
    ("blue_square", "0.2 0.6 0.75 1", (0.016, 0.016, 0.012), 0.25, -0.04, 25),
    ("green_long", "0.6 0.75 0.1 1", (0.032, 0.016, 0.012), 0.18, -0.06, 90),
    ("purple_square", "0.7 0.55 0.85 1", (0.016, 0.016, 0.012), 0.25, 0.06, 40),
]


def scene_xml() -> str:
    bricks = "".join(
        f'<body name="{name}" pos="{x} {y} {half[2]}" euler="0 0 {turn}"><freejoint/>'
        f'<geom type="box" size="{half[0]} {half[1]} {half[2]}" rgba="{rgba}" mass="0.012" '
        f'friction="2 0.1 0.01" condim="6"/></body>'
        for name, rgba, half, x, y, turn in BRICKS)
    cam = TOP_CAMERA
    return f"""<mujoco>
  <include file="{MODEL / 'so101.xml'}"/>
  <compiler meshdir="{MODEL / 'assets'}"/>
  <option timestep="0.002" cone="elliptic" impratio="10"/>  <!-- at the model's 5 ms a held brick popped out of the jaws -->
  <visual>
    <global offwidth="{WIDTH}" offheight="{HEIGHT}"/>
    <headlight ambient="0.35 0.35 0.35" diffuse="0.35 0.35 0.35" specular="0 0 0"/>
  </visual>
  <worldbody>
    <light pos="0.2 0 1" dir="0 0 -1" directional="true" diffuse="0.3 0.3 0.3" specular="0 0 0"/>
    <geom name="table" type="plane" size="0.7 0.7 0.01" rgba="0.72 0.72 0.7 1" friction="1 0.02 0.001"/>
    <camera name="top" pos="{cam['pos'][0]} {cam['pos'][1]} {cam['pos'][2]}" xyaxes="0 -1 0 1 0 0" fovy="{cam['fovy']}"/>
    <camera name="side" pos="0.72 -0.62 0.42" xyaxes="0.65 0.76 0 -0.33 0.28 0.9" fovy="42"/>
    {bricks}
  </worldbody>
</mujoco>"""


def to_pixel(x: float, y: float, z: float = 0.0) -> list[float]:
    """Where a point on the table appears in the top camera's image."""
    cx, cy, cz = TOP_CAMERA["pos"]
    focal = (HEIGHT / 2) / math.tan(math.radians(TOP_CAMERA["fovy"]) / 2)
    depth = cz - z
    return [WIDTH / 2 + focal * -(y - cy) / depth, HEIGHT / 2 - focal * (x - cx) / depth]


def to_radians(joints: list[float]) -> list[float]:
    """Team units (degrees, gripper 0 to 100) -> the model's radians."""
    return [math.radians(v) for v in joints[:5]] + [math.radians(-10 + 1.1 * joints[5])]


def to_team_units(q) -> list[float]:
    return [math.degrees(v) for v in q[:5]] + [(math.degrees(q[5]) + 10) / 1.1]


class _NoWait(threading.Event):
    """Skills pause with stop.wait(); simulated time passes in _write instead."""

    def wait(self, timeout=None):
        return self.is_set()


class SimArm(MockArm):
    """The same methods as the real arm, moving a MuJoCo model."""

    def __init__(self, view: bool = False):
        super().__init__()
        self.halt = _NoWait()
        self.model = mujoco.MjModel.from_xml_string(scene_xml())
        self.data = mujoco.MjData(self.model)
        self.steps = max(1, round(1 / HZ / self.model.opt.timestep))
        self.renderer = mujoco.Renderer(self.model, HEIGHT // 2, WIDTH // 2)
        self.frames = []
        self.window = None
        home = to_radians(HOME_DEG)
        self.data.qpos[:6] = home
        self.data.ctrl[:6] = home
        mujoco.mj_forward(self.model, self.data)
        if view:
            from mujoco import viewer

            self.window = viewer.launch_passive(self.model, self.data)
        self.settle(0.3)

    def _read(self) -> list[float]:
        return to_team_units(self.data.qpos[:6])

    def _write(self, joints: list[float]) -> None:
        low, high = self.model.actuator_ctrlrange[:6].T
        self.data.ctrl[:6] = np.clip(to_radians(joints), low, high)
        mujoco.mj_step(self.model, self.data, self.steps)
        self.renderer.update_scene(self.data, camera="side")
        self.frames.append(cv2.cvtColor(self.renderer.render(), cv2.COLOR_RGB2BGR))
        if self.window:
            import time

            self.window.sync()
            time.sleep(1 / HZ)

    def settle(self, seconds: float) -> None:
        for _ in range(int(seconds * HZ)):
            self._write(to_team_units(self.data.ctrl[:6]))

    def top_view(self):
        big = mujoco.Renderer(self.model, HEIGHT, WIDTH)
        big.update_scene(self.data, camera="top")
        return cv2.cvtColor(big.render(), cv2.COLOR_RGB2BGR)

    def height_of(self, brick: str) -> float:
        return float(self.data.body(brick).xpos[2])

    def save_video(self, path: Path) -> None:
        h, w = self.frames[0].shape[:2]
        out = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"mp4v"), HZ, (w, h))
        for frame in self.frames:
            out.write(frame)
        out.release()


def solve(model, x: float, y: float, z: float, seed=None) -> list[float]:
    """Inverse kinematics: joint angles (team units, gripper left at 0) that put the gripper tip
    at x, y, z pointing straight down."""
    data = mujoco.MjData(model)
    data.qpos[:5] = seed if seed is not None else [math.atan2(y, x), -0.3, 0.6, 1.2, 0.0]
    site = model.site("gripperframe").id
    low, high = model.jnt_range[:5].T
    jac_pos, jac_rot = np.zeros((3, model.nv)), np.zeros((3, model.nv))
    for _ in range(400):
        mujoco.mj_forward(model, data)
        approach = data.site_xmat[site].reshape(3, 3)[:, 0]  # the fingers point along the site's x axis
        error = np.concatenate([np.array([x, y, z]) - data.site_xpos[site],
                                0.3 * np.cross(approach, [0, 0, -1])])
        if np.linalg.norm(error) < 1e-4:
            break
        mujoco.mj_jacSite(model, data, jac_pos, jac_rot, site)
        jac = np.vstack([jac_pos[:, :5], 0.3 * jac_rot[:, :5]])
        step = jac.T @ np.linalg.solve(jac @ jac.T + 1e-4 * np.eye(6), error)
        data.qpos[:5] = np.clip(data.qpos[:5] + 0.5 * step, low, high)
    mujoco.mj_forward(model, data)
    miss = np.linalg.norm(np.array([x, y, z]) - data.site_xpos[site])
    if miss > 0.004:
        raise ValueError(f"the arm cannot reach x={x:.2f} y={y:.2f} z={z:.2f} pointing down (off by {miss * 1000:.0f} mm)")
    return to_team_units(list(data.qpos[:5]) + [math.radians(-10)])


def solve_grasp(model, x: float, y: float, z: float) -> list[float]:
    """solve(), shifted so the point between the jaws, not the jaw tip, ends up over x, y."""
    joints = solve(model, x, y, z)
    data = mujoco.MjData(model)
    for _ in range(3):  # the shift depends on which way the wrist ends up facing
        data.qpos[:6] = to_radians(joints)
        mujoco.mj_forward(model, data)
        across = data.site("gripperframe").xmat.reshape(3, 3)[:, 2]  # the direction the jaws close along
        joints = solve(model, x - GRIP_OFFSET * across[0], y - GRIP_OFFSET * across[1], z, seed=to_radians(joints)[:5])
    return joints


def write_poses(model) -> None:
    """Stand-ins for the poses a person teaches on the real arm, written to outputs/sim_poses."""
    SIM_POSES.mkdir(parents=True, exist_ok=True)
    as_pose = lambda joints: {f"{j}.pos": v for j, v in zip(JOINTS, joints)}
    grid = {"n": GRID_N, "down": [], "up": []}
    for x in np.linspace(FAR, NEAR, GRID_N):         # row 0 is the far edge
        for y in np.linspace(LEFT, RIGHT, GRID_N):   # column 0 is the left
            grid["down"].append(as_pose(solve_grasp(model, x, y, GRASP_Z)))
            grid["up"].append(as_pose(solve_grasp(model, x, y, CLEAR_Z)))
    (SIM_POSES / "table.json").write_text(json.dumps(grid))
    (SIM_POSES / "home.json").write_text(json.dumps(as_pose(HOME_DEG)))
    (SIM_POSES / "handover.json").write_text(json.dumps(as_pose(HANDOVER_DEG)))
    corners = [to_pixel(FAR, LEFT), to_pixel(FAR, RIGHT), to_pixel(NEAR, RIGHT), to_pixel(NEAR, LEFT)]
    (SIM_POSES / "table_corners.json").write_text(json.dumps(corners))


def main() -> None:
    args = sys.argv[1:]
    view = "--view" in args
    args = [a for a in args if a != "--view"]
    if not (MODEL / "so101.xml").exists():
        sys.exit("No arm model. Run: python keypad/geometry_dash/fetch_so101_model.py")
    OUT.mkdir(exist_ok=True)
    arm = SimArm(view)
    write_poses(arm.model)
    core.arm.POSES = SIM_POSES  # skills load poses from here, never from the real poses/ folder
    before = {name: arm.height_of(name) for name, *_ in BRICKS}

    if args[:1] == ["--skill"]:
        skill, params = importlib.import_module(f"skills.{args[1]}"), json.loads(args[2]) if len(args) > 2 else {}
    else:
        skill = importlib.import_module("skills.fetch")
        if args[:1] == ["--at"]:
            params = {"u": float(args[1]), "v": float(args[2])}
        else:
            import pick
            import see

            see.load_env()
            pick.CORNERS = SIM_POSES / "table_corners.json"
            targets, said = pick.locate(arm.top_view(), command=" ".join(args))
            print(f'asked "{said}": {len(targets)} match', [(label, round(u, 2), round(v, 2)) for u, v, label in targets])
            if len(targets) != 1:
                sys.exit("Not moving: the finder needs exactly one match.")
            params = {"u": targets[0][0], "v": targets[0][1]}
    cv2.imwrite(str(OUT / "sim_top.jpg"), arm.top_view())

    lifted = dict(before)
    carried = set()
    write = arm._write

    def watch(joints):  # track how high each brick gets, and which ones reach handover height in the jaws
        write(joints)
        tip = arm.data.site("gripperframe").xpos
        for name in lifted:
            lifted[name] = max(lifted[name], arm.height_of(name))
            if tip[2] > 0.09 and np.linalg.norm(arm.data.body(name).xpos - tip) < 0.03:
                carried.add(name)

    arm._write = watch
    result = skill.run(arm, params, arm.halt)
    arm.settle(0.5)
    arm.save_video(OUT / "sim.mp4")
    print(skill.NAME, params, result)
    for name in lifted:
        if lifted[name] - before[name] > 0.03:
            print(f"  {name} was lifted {100 * (lifted[name] - before[name]):.0f} cm")
    print(f"  carried to the handover in the jaws: {', '.join(sorted(carried)) or 'nothing'}")
    print(f"video: {OUT / 'sim.mp4'}")


if __name__ == "__main__":
    assert to_pixel(*TOP_CAMERA["pos"][:2]) == [WIDTH / 2, HEIGHT / 2]            # under the camera is the image centre
    assert to_pixel(FAR, 0)[1] < to_pixel(NEAR, 0)[1] and to_pixel(0.2, LEFT)[0] < to_pixel(0.2, RIGHT)[0]
    assert all(abs(a - b) < 1e-9 for a, b in zip(to_team_units(to_radians([10, -20, 30, 40, 50, 60])), [10, -20, 30, 40, 50, 60]))
    main()
