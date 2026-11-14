"""Fake providers/robot and temporary poses only: python -m tests.test_perception_boundaries."""
import ast
import contextlib
import io
import json
import re
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch


def functions(filename, names, scope):
    path = Path(__file__).resolve().parents[1] / filename
    nodes = [n for n in ast.parse(path.read_text()).body
             if isinstance(n, ast.FunctionDef) and n.name in names]
    assert len(nodes) == len(names)
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(path), "exec"), scope)


def test_chooser_flag():
    frame = SimpleNamespace(shape=(100, 100, 3))
    boxes = [{"label": "roof", "x0": 0, "x1": 20, "y0": 0, "y1": 20},
             {"label": "purple", "x0": 60, "x1": 80, "y0": 60, "y1": 80}]
    scope = {
        "numbered": lambda *args: frame, "CHOOSER_LONG_EDGE": 100, "CHOOSE": "{command}",
        "cv2": SimpleNamespace(imencode=lambda *args: (True, SimpleNamespace(tobytes=lambda: b""))),
        "json": json, "re": re, "detect": lambda frame: boxes}
    functions("see.py", {"parse_reply", "_number", "to_matches", "to_choice", "choose", "find_all"}, scope)
    scope["math"] = __import__("math")
    spot = {"u": .4, "v": .6, "height_mm": 19, "onto": None}
    malformed = [{"matches": [1], "place": spot, "pick_height_mm": 0}, {"matches": [1], "place": spot, "put_down": True}]
    malformed += [{"matches": [1], "place": spot, "pick_height_mm": 0, "put_down": value}
                  for value in (None, "true", 0, 1, [], {})]
    for answer in malformed:  # no true/false flag: nothing is picked, so nothing can be handed over
        scope["ask_claude"] = lambda *args: json.dumps(answer)
        with contextlib.redirect_stderr(io.StringIO()):
            hits, _, _, placing, place, _ = scope["find_all"](frame, "put roof next to purple")
        assert hits == [] and not placing and place is None, (answer, hits, placing, place)
    bad_place = {"u": "0.4", "v": .6, "height_mm": 19, "onto": None}
    for flag, given, placing_expected, place_expected in (
            (False, None, False, None), (True, None, True, None), (True, bad_place, True, None), (True, spot, True, spot),
            (True, {**spot, "onto": 2}, True, {**spot, "onto": 2, "box": boxes[1]}),
            (True, {**spot, "onto": True}, True, None), (True, {**spot, "onto": 3}, True, None)):
        scope["ask_claude"] = lambda *args: json.dumps({"matches": [1], "pick_height_mm": 0, "put_down": flag, "place": given})
        with contextlib.redirect_stderr(io.StringIO()):
            hits, _, _, placing, place, _ = scope["find_all"](frame, "request")
        assert len(hits) == 1 and placing is placing_expected and place == place_expected, (flag, given, placing, place)


def test_standalone_placement():
    calls = []
    target = (.2, .3, "roof", 0.)
    robot = SimpleNamespace(disconnect=lambda: calls.append("disconnect"))
    arm = SimpleNamespace(follower=lambda: robot, move_to=lambda *args: calls.append("home"))
    scope = {"sys": sys, "see": SimpleNamespace(load_env=lambda: None, grab_frame=lambda: None),
             "load": lambda name: {}, "grasp": lambda *args: calls.append("grasp"), "EDGE": .05}
    functions("pick.py", {"main"}, scope)
    for spot, problem, lift in ((None, "I can't work out where to put it.", 0.), ((.5, .5, 0.), None, 0.), (None, None, .5), (None, None, 0.)):
        calls.clear()
        scope["locate"] = lambda *args: ([target], "request", spot, problem, lift)
        handover = spot is None and problem is None and not lift
        with patch.dict(sys.modules, {"arm": arm}), \
                patch.object(sys, "argv", ["pick.py", "--go", "request"]), \
                contextlib.redirect_stdout(io.StringIO()):
            scope["main"]()
        assert calls.count("grasp") == (1 if handover else 0), (spot, problem, calls)
        assert calls[-1] == "disconnect", calls


def test_contradictory_place():
    scope = {"math": __import__("math")}
    functions("see.py", {"_number", "to_matches", "to_choice"}, scope)
    failures = []
    for value in ("0.4", float("nan"), float("inf"), True):
        reply = {"matches": [1], "put_down": False, "pick_height_mm": 0,
                 "place": {"u": value, "v": .6, "height_mm": 19, "onto": None}}
        picked, placing, place, _ = scope["to_choice"](reply, 1)
        if picked and not placing:
            failures.append((value, picked, placing, place))
    assert not failures, ("malformed non-null place became handover", failures)


def test_taught_draw():
    calls = []
    robot = SimpleNamespace(disconnect=lambda: calls.append("disconnect"))
    arm = SimpleNamespace(follower=lambda: (calls.append("connect") or robot))
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        (root / "poses").mkdir()
        scope = {"HERE": root, "json": json, "Stroke": list, "PEN_SQUEEZE": 5}
        functions("draw.py", {"draw"}, scope)
        for layer in ("up", "down"):
            for value in (float("nan"), float("inf"), -float("inf"), True, "30", None, 30.0):
                calls.clear()
                grid = {"n": 2, "up": [{"gripper.pos": 30.0}], "down": [{"gripper.pos": 30.0}]}
                grid[layer][0]["gripper.pos"] = value
                (root / "poses" / "paper.json").write_text(json.dumps(grid))
                with patch.dict(sys.modules, {"arm": arm, "grid": SimpleNamespace(interpolate=None)}):
                    try:
                        scope["draw"]([])
                    except SystemExit:
                        assert value != 30.0 and not calls, calls
                    else:
                        assert value == 30.0 and calls == ["connect", "disconnect"], (value, calls)


if __name__ == "__main__":
    test_chooser_flag()
    test_contradictory_place()
    test_standalone_placement()
    test_taught_draw()
    print("perception boundaries ok")
