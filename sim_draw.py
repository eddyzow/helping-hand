"""Drawing in the simulator: the arm holds a pen over a sheet of paper, and ink shows where the tip touched.

    python sim_draw.py cat              # no window: saves outputs/sim_drawing.png and outputs/sim_draw.mp4
    python sim_draw.py --text HI        # write a word
    mjpython sim_draw.py --view         # live window; type what to draw, one after another

It runs the real skills/draw.py. Like sim.py it stands in for the taught paper grid (worked out by
inverse kinematics) and the arm. The pencil is a body in the physics, in a spring-loaded holder on the
gripper like a pen plotter's: its point presses on the table and drags with friction. (Gripped by
the bare jaws, the model's pencil is pinched at one point and swings. Held rigidly, the pressing
depth had to be right to a fraction of a millimetre: see PRESS.)
The page is PAGE metres square and faces a person standing in front of the arm.
"""
import importlib
import json
import math
import os
import sys

import cv2
import mujoco
import numpy as np

import core.arm
import draw
import sim

PAGE = 0.12            # the drawing area: a square this many metres across
PAGE_X = 0.125         # its edge nearest the arm; the page runs from here away from the arm
PAPER_Z = 0.0003       # top of the sheet above the table
PEN = 0.040            # pencil tip below the gripper's reference point
PENCIL = 0.100         # the pencil's length
POINT = 0.0012         # radius of the pencil's point, the only part of it that touches anything
# With a rigid holder the pressing depth decided everything. Measured: at 1 mm the point trailed the gripper by
# 5 to 6 mm (strokes ended short, corners were cut); at 0.5 mm it was accurate where it touched but skipped
# 4 to 15 percent of the line; at 0.2 mm it skipped more. The spring makes the depth uncritical.
PRESS = float(os.environ.get("PRESS", "0.002"))          # the "down" poses aim this far into the table, as a taught pose would
LIFT = 0.012           # pen height above the paper between strokes
PAPER_N = int(os.environ.get("PAPER_N", "5"))            # taught points per side: what a person would teach by hand
SPRING = float(os.environ.get("SPRING", "120"))   # the holder's spring, newtons per metre: 2 mm of travel presses with about 25 grams
SPRING_TRAVEL = 0.008  # how far the pencil can slide up into the holder
RUB = float(os.environ.get("RUB", "0.4"))         # friction of the pencil's point on the paper
PEN_DRAG = 0.0         # lead for a trailing point (see draw.py). Not needed at this pressing depth; at 1 mm, 0.033 fixed it
BESIDE = float(os.environ.get("BESIDE", "-0.0155"))  # the pencil lies against the fixed jaw: this far from the gripper's reference point, across the jaws
GRIP = float(os.environ.get("GRIP", "12"))  # gripper value taught around the pencil; skills/draw.py squeezes PEN_SQUEEZE past it, onto the pencil
INK_GAP = 0.0015       # ink is laid down in segments at least this long
BLACK = [0.05, 0.05, 0.08, 1]


def page_xy(u: float, v: float) -> tuple[float, float]:
    """Page position (u right, v down the page) -> table x, y. The top of the page is nearest the arm,
    so the drawing is the right way up for someone facing the arm."""
    return PAGE_X + v * PAGE, -PAGE / 2 + u * PAGE


