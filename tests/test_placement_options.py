"""Pure placement planning and fake-arm validation; no camera or robot."""
import ast
import json
import math
import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import core.arm
from skills import fetch
from tests.test_perception_boundaries import functions


def placement_scope():
    path = Path(__file__).resolve().parents[1] / "pick.py"
    names = {"DROP_GAP", "GRID_ASPECT", "SIDES", "STACK_LIFT"}
    nodes = [node for node in ast.parse(path.read_text()).body
             if isinstance(node, ast.Assign) and any(
                 isinstance(target, ast.Name) and target.id in names for target in node.targets)]
    scope = {"os": SimpleNamespace(environ={})}
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(path), "exec"), scope)
    functions("pick.py", {"drop_spot"}, scope)
    return scope


def test_drop_directions():
    scope = placement_scope()
    drop = scope["drop_spot"]
    cases = {"left of": (.2, .5, 0), "right of": (.8, .5, 0),
             "behind": (.5, .2, 0), "in front of": (.5, .8, 0),
             "on top of": (.5, .5, .5), "onto": (.5, .5, .5)}
    for words, expected in cases.items():
        actual = drop((.1, .5), (.5, .5), "put red " + words + " blue")
        assert len(actual) == 3 and all(math.isclose(a, b) for a, b in zip(actual, expected)), (words, actual)
    assert drop((.5, .5), (.5, -.9)) == (.5, .05, 0.)
    scope["GRID_ASPECT"] = 2
    assert drop((.1, .5), (.5, .2), "in front of blue") == (.5, .8, 0.)


def test_inline_drop_assertions():
    path = Path(__file__).resolve().parents[1] / "pick.py"
    checks = [check for node in ast.parse(path.read_text()).body
              if isinstance(node, ast.If) and "__main__" in ast.unparse(node.test)
              for check in node.body if isinstance(check, ast.Assert)
              and any(isinstance(n, ast.Name) and n.id == "drop_spot" for n in ast.walk(check))]
    assert checks
    exec(compile(ast.Module(body=checks, type_ignores=[]), str(path), "exec"), placement_scope())


def test_fetch_options():
    calls, waits = [], []
    arm = SimpleNamespace(load_pose=lambda name: [0.] * 6,
                          home=lambda: calls.append("home") or True,
                          move_joints=lambda joints, seconds: calls.append(joints) or True)
    stop = SimpleNamespace(wait=lambda seconds: waits.append(seconds) or False)
    with tempfile.TemporaryDirectory() as directory:
        folder = Path(directory)
        down = {name + ".pos": 0. for name in core.arm.JOINTS}
        up = {name: value + 10 for name, value in down.items()}
        (folder / "table.json").write_text(json.dumps({"n": 2, "up": [up] * 4, "down": [down] * 4}))
        with patch.object(core.arm, "POSES", folder):
            for key, bad_values in {"to_lift": [-.1, 1.1, float("nan"), float("inf"), True, "0.5", None],
                                    "hold": [-1, 31, float("nan"), float("inf"), True, "3", None]}.items():
                for value in bad_values:
                    calls.clear()
                    result = fetch.run(arm, {"u": .5, "v": .5, key: value}, stop)
                    assert not result["ok"] and calls == [], (key, value, result, calls)
            assert fetch.run(arm, {"u": .5, "v": .5, "hold": 7}, stop)["ok"]
            assert waits == [7], waits
            calls.clear()
            waits.clear()
            assert fetch.run(arm, {"u": .5, "v": .5, "to_u": .5, "to_v": .5, "to_lift": .5}, stop)["ok"]
            assert [5.] * 5 + [fetch.GRIP_OPEN] in calls
            assert waits == []


if __name__ == "__main__":
    test_drop_directions()
    test_inline_drop_assertions()
    test_fetch_options()
    print("placement options ok")
