"""Write a word with a pen, through the dispatcher and its stop key. Strokes come from Eddy's root draw.py.

    run draw                       # writes WORD
    run draw {"text": "BEN"}
    python -m skills.draw          # self-check on a fake arm, no hardware

Needs poses/paper.json: teach it with `python arm.py teach paper` (pen on the paper, then lifted).
Put the pen in the gripper before running. The arm keeps the pen grip the whole time, home included.

UNTESTED ON HARDWARE. Not known yet: whether the pen touches evenly across the page, how hard
PEN_SQUEEZE grips, and whether moving home with a pen in the gripper clears the table.
"""
import json
import math
from pathlib import Path

import draw as strokes_lib  # the root draw.py: text -> strokes, resampling, pen settings
from core.arm import JOINTS, _checked
from grid import interpolate

NAME = "draw"
DESCRIPTION = "Write a short word on the paper with the pen"
PARAMS = {"text": "str"}

WORD = "HI"      # what it writes when no text is given
MAX_CHARS = 8    # longer words get too small to read and too slow for a demo
MAX_STEP_S = 30  # the arm refuses any single move longer than this
GRID = Path(__file__).parent.parent / "poses" / "paper.json"
STOPPED = {"ok": False, "reason": "stopped"}


def plan(text: str, grid: dict, home: list[float]) -> list[tuple[list[float], float]]:
    """Every (joints, seconds) step for the whole word, home to home. Nothing moves here."""
    n = grid["n"]

    def pose(layer: str, u: float, v: float) -> list[float]:
        p = interpolate(grid[layer], n, u, v)
        # taught limp around the pen, so the taught value is exactly pen width: squeeze a bit more
        p["gripper.pos"] = max(0.0, p["gripper.pos"] - strokes_lib.PEN_SQUEEZE)
        return _checked(p[f"{j}.pos"] for j in JOINTS)

    grip = pose("up", 0.5, 0.5)[5]
    rest = _checked(home[:5] + [grip])  # home, but still holding the pen
    steps = [(rest, 2.0)]
    for stroke in strokes_lib.from_text(text):
        pts = strokes_lib.resample(stroke)
        steps.append((pose("up", *pts[0]), 1.0))
        steps.append((pose("down", *pts[0]), 0.4))
        steps += [(pose("down", u, v), strokes_lib.STEP / strokes_lib.PEN_SPEED) for u, v in pts[1:]]
        steps.append((pose("up", *pts[-1]), 0.4))
    steps.append((rest, 2.0))
    for _, seconds in steps:  # a bad PEN_SPEED must be caught here, not after the pen is already down
        if not (math.isfinite(seconds) and 0 < seconds <= MAX_STEP_S):
            raise ValueError(f"a move would take {seconds} seconds: check PEN_SPEED ({strokes_lib.PEN_SPEED})")
    return steps


def run(arm, params, stop):
    text = params.get("text", WORD)
    if not isinstance(text, str) or not text.strip() or len(text) > MAX_CHARS or not text.isascii():
        return {"ok": False, "reason": f"text must be 1 to {MAX_CHARS} plain characters"}
    if not GRID.exists():
        return {"ok": False, "reason": "no paper grid: teach it with python arm.py teach paper"}
    try:  # the whole word is planned and checked before the first move
        steps = plan(text.strip(), json.loads(GRID.read_text()), arm.load_pose("home"))
    except (ValueError, KeyError, IndexError, TypeError, ZeroDivisionError) as err:
        return {"ok": False, "reason": f"cannot plan '{text}': {err}"}
    print(f"[draw] '{text.strip()}': {len(steps)} moves, about {sum(s for _, s in steps):.0f} seconds", flush=True)
    for joints, seconds in steps:
        if not arm.move_joints(joints, seconds):
            return STOPPED
    return {"ok": True, "reason": ""}


if __name__ == "__main__":
    import tempfile

    from core.arm import MockArm

    class FakeArm(MockArm):  # records each commanded target and jumps there, so the check is instant
        def __init__(self, stop_after=None):
            super().__init__()
            self.sent, self.stop_after = [], stop_after

        def move_joints(self, joints_deg, duration_s):
            if self.halt.is_set():
                return False
            self.sent.append(list(joints_deg))
            if self.stop_after is not None and len(self.sent) >= self.stop_after:
                self.halt.set()
            return not self.halt.is_set()

    def taught(lift: float) -> list[dict]:  # a made-up 3x3 grid: pan follows u, elbow follows v, lift is the pen height
        return [{"shoulder_pan.pos": 20 * c - 20, "shoulder_lift.pos": lift, "elbow_flex.pos": 10 * r,
                 "wrist_flex.pos": 0, "wrist_roll.pos": 0, "gripper.pos": 20} for r in range(3) for c in range(3)]

    def write_grid(grid: dict) -> None:
        global GRID
        GRID = Path(tempfile.mkdtemp()) / "paper.json"
        GRID.write_text(json.dumps(grid))

    real_grid = GRID
    GRID = Path("no-such-grid.json")
    arm = FakeArm()
    assert not run(arm, {}, arm.halt)["ok"] and arm.sent == [], "no grid: must not move"

    write_grid({"n": 3, "down": taught(0), "up": taught(10)})
    for bad in ("", "   ", "x" * 9, 7, "héllo"):
        arm = FakeArm()
        assert not run(arm, {"text": bad}, arm.halt)["ok"] and arm.sent == [], f"bad text {bad!r} must not move"

    arm = FakeArm()
    assert run(arm, {}, arm.halt) == {"ok": True, "reason": ""}
    home = arm.load_pose("home")
    grip = 20 - strokes_lib.PEN_SQUEEZE
    assert arm.sent[0] == arm.sent[-1] == home[:5] + [grip], "starts and ends at home, still holding the pen"
    assert all(t[5] == grip for t in arm.sent), "pen grip never changes"
    assert arm.sent[1][1] == 10 and arm.sent[2][1] == 0, "first stroke: arrive lifted, then lower"
    lifts = [t[1] for t in arm.sent[1:-1]]
    assert set(lifts) == {0, 10} and lifts[-1] == 10, "pen is either down or up, and ends up"

    arm = FakeArm(stop_after=5)  # stop lands mid-word: nothing more is sent
    assert run(arm, {}, arm.halt) == STOPPED and len(arm.sent) == 5

    good_speed = strokes_lib.PEN_SPEED
    for bad_speed in (-0.15, float("nan"), 0.0001, 0.0):  # the real MockArm: its position must not change
        strokes_lib.PEN_SPEED = bad_speed
        arm = MockArm()
        before = arm.get_joints()
        assert not run(arm, {}, arm.halt)["ok"] and arm.get_joints() == before, f"PEN_SPEED {bad_speed}: must not move"
    strokes_lib.PEN_SPEED = good_speed

    write_grid({"n": 3, "down": taught(float("nan")), "up": taught(10)})
    arm = FakeArm()
    assert not run(arm, {}, arm.halt)["ok"] and arm.sent == [], "bad taught value: must not move"
    GRID = real_grid
    print("draw ok")
