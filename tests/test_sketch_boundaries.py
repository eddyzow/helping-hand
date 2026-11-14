"""Fake provider/voice/arm only: python -B -m tests.test_sketch_boundaries."""
import contextlib
import io
import json
import os
import sys
import tempfile
import threading
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import draw
from skills import draw as skill
from tests.test_perception_boundaries import functions


def test_stroke_preflight():
    stroke = [[.1, .1], [.9, .9]]
    bad = [None, True, [stroke] * 81, [[stroke[0]] * 4001]]
    bad += [[[[value, .1], [.2, .2]]] for value in (False, float("inf"), float("nan"), -0.1, 1.1, "0.2")]
    arm = SimpleNamespace(move_joints=lambda *args: (_ for _ in ()).throw(AssertionError("invalid strokes moved")))
    for strokes in bad:
        assert not skill.run(arm, {"strokes": strokes}, threading.Event())["ok"]
    assert skill.checked_strokes([stroke] * 80)
    assert len(skill.checked_strokes([[stroke[0]] * 4000])[0]) == 4000
    for path in (Path(draw.__file__).parent / "drawings").glob("sketch_*.json"):
        assert skill.checked_strokes(json.loads(path.read_text())), path


def test_generated_and_cached():
    reply = [{"smooth": True, "points": [[0, 0], [50, 100], [100, 0]]},
             {"points": [[True, 0], [1, 1]]}]
    see = SimpleNamespace(load_env=lambda: None, parse_reply=json.loads,
                          ask_claude=lambda *args, **kwargs: json.dumps(reply))
    with patch.dict(sys.modules, {"see": see}):
        strokes = draw.from_model("curve")
        assert len(strokes) == 1 and len(strokes[0]) > 3
        assert skill.checked_strokes(strokes)
        with tempfile.TemporaryDirectory() as temporary, patch.object(draw, "HERE", Path(temporary)):
            cache = Path(temporary) / "drawings/sketch_a_cat.json"
            cache.parent.mkdir()
            cache.write_text(json.dumps(strokes))
            with patch.object(see, "ask_claude", side_effect=AssertionError("cached request called provider")):
                assert draw.sketch("a cat") == strokes


def test_voice_sketch():
    strokes = [[(.1, .1), (.9, .9)]]
    commands, spoken = [], []
    with tempfile.TemporaryDirectory() as temporary:
        scope = {"sys": sys, "Path": Path, "json": json, "os": os,
                 "__file__": str(Path(temporary) / "voice/route.py"), "speak": spoken.append,
                 "by_model": lambda *args: {"skill": "draw", "params": {"what": "a cat"}},
                 "send": lambda command: commands.append(command) or
                     ([{"name": "draw"}] if command == "list" else {"ok": True})}
        functions("voice/route.py", {"main"}, scope)
        for failed in (False, True):
            commands.clear()
            with patch.object(sys, "argv", ["route", "draw a cat"]), \
                    patch.object(draw, "sketch", side_effect=LookupError("fake unavailable") if failed else None,
                                 return_value=strokes), \
                    contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                scope["main"]()
            assert commands == (["list"] if failed else ["list", "run draw " + json.dumps({"strokes": strokes})]), commands


if __name__ == "__main__":
    test_stroke_preflight()
    test_generated_and_cached()
    test_voice_sketch()
    print("sketch boundaries ok")
