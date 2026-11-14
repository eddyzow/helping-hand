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
                                    "lift": [-.1, 1.1, float("nan"), float("inf"), True, "0.5", None],
                                    "turn": [-91, 91, float("nan"), float("inf"), True, "30", None],
                                    "to_turn": [-91, 91, float("nan"), float("inf"), True, "30", None],
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
            calls.clear()
            assert fetch.run(arm, {"u": .5, "v": .5, "lift": .25, "hold": 0}, stop)["ok"]
            assert [2.5] * 5 + [fetch.GRIP_CLOSED] in calls
            calls.clear()
            assert fetch.run(arm, {"u": .5, "v": .5, "to_u": .5, "to_v": .5,
                                   "to_lift": .5, "to_turn": 30}, stop)["ok"]
            assert [5., 5., 5., 5., -25., fetch.GRIP_OPEN] in calls
            calls.clear()
            with patch.multiple(fetch, ROLL_MIN=-20., ROLL_MAX=20.):
                result = fetch.run(arm, {"u": .5, "v": .5, "to_u": .5, "to_v": .5, "to_turn": 80}, stop)
                assert not result["ok"] and calls == [], (result, calls)


def test_held_shift():
    coordinates = []

    def interpolate(layer, n, u, v):
        coordinates.append((round(u, 6), round(v, 6)))
        return {name + ".pos": 0. for name in core.arm.JOINTS}

    table = {"n": 2, "up": [], "down": []}
    with patch.object(fetch, "interpolate", interpolate), patch.multiple(
            fetch, HELD_SHIFT_MM=(10., 20.), GRID_WIDTH_MM=100., GRID_DEPTH_MM=100., JAW_ARM_MM=0.):
        assert not isinstance(fetch._aim(table, .5, .5, 0., 0., holding=True), str)
        assert coordinates[-2:] == [(.4, .3)] * 2
        assert not isinstance(fetch._aim(table, .5, .5, 90., 0., holding=True), str)
        assert coordinates[-2:] == [(.7, .4)] * 2
        assert not isinstance(fetch._aim(table, .5, .5, 0., 0.), str)
        assert coordinates[-2:] == [(.5, .5)] * 2
        assert isinstance(fetch._aim(table, 0., 0., 0., 0., holding=True), str)


if __name__ == "__main__":
    test_fetch_options()
    test_held_shift()
    print("placement options ok")
