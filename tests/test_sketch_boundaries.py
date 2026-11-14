"""Fake provider/voice/arm only: python -B -m tests.test_sketch_boundaries."""
import contextlib
import io
import json
import math
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
    for prefix in ("sketch", "simple"):
        for path in (Path(draw.__file__).parent / "drawings").glob(f"{prefix}_*.json"):
            assert skill.checked_strokes(json.loads(path.read_text())), path


def test_generated_and_cached():
    reply = [{"smooth": True, "points": [[0, 0], [50, 100], [100, 0]]},
             {"points": [[True, 0], [1, 1]]}]
    prompts = []
    see = SimpleNamespace(load_env=lambda: None, parse_reply=json.loads,
                          ask_claude=lambda prompt, *args, **kwargs: prompts.append(prompt) or json.dumps(reply))
    with patch.dict(sys.modules, {"see": see}):
        strokes = draw.from_model("curve")
        assert len(strokes) == 1 and len(strokes[0]) > 3
        assert skill.checked_strokes(strokes)
        reply[0]["points"] = [[0, 0], [10, 0], [10, 10], [0, 10], [0, 1]]
        loop = draw.from_model("loop")[0]
        assert loop[0] == loop[-1], "near-closed model loop reopened during smoothing"
        assert draw.closed_up([(0, 0), (10, 0)]) == [(0, 0), (10, 0)]
        for detail, wording in (("detailed", "4 to 30 strokes"), ("simple", "3 to 10 strokes")):
            with patch.dict(os.environ, {"DRAW_DETAIL": detail}):
                assert skill.checked_strokes(draw.from_model("loop"))
                assert wording in prompts[-1]
        with tempfile.TemporaryDirectory() as temporary, patch.object(draw, "HERE", Path(temporary)):
            cache = Path(temporary) / "drawings/sketch_a_cat.json"
            cache.parent.mkdir()
            cache.write_text(json.dumps(strokes))
            simple = [[(.2, .2), (.8, .8)]]
            cache.with_name("simple_a_cat.json").write_text(json.dumps(simple))
            with patch.object(see, "ask_claude", side_effect=AssertionError("cached request called provider")):
                for detail, expected in (("detailed", strokes), ("simple", simple)):
                    with patch.object(draw, "DETAIL", detail):
                        assert draw.sketch("a cat") == expected


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


def test_pen_motion():
    strokes = [[[.1, .1], [.2, .1]], [[.8, .1], [.9, .1]]]
    grid = {"n": 2}
    for layer, height in (("up", 10), ("down", 0)):
        grid[layer] = [dict(zip((joint + ".pos" for joint in skill.JOINTS), [u, height, v, 0, 0, 20]))
                       for v in (0, 1) for u in (0, 1)]
    with tempfile.TemporaryDirectory() as temporary:
        path = Path(temporary) / "paper.json"
        path.write_text(json.dumps(grid))
        sent = []
        arm = SimpleNamespace(load_pose=lambda name: [0] * 6,
                              move_joints=lambda joints, seconds: sent.append((joints, seconds)) or True)
        with patch.object(skill, "GRID", path), patch.object(draw, "PEN_DRAG", 0), \
                patch.object(draw, "PEN_SQUEEZE", 8), patch.object(draw, "PEN_SPEED", .15):
            for invalid in (float("nan"), float("inf"), -.001, .101):
                draw.PEN_DRAG = invalid
                assert not skill.run(arm, {"strokes": strokes}, threading.Event())["ok"] and not sent
            draw.PEN_DRAG = 0
            steps = skill.plan(strokes, grid, [0] * 6)
            hop = [seconds for joints, seconds in steps
                   if math.isclose(joints[0], .8) and joints[1] == 10]
            assert len(hop) == 1 and math.isclose(hop[0], 1), hop
            assert sum(seconds == skill.PEN_SETTLE_S for _, seconds in steps) == 2
            assert sum(seconds == skill.PEN_FINISH_S for _, seconds in steps) == 2
            draw.PEN_DRAG = .03
            led = skill.plan(strokes, grid, [0] * 6)
            assert math.isclose(max(joints[0] for joints, _ in led if joints[1] == 0), .93)


if __name__ == "__main__":
    test_stroke_preflight()
    test_generated_and_cached()
    test_voice_sketch()
    test_pen_motion()
    print("sketch boundaries ok")
