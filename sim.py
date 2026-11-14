"""Try skills on a simulated SO-101 in MuJoCo, with no arm attached.

    python keypad/geometry_dash/fetch_so101_model.py     # once: downloads the arm model
    mjpython sim.py --view                               # live window; type requests one after another
    python sim.py "pick up the purple brick"             # no window: camera -> finder -> fetch, saves a video
    python sim.py --at 0.5 0.5                           # fetch at a grid position, no AI calls
    python sim.py --skill wave                           # any skill in skills/

The live window needs mjpython on macOS (it is installed next to python in .venv/bin). On Windows
and Linux, plain python works with --view.

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
FAR, NEAR, LEFT, RIGHT = 0.235, 0.125, 0.145, -0.145  # the far right corner is out of reach beyond this
GRASP_Z, CLEAR_Z = 0.010, 0.050  # gripper tip height when closing on a brick, and when carrying
GRID_N = 9           # taught points per side. On the first, smaller grid: 3 was 7 mm off between points and
                     # grasps failed, 5 was under 2 mm. This grid is wider, so it uses 7.
GRIP_OFFSET = 0.004  # the model's reference point is one jaw's tip; the brick sits this far toward the other.
                     # Measured here: a 32 mm brick is carried at 0 to 8 mm and dropped at -10 or +16.
JAW_ACROSS = math.pi / 2   # every taught pose has the jaws closing left-right across the table
ROLL_TURNS_JAW = 1.0       # which way the roll joint turns the jaws on this model: 1 or -1
JAW_ARM_MM = -16.0         # measured on this model: the point between the jaws is 16 mm off the wrist's turning axis
HOME_DEG = [95, -95, 90, 70, 0, 20]      # folded to the side, out of the camera's view
HANDOVER_DEG = [-50, -30, 30, 50, 0, 0]  # held out to the front right

RED, BLUE, PURPLE = "0.85 0.08 0.08 1", "0.25 0.62 0.72 1", "0.75 0.62 0.86 1"
CREAM, LIME, BLACK = "0.93 0.89 0.82 1", "0.68 0.78 0.13 1", "0.06 0.06 0.06 1"
GRIP = 'friction="2 0.1 0.01" condim="6"'

# The Duplo set from photos/duplo_a.jpg: name, shape, colour, x, y, turn in degrees.
# Pieces sit about 10 cm apart: at 6 cm the open jaws knocked the neighbours on the way down.
# Long pieces lie across the arm's reach so the jaws close on their 32 mm width. The chassis and the
# car body sit beyond the taught grid: the camera sees them and fetch should refuse them.
PIECES = [
    ("red_square_left", "2x2", RED, 0.140, 0.135, 0),
    ("blue_square", "2x2", BLUE, 0.140, 0.045, 10),
    ("purple_square", "2x2", PURPLE, 0.140, -0.045, 45),
    ("red_square_right", "2x2", RED, 0.140, -0.135, 30),
    ("white_flat", "plate", CREAM, 0.220, 0.100, 90),
    ("red_triangle", "roof", RED, 0.220, 0.0, 90),
    ("green_curved", "boat", LIME, 0.220, -0.100, 90),
    ("car_chassis", "chassis", BLACK, 0.350, 0.100, 20),
    ("car_body", "carbody", BLUE, 0.360, -0.090, -15),
]
NAMES = [piece[0] for piece in PIECES]


def _studs(across: int, along: int, top: float, rgba: str) -> str:
    """Duplo studs, for looks only: 9.4 mm wide, 16 mm apart."""
    return "".join(
        f'<geom type="cylinder" size="0.0047 0.0023" pos="{(i - (along - 1) / 2) * 0.016} '
        f'{(j - (across - 1) / 2) * 0.016} {top + 0.0023}" rgba="{rgba}" contype="0" conaffinity="0" density="0"/>'
        for i in range(along) for j in range(across))


def _shape(kind: str, rgba: str) -> str:
    box = lambda sx, sy, sz, z, mass: (f'<geom type="box" size="{sx} {sy} {sz}" pos="0 0 {z}" rgba="{rgba}" '
                                       f'mass="{mass}" {GRIP}/>')
    if kind == "2x2":       # 32 x 32 x 19 mm
        return box(0.0159, 0.0159, 0.0096, 0.0096, 0.012) + _studs(2, 2, 0.0192, rgba)
    if kind == "plate":     # the flat 2x4: 64 x 32 x 10 mm
        return box(0.0319, 0.0159, 0.0048, 0.0048, 0.012) + _studs(2, 4, 0.0096, rgba)
    if kind == "roof":      # the "triangle": a 2x4 ridge roof, two slopes meeting at a ridge across its width
        return f'<geom type="mesh" mesh="roof" rgba="{rgba}" mass="0.02" {GRIP}/>'
    if kind == "boat":      # the curved 2x4: flat top with studs, underside curving up at both ends
        return f'<geom type="mesh" mesh="boat" rgba="{rgba}" mass="0.02" {GRIP}/>' + _studs(2, 4, 0.0192, rgba)
    if kind == "chassis":   # a flat base on four wheels
        wheels = "".join(
            f'<geom type="cylinder" size="0.012 0.005" pos="{x} {y} 0.012" euler="{math.pi / 2} 0 0" rgba="{BLACK}" mass="0.004" {GRIP}/>'
            f'<geom type="cylinder" size="0.007 0.0055" pos="{x} {y} 0.012" euler="{math.pi / 2} 0 0" rgba="{CREAM}" '
            f'contype="0" conaffinity="0" density="0"/>'
            for x in (-0.022, 0.022) for y in (-0.021, 0.021))
        return box(0.032, 0.0159, 0.004, 0.014, 0.02) + _studs(2, 4, 0.018, rgba) + wheels
    if kind == "carbody":   # an open-top car shell: hollow, wheel arches on both sides, studs and a hitch at the back
        # What you see is the sculpted mesh (sim_assets/make_car_body.py). What the physics touches is a
        # few invisible boxes in the same places, because MuJoCo would otherwise fill the hollow shell in.
        part = lambda sx, sy, sz, x, y, z: (f'<geom type="box" size="{sx} {sy} {sz}" pos="{x} {y} {z}" '
                                            f'rgba="0 0 0 0" mass="0.002" {GRIP}/>')
        shell = part(0.014, 0.026, 0.009, 0.036, 0, 0.018) + part(0.010, 0.017, 0.011, -0.039, 0, 0.026)
        for side in (-1, 1):
            shell += part(0.036, 0.004, 0.005, 0.0, side * 0.023, 0.024)
            for x in (-0.046, 0.0, 0.046):
                shell += part(0.005, 0.004, 0.0115, x, side * 0.025, 0.0115)
        return shell + f'<geom type="mesh" mesh="car_body" rgba="{rgba}" contype="0" conaffinity="0" density="0"/>'
    raise ValueError(kind)


def _hull(points) -> str:
    return " ".join(f"{v:.4f}" for point in points for v in point)


def scene_xml() -> str:
    # side profiles (along the length, height), swept across the 32 mm width
    roof = [(x, y, z) for y in (-0.0159, 0.0159)
            for x, z in ((-0.0319, 0), (-0.0319, 0.006), (0, 0.0384), (0.0319, 0.006), (0.0319, 0))]
    curve = [(0.014 + 0.018 * math.sin(a), 0.018 - 0.018 * math.cos(a)) for a in [math.pi / 2 * k / 6 for k in range(7)]]
    profile = [(-0.0319, 0.0192), (0.0319, 0.0192)] + curve + [(-x, z) for x, z in curve]
    boat = [(x, y, z) for y in (-0.0159, 0.0159) for x, z in profile]
    # the arm model sets angles to radians for the whole file, so turns are converted here
    pieces = "".join(f'<body name="{name}" pos="{x} {y} 0.0005" euler="0 0 {math.radians(turn)}"><freejoint/>'
                     f'{_shape(kind, rgba)}</body>'
                     for name, kind, rgba, x, y, turn in PIECES)
    cam = TOP_CAMERA
    return f"""<mujoco>
  <include file="{MODEL / 'so101.xml'}"/>
  <compiler meshdir="{MODEL / 'assets'}"/>
  <option timestep="0.002" cone="elliptic" impratio="10"/>  <!-- at the model's 5 ms a held brick popped out of the jaws -->
  <visual>
    <global offwidth="{WIDTH}" offheight="{HEIGHT}"/>
    <headlight ambient="0.35 0.35 0.35" diffuse="0.35 0.35 0.35" specular="0 0 0"/>
  </visual>
  <asset>
    <mesh name="roof" vertex="{_hull(roof)}"/>
    <mesh name="boat" vertex="{_hull(boat)}"/>
    <mesh name="car_body" file="{HERE / 'sim_assets' / 'car_body.stl'}" smoothnormal="true"/>
  </asset>
  <worldbody>
    <light pos="0.2 0 1" dir="0 0 -1" directional="true" diffuse="0.3 0.3 0.3" specular="0 0 0"/>
    <geom name="table" type="plane" size="0.7 0.7 0.01" rgba="0.72 0.72 0.7 1" friction="1 0.02 0.001"/>
    <camera name="top" pos="{cam['pos'][0]} {cam['pos'][1]} {cam['pos'][2]}" xyaxes="0 -1 0 1 0 0" fovy="{cam['fovy']}"/>
    <camera name="side" pos="0.74 -0.60 0.44" xyaxes="0.63 0.78 0 -0.34 0.28 0.9" fovy="44"/>
    {pieces}
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
        self.renderer = None if view else mujoco.Renderer(self.model, HEIGHT // 2, WIDTH // 2)
        self.frames = []
        self.window = None
        home = to_radians(HOME_DEG)
        self.data.qpos[:6] = home
        self.data.ctrl[:6] = home
        mujoco.mj_forward(self.model, self.data)
        if view:
            from mujoco import viewer

            self.window = viewer.launch_passive(self.model, self.data)
            self.window.cam.lookat[:] = [0.24, 0.0, 0.02]  # start close on the pieces
            self.window.cam.distance, self.window.cam.azimuth, self.window.cam.elevation = 0.55, 150, -28
            print("Window controls: scroll (two fingers on a trackpad) zooms, left-drag turns the view, "
                  "right-drag slides it, double-click a piece to centre on it.", flush=True)
        self.settle(0.3)

    def _read(self) -> list[float]:
        return to_team_units(self.data.qpos[:6])

    def _write(self, joints: list[float]) -> None:
        low, high = self.model.actuator_ctrlrange[:6].T
        self.data.ctrl[:6] = np.clip(to_radians(joints), low, high)
        mujoco.mj_step(self.model, self.data, self.steps)
        if self.window:  # live window, at real speed; no video
            import time

            self.window.sync()
            time.sleep(1 / HZ)
        else:
            self.renderer.update_scene(self.data, camera="side")
            self.frames.append(cv2.cvtColor(self.renderer.render(), cv2.COLOR_RGB2BGR))

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


def _jaw_angle(data, site) -> float:
    """Which way the jaws close, as an angle on the table (radians, 0 = away from the arm)."""
    across = data.site_xmat[site].reshape(3, 3)[:, 2]
    return math.atan2(across[1], across[0])


def _half_turn(angle: float) -> float:
    """Jaws closing one way or the opposite way are the same grasp: fold into -90..90 degrees."""
    return (angle + math.pi / 2) % math.pi - math.pi / 2


def solve(model, x: float, y: float, z: float, seed=None, jaw: float | None = JAW_ACROSS) -> list[float]:
    """Inverse kinematics: joint angles (team units, gripper left at 0) that put the gripper tip
    at x, y, z pointing straight down, with the jaws closing along the table angle `jaw`."""
    data = mujoco.MjData(model)
    data.qpos[:5] = seed if seed is not None else [math.atan2(y, x), -0.3, 0.6, 1.2, 0.0]
    site = model.site("gripperframe").id
    low, high = model.jnt_range[:5].T
    jac_pos, jac_rot = np.zeros((3, model.nv)), np.zeros((3, model.nv))
    for _ in range(600):
        mujoco.mj_forward(model, data)
        approach = data.site_xmat[site].reshape(3, 3)[:, 0]  # the fingers point along the site's x axis
        error = np.concatenate([np.array([x, y, z]) - data.site_xpos[site],
                                0.3 * np.cross(approach, [0, 0, -1])])
        # a full turn, not a half: the jaws must face the same way at every taught point, or the
        # wrist-turn correction in skills/fetch.py would flip sign across the table
        twist = (jaw - _jaw_angle(data, site) + math.pi) % (2 * math.pi) - math.pi if jaw is not None else 0.0
        if np.linalg.norm(error) < 1e-4 and abs(twist) < 2e-3:
            break
        mujoco.mj_jacSite(model, data, jac_pos, jac_rot, site)
        jac = np.vstack([jac_pos[:, :5], 0.3 * jac_rot[:, :5]])
        step = jac.T @ np.linalg.solve(jac @ jac.T + 1e-4 * np.eye(6), error)
        step[4] += ROLL_TURNS_JAW * twist  # pointing down, the wrist roll joint is what turns the jaws
        data.qpos[:5] = np.clip(data.qpos[:5] + 0.5 * step, low, high)
    mujoco.mj_forward(model, data)
    miss = np.linalg.norm(np.array([x, y, z]) - data.site_xpos[site])
    if miss > 0.004:
        raise ValueError(f"the arm cannot reach x={x:.2f} y={y:.2f} z={z:.2f} pointing down (off by {miss * 1000:.0f} mm)")
    return to_team_units(list(data.qpos[:5]) + [math.radians(-10)])


def solve_grasp(model, x: float, y: float, z: float, jaw: float | None = JAW_ACROSS) -> list[float]:
    """solve(), shifted so the point between the jaws, not the jaw tip, ends up over x, y."""
    joints = solve(model, x, y, z, jaw=jaw)
    data = mujoco.MjData(model)
    for _ in range(3):  # the shift depends on which way the wrist ends up facing
        data.qpos[:6] = to_radians(joints)
        mujoco.mj_forward(model, data)
        across = data.site("gripperframe").xmat.reshape(3, 3)[:, 2]  # the direction the jaws close along
        joints = solve(model, x - GRIP_OFFSET * across[0], y - GRIP_OFFSET * across[1], z,
                       seed=to_radians(joints)[:5], jaw=jaw)
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


def request(arm, args: list[str]) -> None:
    """Run one request on the simulated arm and report what happened to the pieces."""
    before = {name: arm.height_of(name) for name in NAMES}
    start = {name: arm.data.body(name).xpos[:2].copy() for name in NAMES}
    if args[:1] == ["--skill"]:
        skill, params = importlib.import_module(f"skills.{args[1]}"), json.loads(args[2]) if len(args) > 2 else {}
    else:
        skill = importlib.import_module("skills.fetch")
        if args[:1] == ["--at"]:
            params = {"u": float(args[1]), "v": float(args[2]), "turn": float(args[3]) if len(args) > 3 else 0.0}
        else:
            import pick
            import see

            see.load_env()
            pick.CORNERS = SIM_POSES / "table_corners.json"
            pick.GRID_ASPECT = (LEFT - RIGHT) / (FAR - NEAR)
            targets, said, near = pick.locate(arm.top_view(), command=" ".join(args))
            print(f'asked "{said}": {len(targets)} match', [(label, round(u, 2), round(v, 2), f"turn {turn:.0f}") for u, v, label, turn in targets])
            if len(targets) != 1:
                print("Not moving: the finder needs exactly one match.")
                return
            if pick.place_problem(near):
                print(f"Not moving: {pick.place_problem(near)}")
                return
            params = {"u": targets[0][0], "v": targets[0][1], "turn": targets[0][3]}
            if near:
                params["to_u"], params["to_v"] = pick.drop_spot(targets[0], near[0])
                print(f"  putting it beside: {near[0][2]}, at u={params['to_u']:.2f} v={params['to_v']:.2f}")
    cv2.imwrite(str(OUT / "sim_top.jpg"), arm.top_view())

    lifted = dict(before)
    carried = set()
    write = arm._write

    def watch(joints):  # track how high each piece gets, and which ones reach handover height in the jaws
        write(joints)
        tip = arm.data.site("gripperframe").xpos
        for name in lifted:
            lifted[name] = max(lifted[name], arm.height_of(name))
            if tip[2] > 0.09 and np.linalg.norm(arm.data.body(name).xpos - tip) < 0.035:
                carried.add(name)

    arm._write, arm.frames = watch, []
    try:
        result = skill.run(arm, params, arm.halt)
        arm.settle(0.5)
    finally:
        arm._write = write
    print(skill.NAME, params, result)
    for name in lifted:
        if lifted[name] - before[name] > 0.03:
            print(f"  {name} was lifted {100 * (lifted[name] - before[name]):.0f} cm")
    if skill.NAME == "fetch" and "to_u" in params:
        for name in NAMES:
            moved = np.linalg.norm(arm.data.body(name).xpos[:2] - start[name])
            if moved > 0.02:
                gap = np.linalg.norm(arm.data.body(name).xpos[:2] - arm.data.body("car_body").xpos[:2])
                print(f"  {name} moved {100 * moved:.0f} cm and now sits {100 * gap:.0f} cm from the car body")
    elif skill.NAME == "fetch":
        print(f"  carried to the handover in the jaws: {', '.join(sorted(carried)) or 'nothing'}")
    if arm.frames:
        arm.save_video(OUT / "sim.mp4")
        print(f"video: {OUT / 'sim.mp4'}")


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
    fetch = importlib.import_module("skills.fetch")  # tell fetch this table's size and this gripper's geometry
    fetch.GRID_WIDTH_MM, fetch.GRID_DEPTH_MM = 1000 * (LEFT - RIGHT), 1000 * (FAR - NEAR)
    fetch.JAW_ARM_MM = JAW_ARM_MM
    if args:
        request(arm, args)
    while view and arm.window.is_running():  # live window: keep taking requests until it is closed
        try:
            line = input('Request, e.g. "pick up the purple brick" (Enter to quit): ').strip()
        except EOFError:  # started without a terminal: leave the window up until it is closed
            import time

            print("No terminal to type in. Close the window to finish.", flush=True)
            while arm.window.is_running():
                time.sleep(0.2)
            break
        if not line:
            break
        try:
            request(arm, line.split())
        except Exception as err:  # a failed AI call or a bad request must not close the window
            print(f"That request failed: {type(err).__name__}: {str(err)[:200]}")


if __name__ == "__main__":
    assert to_pixel(*TOP_CAMERA["pos"][:2]) == [WIDTH / 2, HEIGHT / 2]            # under the camera is the image centre
    assert to_pixel(FAR, 0)[1] < to_pixel(NEAR, 0)[1] and to_pixel(0.2, LEFT)[0] < to_pixel(0.2, RIGHT)[0]
    assert all(abs(a - b) < 1e-9 for a, b in zip(to_team_units(to_radians([10, -20, 30, 40, 50, 60])), [10, -20, 30, 40, 50, 60]))
    main()
