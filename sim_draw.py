"""Drawing in the simulator: the arm holds a pen over a sheet of paper, and ink shows where the tip touched.

    python sim_draw.py cat              # no window: saves outputs/sim_drawing.png and outputs/sim_draw.mp4
    python sim_draw.py --text HI        # write a word
    mjpython sim_draw.py --view         # live window; type what to draw, one after another

It runs the real skills/draw.py. Like sim.py it stands in for three things: the taught paper grid
(worked out by inverse kinematics), the arm, and the pen (the tip is a point 4 cm below the jaws;
it is not gripped, so a pen slipping in the real jaws does not show up here).
The page is PAGE metres square and faces a person standing in front of the arm.
"""
import importlib
import json
import math
import sys

import cv2
import mujoco
import numpy as np

import core.arm
import draw
import sim

PAGE = 0.12            # the drawing area: a square this many metres across
PAGE_X = 0.125         # its edge nearest the arm; the page runs from here away from the arm
PAPER_Z = 0.001        # top of the sheet above the table
PEN = 0.040            # pen tip below the gripper's reference point
PRESS = 0.001          # the "down" poses aim this far into the paper, as a taught pose would
LIFT = 0.012           # pen height above the paper between strokes
PAPER_N = 5            # taught points per side: what a person would teach by hand
INK_GAP = 0.0015       # ink is laid down in segments at least this long
BLACK, PENCIL = [0.05, 0.05, 0.08, 1], [0.95, 0.75, 0.1, 1]


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
                     f'<camera name="page" pos="{x + 0.30} {y - 0.02} 0.34" xyaxes="0 1 0 -0.72 0 0.69" fovy="27"/>')
        self.ink, self.last, self.shown = [], None, 0
        super().__init__(view)
        self.camera, self.frame_every = "page", 3

    def tip(self) -> np.ndarray:
        site = self.data.site("gripperframe")
        return site.xpos + PEN * site.xmat.reshape(3, 3)[:, 0]  # the fingers point along the site's x axis

    def _write(self, joints: list[float]) -> None:
        super()._write(joints)
        now = self.tip()
        x0, y0 = page_xy(0, 0)
        on_sheet = x0 - 0.01 <= now[0] <= x0 + PAGE + 0.01 and y0 - 0.01 <= now[1] <= y0 + PAGE + 0.01
        if now[2] > PAPER_Z + 0.0015 or not on_sheet:
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
        site = self.data.site("gripperframe")
        if first + 1 + len(self.ink) - start > scene.maxgeom - (0 if live else 0):
            start = max(start, len(self.ink) - (scene.maxgeom - first - 1))  # out of room: keep the newest ink
        capsule(first, site.xpos, self.tip(), 0.0035, PENCIL)  # the pen
        count = max(scene.ngeom, first + 1) if live else first + 1
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
    as_pose = lambda joints: {f"{j}.pos": v for j, v in zip(sim.JOINTS, joints[:5] + [20.0])}
    grid = {"n": PAPER_N, "down": [], "up": []}
    for v in np.linspace(0, 1, PAPER_N):          # row 0 is the top of the page
        for u in np.linspace(0, 1, PAPER_N):      # column 0 is its left edge
            x, y = page_xy(u, v)
            grid["down"].append(as_pose(sim.solve(model, x, y, PAPER_Z - PRESS + PEN)))
            grid["up"].append(as_pose(sim.solve(model, x, y, PAPER_Z + LIFT + PEN)))
    (sim.SIM_POSES / "paper.json").write_text(json.dumps(grid))
    # Resting pose: pen held 5 cm above the middle of the page. From sim.py's folded-away home, the straight
    # joint move to the page dipped the pen through the table at the page's corner and left a mark.
    x, y = page_xy(0.5, 0.5)
    (sim.SIM_POSES / "home.json").write_text(json.dumps(as_pose(sim.solve(model, x, y, PAPER_Z + 0.05 + PEN))))


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


def strayed(ink, strokes) -> tuple[float, float]:
    """How far the ink is from the line asked for, in mm: (typical, worst)."""
    wanted = np.array([p for s in strokes for p in draw.resample(s)])
    drawn = np.array([((p[1] + PAGE / 2) / PAGE, (p[0] - PAGE_X) / PAGE) for seg in ink for p in seg])
    if not len(drawn):
        return float("inf"), float("inf")
    gaps = np.min(np.linalg.norm(drawn[:, None, :] - wanted[None, :, :], axis=2), axis=1) * PAGE * 1000
    return float(np.mean(gaps)), float(np.max(gaps))


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
    typical, worst = strayed(arm.ink, strokes)
    if arm.frames:
        arm.save_video(sim.OUT / "sim_draw.mp4")
    return {**result, "typical_mm": round(typical, 1), "worst_mm": round(worst, 1)}


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
    line = [(np.array([PAGE_X + 0.06, 0.0, PAPER_Z]), np.array([PAGE_X + 0.06, 0.012, PAPER_Z]))]
    assert strayed(line, [[(0.5, 0.5), (0.6, 0.5)]])[1] < 0.01          # ink exactly on the asked line
    assert abs(strayed(line, [[(0.5, 0.6), (0.6, 0.6)]])[0] - 12) < 0.01  # a line 0.1 of the page lower is 12 mm away
    main()
