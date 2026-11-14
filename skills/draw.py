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
DESCRIPTION = "Draw a picture of something, or write a short word, on the paper with the pen"
PARAMS = {"text": "str: a short word to write",
          "what": "str: a thing to sketch, in the person's own words, e.g. 'a cat' (voice/route.py turns it into strokes)",
          "strokes": "filled in by voice/route.py or sim_draw.py for a sketch: pen strokes as [[[u, v], ...], ...], 0 to 1"}

WORD = "HI"      # what it writes when no text is given
MAX_CHARS = 8    # longer words get too small to read and too slow for a demo
TRAVEL_SPEED = 0.6   # pen-up travel between strokes, in pages per second; never quicker than TRAVEL_MIN_S
TRAVEL_MIN_S = 0.35
PEN_SETTLE_S = 0.25  # wait this long after lowering the pen: it lands late, and short strokes (an eye) were skipped
PEN_FINISH_S = 0.15  # and this long at the end of a stroke before lifting, so the dragging point catches up
MAX_STEP_S = 30  # the arm refuses any single move longer than this
MAX_DRAG = 0.1    # most the pen may be led ahead of the line, as a fraction of the page
MAX_SQUEEZE = 30  # most the gripper may close past the taught pen width, on its 0-100 scale
GRID = Path(__file__).parent.parent / "poses" / "paper.json"
STOPPED = {"ok": False, "reason": "stopped"}


MAX_STROKES, MAX_POINTS = 80, 4000  # a sketch bigger than this is not a demo any more


def checked_strokes(strokes) -> list:
    """Strokes from outside (a model or a database) -> lists of (u, v) inside the page, or ValueError."""
    if not isinstance(strokes, list) or not 1 <= len(strokes) <= MAX_STROKES:
        raise ValueError(f"strokes must be a list of 1 to {MAX_STROKES} strokes")
    out = []
    for stroke in strokes:
        if not isinstance(stroke, (list, tuple)) or len(stroke) < 2:
            raise ValueError("every stroke needs at least two points")
        for point in stroke:
            if not (isinstance(point, (list, tuple)) and len(point) == 2
                    and all(type(n) in (int, float) and math.isfinite(n) and 0 <= n <= 1 for n in point)):
                raise ValueError(f"a stroke point must be two numbers from 0 to 1, got {point!r}")
        out.append([(float(u), float(v)) for u, v in stroke])
    if sum(len(s) for s in out) > MAX_POINTS:
        raise ValueError(f"more than {MAX_POINTS} points")
    return out


def plan(text, grid: dict, home: list[float]) -> list[tuple[list[float], float]]:
    """Every (joints, seconds) step for the whole word (or, given a list, those strokes), home to
    home. Nothing moves here."""
    n = grid["n"]
    squeeze = strokes_lib.PEN_SQUEEZE  # read from the environment: NaN would clench fully, a negative would let go
    if not (math.isfinite(squeeze) and 0 <= squeeze <= MAX_SQUEEZE):
        raise ValueError(f"PEN_SQUEEZE must be 0 to {MAX_SQUEEZE}, got {squeeze}")

    def pose(layer: str, u: float, v: float) -> list[float]:
        p = interpolate(grid[layer], n, u, v)
        joints = _checked(p[f"{j}.pos"] for j in JOINTS)  # before the clamp: max(0.0, nan) is 0.0 and would hide a bad value
        # taught limp around the pen, so the taught value is exactly pen width: squeeze a bit more
        joints[5] = max(0.0, joints[5] - squeeze)
        return joints

    drag = strokes_lib.PEN_DRAG
    if not (math.isfinite(drag) and 0 <= drag <= MAX_DRAG):
        raise ValueError(f"PEN_DRAG must be 0 to {MAX_DRAG}, got {drag}")

    def led(pts: list) -> list:
        """The points to command so the trailing pen point lands on pts: each one pushed `drag` further
        along the way the pen is travelling when it gets there."""
        out = [pts[0]]
        for (u0, v0), (u1, v1) in zip(pts, pts[1:]):
            length = math.hypot(u1 - u0, v1 - v0) or 1.0
            out.append((u1 + drag * (u1 - u0) / length, v1 + drag * (v1 - v0) / length))
        return out

    grip = pose("up", 0.5, 0.5)[5]
    rest = _checked(home[:5] + [grip])  # home, but still holding the pen
    steps = [(rest, 2.0)]
    at = None  # where the pen last was on the page
    for stroke in (strokes_lib.from_text(text) if isinstance(text, str) else text):
        pts = led(strokes_lib.resample(stroke))
        hop = 1.0 if at is None else max(TRAVEL_MIN_S, math.hypot(pts[0][0] - at[0], pts[0][1] - at[1]) / TRAVEL_SPEED)
        steps.append((pose("up", *pts[0]), hop))
        at = pts[-1]
        steps.append((pose("down", *pts[0]), 0.4))
        steps.append((pose("down", *pts[0]), PEN_SETTLE_S))
        steps += [(pose("down", u, v), strokes_lib.STEP / strokes_lib.PEN_SPEED) for u, v in pts[1:]]
        steps.append((pose("down", *pts[-1]), PEN_FINISH_S))
        steps.append((pose("up", *pts[-1]), 0.4))
    steps.append((rest, 2.0))
    for _, seconds in steps:  # a bad PEN_SPEED must be caught here, not after the pen is already down
        if not (math.isfinite(seconds) and 0 < seconds <= MAX_STEP_S):
            raise ValueError(f"a move would take {seconds} seconds: check PEN_SPEED ({strokes_lib.PEN_SPEED})")
    return steps


