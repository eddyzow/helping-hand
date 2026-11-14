"""Installed local font and fake drawing sink only: python -B -m tests.test_writing_boundaries."""
import threading
from types import SimpleNamespace
from unittest.mock import patch

import draw
from skills import write


def test_names():
    sent = []
    arm = SimpleNamespace()
    with patch.object(write.draw_skill, "run", side_effect=lambda arm, params, stop:
                      sent.append(params["strokes"]) or {"ok": True}):
        for text in ("Sam", "Maria Hernandez", "Dr. Ann Lee"):
            for style in ("print", "script"):
                assert write.run(arm, {"text": text, "style": style}, threading.Event())["ok"]
                assert write.draw_skill.checked_strokes(sent[-1])
        sent.clear()
        for text in ("", "x" * 25, "Zoë", "a\nb"):
            assert not write.run(arm, {"text": text}, threading.Event())["ok"] and not sent


def test_no_truncation(style):
    text, shortened = "Dr. Ann Marie Lee", "Dr. Ann Marie"
    truncated = [[list(point) for point in stroke] for stroke in draw.from_writing(shortened, style)]
    try:
        full = draw.from_writing(text, style)
    except ValueError:
        full = None  # Explicit refusal is acceptable when the complete name cannot fit.
    sent = []
    with patch.object(write.draw_skill, "run", side_effect=lambda arm, params, stop:
                      sent.append(params["strokes"]) or {"ok": True}):
        result = write.run(SimpleNamespace(), {"text": text, "style": style}, threading.Event())
    assert (not result["ok"] and not sent) or (result["ok"] and sent and sent[0] != truncated), \
        ("skill silently dropped Lee", result)
    assert full is None or full != draw.from_writing(shortened, style), "shared layout silently dropped Lee"


if __name__ == "__main__":
    test_names()
    print("ordinary names and invalid-input controls pass")
    failures = []
    for style in ("print", "script"):
        try:
            test_no_truncation(style)
        except AssertionError as error:
            failures.append((style, str(error)))
            print("FAIL", style, error)
    assert not failures, failures