class DrawArm(sim.SimArm):
    def __init__(self, view: bool = False):
        sim.PIECES[:] = []
        sim.NAMES[:] = []
        x, y = page_xy(0.5, 0.5)
        sim.EXTRA = (f'<geom name="paper" type="box" size="{PAGE / 2 + 0.01} {PAGE / 2 + 0.01} {PAPER_Z / 2}" '
                     f'pos="{x} {y} {PAPER_Z / 2}" rgba="1 1 1 1" contype="0" conaffinity="0"/>'
                     f'<camera name="page" pos="{x + 0.20} {y - 0.26} 0.34" xyaxes="0.79 0.61 0 -0.42 0.55 0.72" fovy="30"/>')
        # The pencil sits in a spring-loaded holder on the gripper, like a pen plotter's: it can slide up
        # SPRING_TRAVEL against a light spring. Only its point touches anything. It is added to a copy of the arm model.
        cone = " ".join(f"{0.004 * math.cos(a):.5f} {0.004 * math.sin(a):.5f} {-PENCIL / 2 + 0.012}"
                        for a in np.linspace(0, 2 * math.pi, 12, endpoint=False)) + f" 0 0 {-PENCIL / 2}"
        pencil = (f'<body name="pencil" pos="{0.012 + BESIDE} -0.000218 {-0.098127 - PEN + PENCIL / 2}">'
                  f'<joint name="pen_spring" type="slide" axis="0 0 1" range="0 {SPRING_TRAVEL}" stiffness="{SPRING}" '
                  f'damping="0.4" armature="0.0005"/>'
                  f'<geom type="cylinder" size="0.004 {PENCIL / 2 - 0.006}" pos="0 0 0.006" rgba="0.8 0.15 0.15 1" '
                  f'mass="0.006" contype="0" conaffinity="0"/>'
                  f'<geom type="mesh" mesh="pencil_cone" rgba="0.85 0.7 0.5 1" contype="0" conaffinity="0" density="0"/>'
                  f'<geom name="pencil_tip" type="sphere" size="{POINT}" pos="0 0 {-PENCIL / 2}" rgba="0.1 0.1 0.1 1" '
                  f'mass="0.0003" friction="{RUB} 0.005 0.0001"/></body>')
        source = (sim.MODEL / "so101.xml").read_text()
        marker = "<!-- Camera mount -->"
        assert marker in source, "the arm model changed: cannot find where to mount the pencil"
        source = source.replace(marker, pencil + marker, 1).replace("<asset>", f'<asset><mesh name="pencil_cone" vertex="{cone}"/>', 1)
        sim.ARM_XML = sim.MODEL / "so101_pencil.xml"  # next to the original, so its mesh paths still work
        sim.ARM_XML.write_text(source)
        self.ink, self.last, self.shown = [], None, 0
        super().__init__(view)
        self.camera, self.frame_every = "page", 3

    def tip(self) -> np.ndarray:
        return self.data.geom("pencil_tip").xpos.copy()  # the centre of the pencil's point

    def _write(self, joints: list[float]) -> None:
        super()._write(joints)
        now = self.tip()
        x0, y0 = page_xy(0, 0)
        on_sheet = x0 - 0.01 <= now[0] <= x0 + PAGE + 0.01 and y0 - 0.01 <= now[1] <= y0 + PAGE + 0.01
        if now[2] > POINT + 0.0006 or not on_sheet:  # the point is resting on the table when its centre is one radius up
            self.last = None  # pen is off the paper
        elif self.last is None:
            self.last = now.copy()
        elif np.linalg.norm(now[:2] - self.last[:2]) >= INK_GAP:
            self.ink.append((self.last.copy(), now.copy()))
            self.last = now.copy()

    def _extras(self, scene, live: bool) -> None:
        def capsule(index, a, b, radius, rgba):
            mujoco.mjv_initGeom(scene.geoms[index], mujoco.mjtGeom.mjGEOM_CAPSULE, np.zeros(3), np.zeros(3),
                                np.zeros(9), np.array(rgba, dtype=np.float32))
            mujoco.mjv_connector(scene.geoms[index], mujoco.mjtGeom.mjGEOM_CAPSULE, radius, a, b)

        first = 0 if live else scene.ngeom           # the live window keeps its shapes; a rendered frame starts empty
        start = self.shown if live else 0
        count = scene.ngeom if live else first
        for a, b in self.ink[start:]:
            if count >= scene.maxgeom:
                break
            up = np.array([0, 0, 0.0006])
            capsule(count, np.array([a[0], a[1], PAPER_Z]) + up, np.array([b[0], b[1], PAPER_Z]) + up, 0.0007, BLACK)
            count += 1
        scene.ngeom = count
        if live:
            self.shown = len(self.ink)

    def clear(self) -> None:
        self.ink, self.last, self.shown = [], None, 0
        if self.window:
            with self.window.lock():
                self.window.user_scn.ngeom = 0


def write_paper(model) -> None:
    """Stand-in for `python arm.py teach paper`: pen on the paper, then lifted, at PAPER_N by PAPER_N points."""
    sim.SIM_POSES.mkdir(parents=True, exist_ok=True)
    as_pose = lambda joints: {f"{j}.pos": v for j, v in zip(sim.JOINTS, joints[:5] + [GRIP])}
    grid = {"n": PAPER_N, "down": [], "up": []}
    # the pencil is beside the gripper's reference point, across the jaws, so the gripper goes that much to one side
    off_x, off_y = BESIDE * math.cos(sim.JAW_ACROSS), BESIDE * math.sin(sim.JAW_ACROSS)
    for v in np.linspace(0, 1, PAPER_N):          # row 0 is the top of the page
        for u in np.linspace(0, 1, PAPER_N):      # column 0 is its left edge
            x, y = page_xy(u, v)
            grid["down"].append(as_pose(sim.solve(model, x - off_x, y - off_y, POINT - PRESS + PEN)))
            grid["up"].append(as_pose(sim.solve(model, x - off_x, y - off_y, POINT + LIFT + PEN)))
    (sim.SIM_POSES / "paper.json").write_text(json.dumps(grid))
    # Resting pose: pen held 5 cm above the middle of the page. From sim.py's folded-away home, the straight
    # joint move to the page dipped the pen through the table at the page's corner and left a mark.
    x, y = page_xy(0.5, 0.5)
    (sim.SIM_POSES / "home.json").write_text(json.dumps(as_pose(sim.solve(model, x - off_x, y - off_y, POINT + 0.05 + PEN))))


