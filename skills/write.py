"""Write a person's name (or a few words) on the paper with the pen, through the dispatcher and its stop key.

    run write {"text": "Dr. Lee"}
    run write {"text": "Maria Hernandez", "style": "script"}
    python -m skills.write          # self-check on a fake arm, no hardware

The writing is laid out by the root draw.py (one word per line when the name is long) and drawn by
skills/draw.py, so it needs the same taught paper grid and the pen already in the gripper.
"""
import draw as strokes_lib
from skills import draw as draw_skill

NAME = "write"
DESCRIPTION = "Write a person's name, or a few words, on the paper with the pen"
PARAMS = {"text": "str: the name or words to write, e.g. 'Dr. Lee'",
          "style": "optional: 'print' (default, plain letters) or 'script' (joined-up handwriting)"}

MAX_CHARS = 24  # three lines of eight: more than that is too small to read on the page


def run(arm, params, stop):
    text, style = params.get("text"), params.get("style", "print")
    if not isinstance(text, str) or not text.strip() or len(text.strip()) > MAX_CHARS or not text.isascii() or not text.isprintable():
        return {"ok": False, "reason": f"text must be 1 to {MAX_CHARS} plain characters"}
    if style not in strokes_lib.FONTS:
        return {"ok": False, "reason": "style must be 'print' or 'script'"}
    try:  # letters the font does not have give no strokes: say so instead of writing nothing
        strokes = strokes_lib.from_writing(text.strip(), style)
    except ValueError as err:
        return {"ok": False, "reason": f"cannot write '{text}': {err}"}
    return draw_skill.run(arm, {"strokes": [[list(point) for point in stroke] for stroke in strokes]}, stop)


if __name__ == "__main__":
    from core.arm import MockArm

    moved = []

    class FakeArm(MockArm):
        def move_joints(self, joints_deg, duration_s):
            moved.append(list(joints_deg))
            return True

    real_run, sent = draw_skill.run, []
    draw_skill.run = lambda arm, params, stop: sent.append(params) or {"ok": True, "reason": ""}
    arm = FakeArm()
    for bad in ({}, {"text": ""}, {"text": "   "}, {"text": "x" * 25}, {"text": 7}, {"text": "Zoë"}, {"text": "a\nb"},
                {"text": "Sam", "style": "comic"}):
        assert not run(arm, bad, arm.halt)["ok"] and not sent and not moved, f"{bad!r} must not reach the arm"
    assert run(arm, {"text": "Maria Hernandez"}, arm.halt)["ok"] and len(sent) == 1
    points = [p for stroke in sent[0]["strokes"] for p in stroke]
    assert all(0 <= u <= 1 and 0 <= v <= 1 for u, v in points), "the writing stays on the page"
    assert draw_skill.checked_strokes(sent[0]["strokes"]), "and passes the draw skill's own check"
    assert run(arm, {"text": "Sam", "style": "script"}, arm.halt)["ok"] and len(sent) == 2
    draw_skill.run = real_run
    print("write ok")