def run(arm, params, stop):
    text = params.get("text", WORD)
    if "strokes" in params:  # a sketch: the strokes are checked here, the text rules do not apply
        try:
            text = checked_strokes(params["strokes"])
        except ValueError as err:
            return {"ok": False, "reason": str(err)}
    elif "what" in params:
        return {"ok": False, "reason": "a sketch needs its strokes: voice/route.py or sim_draw.py supplies them"}
    elif not isinstance(text, str) or not text.strip() or len(text) > MAX_CHARS or not text.isascii():
        return {"ok": False, "reason": f"text must be 1 to {MAX_CHARS} plain characters"}
    if not GRID.exists():
        return {"ok": False, "reason": "no paper grid: teach it with python arm.py teach paper"}
    try:  # the whole word is planned and checked before the first move
        steps = plan(text.strip() if isinstance(text, str) else text, json.loads(GRID.read_text()), arm.load_pose("home"))
    except (ValueError, KeyError, IndexError, TypeError, ZeroDivisionError) as err:
        return {"ok": False, "reason": f"cannot plan '{text}': {err}"}
    print(f"[draw] {text.strip() if isinstance(text, str) else 'sketch'!r}: {len(steps)} moves, about {sum(s for _, s in steps):.0f} seconds", flush=True)
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

    arm = FakeArm()  # a sketch: ready-made strokes are drawn; bad ones never move the arm
    assert run(arm, {"strokes": [[[0.1, 0.1], [0.9, 0.9]]]}, arm.halt)["ok"] and len(arm.sent) > 4
    for bad in ([], [[[0.1, 0.1]]], [[[0.1, 0.1], [1.5, 0.2]]], [[[0.1, float("nan")], [0.2, 0.2]]], "cat", [[[0.1, 0.1], ["a", 0.2]]]):
        arm = FakeArm()
        assert not run(arm, {"strokes": bad}, arm.halt)["ok"] and arm.sent == [], f"bad strokes {bad!r} must not move"

    arm = FakeArm(stop_after=5)  # stop lands mid-word: nothing more is sent
    assert run(arm, {}, arm.halt) == STOPPED and len(arm.sent) == 5

    good_speed = strokes_lib.PEN_SPEED
    for bad_speed in (-0.15, float("nan"), 0.0001, 0.0):  # the real MockArm: its position must not change
        strokes_lib.PEN_SPEED = bad_speed
        arm = MockArm()
        before = arm.get_joints()
        assert not run(arm, {}, arm.halt)["ok"] and arm.get_joints() == before, f"PEN_SPEED {bad_speed}: must not move"
    strokes_lib.PEN_SPEED = good_speed

    good_squeeze = strokes_lib.PEN_SQUEEZE
    for bad_squeeze in (-5, float("nan"), float("inf"), 31):
        strokes_lib.PEN_SQUEEZE = bad_squeeze
        arm = MockArm()
        before = arm.get_joints()
        assert not run(arm, {}, arm.halt)["ok"] and arm.get_joints() == before, f"PEN_SQUEEZE {bad_squeeze}: must not move"
    strokes_lib.PEN_SQUEEZE = good_squeeze

    write_grid({"n": 3, "down": taught(float("nan")), "up": taught(10)})
    arm = FakeArm()
    assert not run(arm, {}, arm.halt)["ok"] and arm.sent == [], "bad taught value: must not move"

    bad_grip = taught(0)
    bad_grip[4]["gripper.pos"] = float("nan")  # one taught point with a broken gripper reading
    write_grid({"n": 3, "down": bad_grip, "up": taught(10)})
    arm = FakeArm()
    assert not run(arm, {}, arm.halt)["ok"] and arm.sent == [], "bad taught gripper: must not move"
    GRID = real_grid
    print("draw ok")