def picture(ink, strokes=None, size: int = 600):
    """The ink as a picture of the page, black on white. With `strokes`, what was asked for is drawn
    underneath in orange, to see where the pen strayed."""
    page = np.full((size, size, 3), 255, np.uint8)
    to_px = lambda u, v: (int(u * size), int(v * size))
    for stroke in strokes or []:
        cv2.polylines(page, [np.int32([to_px(u, v) for u, v in stroke])], False, (60, 160, 255), 5, cv2.LINE_AA)
    for a, b in ink:
        uv = [((p[1] + PAGE / 2) / PAGE, (p[0] - PAGE_X) / PAGE) for p in (a, b)]
        cv2.line(page, to_px(*uv[0]), to_px(*uv[1]), (20, 20, 20), 3, cv2.LINE_AA)
    return page


def strayed(ink, strokes) -> tuple[float, float, float]:
    """How the ink compares with the line asked for: (typical distance of the ink from the line in mm,
    worst distance, percent of the line with no ink within 2 mm of it)."""
    wanted = np.array([(u0 + (u1 - u0) * k / 8, v0 + (v1 - v0) * k / 8)   # the asked line, sampled every 0.3 mm or finer
                       for s in strokes for (u0, v0), (u1, v1) in zip(draw.resample(s), draw.resample(s)[1:]) for k in range(9)])
    drawn = np.array([((p[1] + PAGE / 2) / PAGE, (p[0] - PAGE_X) / PAGE) for seg in ink for p in seg])
    if not len(drawn):
        return float("inf"), float("inf"), 100.0
    apart = np.linalg.norm(drawn[:, None, :] - wanted[None, :, :], axis=2) * PAGE * 1000
    gaps = apart.min(axis=1)
    return float(np.mean(gaps)), float(np.max(gaps)), float(100 * np.mean(apart.min(axis=0) > 2.0))


def sketch(arm, strokes) -> dict:
    """Draw these strokes on a clean sheet. Saves the picture and returns the skill's result plus how
    far the ink strayed."""
    skill = importlib.import_module("skills.draw")
    skill.GRID = sim.SIM_POSES / "paper.json"
    arm.clear()
    arm.frames = []
    result = skill.run(arm, {"strokes": [[list(p) for p in s] for s in strokes]}, arm.halt)
    cv2.imwrite(str(sim.OUT / "sim_drawing.png"), picture(arm.ink))
    cv2.imwrite(str(sim.OUT / "sim_drawing_check.png"), picture(arm.ink, strokes))
    typical, worst, missing = strayed(arm.ink, strokes)
    if arm.frames:
        arm.save_video(sim.OUT / "sim_draw.mp4")
    return {**result, "typical_mm": round(typical, 1), "worst_mm": round(worst, 1), "missing_percent": round(missing, 1)}


def strokes_for(words: list[str]):
    if words[:1] == ["--text"]:
        return draw.from_text(" ".join(words[1:]))
    return draw.sketch(" ".join(words))


def main() -> None:
    args = [a for a in sys.argv[1:] if a != "--view"]
    view = "--view" in sys.argv
    sim.OUT.mkdir(exist_ok=True)
    arm = DrawArm(view)
    write_paper(arm.model)
    core.arm.POSES = sim.SIM_POSES
    if "PEN_DRAG" not in os.environ:
        draw.PEN_DRAG = PEN_DRAG
    if "PEN_SPEED" not in os.environ:
        draw.PEN_SPEED = 0.25  # the spring-loaded pencil stays within 1 mm at this speed here; draw.py's own default is slower
    while True:
        if not args:
            if not (view and arm.window.is_running()):
                break
            args = input('What should I draw, e.g. "a cat" or "--text HI" (Enter to quit)? ').split()
            if not args:
                break
        try:
            print(sketch(arm, strokes_for(args)), "-> outputs/sim_drawing.png")
        except Exception as err:  # a failed AI call must not close the window
            print(f"That failed: {type(err).__name__}: {str(err)[:200]}")
        args = []


if __name__ == "__main__":
    assert page_xy(0, 0) == (PAGE_X, -PAGE / 2) and page_xy(1, 1) == (PAGE_X + PAGE, PAGE / 2)
    line = [(np.array([PAGE_X + 0.06, 0.0015 * i, PAPER_Z]), np.array([PAGE_X + 0.06, 0.0015 * (i + 1), PAPER_Z]))
            for i in range(8)]  # 12 mm of ink in short segments, as the simulator lays it down
    assert strayed(line, [[(0.5, 0.5), (0.6, 0.5)]])[1] < 0.01          # ink exactly on the asked line
    assert strayed(line, [[(0.5, 0.5), (0.6, 0.5)]])[2] == 0 and strayed(line, [[(0.5, 0.5), (0.7, 0.5)]])[2] > 30  # half undrawn
    assert abs(strayed(line, [[(0.5, 0.6), (0.6, 0.6)]])[0] - 12) < 0.01  # a line 0.1 of the page lower is 12 mm away
    main()
