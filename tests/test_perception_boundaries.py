"""Fake providers/robot and temporary poses only: python -m tests.test_perception_boundaries."""
import ast
import contextlib
import io
import json
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
        "os": SimpleNamespace(environ={}), "sys": sys, "detect": lambda frame: boxes}
    functions("see.py", {"to_matches", "to_choice", "choose", "find_all"}, scope)
    malformed = [{"matches": [1], "near": []}]
    malformed += [{"matches": [1], "near": [], "put_down": value}
                  for value in (None, "true", 0, 1, [], {})]
    for answer in malformed:
        scope["_gemini"] = lambda *args: answer
        with contextlib.redirect_stderr(io.StringIO()):
            hits, _, _, near = scope["find_all"](frame, "put roof next to purple")
        assert hits == [] and near is None, (answer, hits, near)
    for placing, destinations in ((False, []), (True, []), (True, [2])):
        scope["_gemini"] = lambda *args: {"matches": [1], "put_down": placing, "near": destinations}
        with contextlib.redirect_stderr(io.StringIO()):
            hits, _, _, near = scope["find_all"](frame, "request")
        assert len(hits) == 1
        assert (near is None) if not placing else len(near) == len(destinations)


def test_standalone_placement():
    calls = []
    target = (.2, .3, "roof", 0.)
    robot = SimpleNamespace(disconnect=lambda: calls.append("disconnect"))
    arm = SimpleNamespace(follower=lambda: robot, move_to=lambda *args: calls.append("home"))
    scope = {"sys": sys, "see": SimpleNamespace(load_env=lambda: None, grab_frame=lambda: None),
             "load": lambda name: {}, "grasp": lambda *args: calls.append("grasp"), "EDGE": .05}
    functions("pick.py", {"main"}, scope)
    for near in ([], [target], [target, target], None):
        calls.clear()
        scope["locate"] = lambda *args: ([target], "request", near)
        command = "fetch roof" if near is None else "put roof next to purple"
        with patch.dict(sys.modules, {"arm": arm}), \
                patch.object(sys, "argv", ["pick.py", "--go", command]), \
                contextlib.redirect_stdout(io.StringIO()):
            scope["main"]()
        assert calls.count("grasp") == (1 if near is None else 0), (near, calls)
        assert calls[-1] == "disconnect", calls


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
    test_standalone_placement()
    test_taught_draw()
    print("perception boundaries ok")
