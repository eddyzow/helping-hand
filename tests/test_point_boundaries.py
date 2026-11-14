"""Fake arm, environment and voice routing: python -B -m tests.test_point_boundaries."""
import contextlib
import io
import json
import os
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import core.arm
from skills import point
from tests.test_perception_boundaries import functions


def test_point():
    calls = []
    fail_at = None

    def command(*args):
        calls.append(args)
        return len(calls) != fail_at

    arm = SimpleNamespace(home=lambda: command("home"), move_joints=command)
    stop = SimpleNamespace(wait=lambda seconds: False)
    table = {"n": 2, **{layer: [dict(zip((j + ".pos" for j in core.arm.JOINTS),
             [u, height, v, 0, 0, 20])) for v in (0, 1) for u in (0, 1)]
             for layer, height in (("up", 10), ("down", 0))}}
    valid = {"u": .5, "v": .5}
    with tempfile.TemporaryDirectory() as temporary, patch.object(core.arm, "POSES", Path(temporary)), \
            patch.object(point, "POINT_GRIP", 0), patch.object(point, "POINT_DIP", .5), \
            patch.object(point, "POINT_SECONDS", 0):
        assert not point.run(arm, valid, stop)["ok"] and not calls
        path = Path(temporary) / "table.json"
        path.write_text(json.dumps(table))
        for setting, invalids in (("POINT_GRIP", (-1, 101)), ("POINT_DIP", (-.1, 1.1)),
                                 ("POINT_SECONDS", (-1, 31))):
            for invalid in (*invalids, float("nan"), float("inf")):
                with patch.object(point, setting, invalid):
                    assert not point.run(arm, valid, stop)["ok"] and not calls
        for bad in ({}, {"u": True, "v": .5}, {"u": "0.5", "v": .5},
                    {"u": float("nan"), "v": .5}, {"u": .5, "v": float("inf")}, {"u": 2, "v": .5}):
            assert not point.run(arm, bad, stop)["ok"] and not calls
        table["down"][0]["shoulder_lift.pos"] = float("nan")
        path.write_text(json.dumps(table))
        assert not point.run(arm, valid, stop)["ok"] and not calls
        table["down"][0]["shoulder_lift.pos"] = 0
        path.write_text(json.dumps(table))
        assert point.run(arm, valid, stop)["ok"]
        assert calls[0] == calls[-1] == ("home",)
        assert [call[0][1] for call in calls[1:-1]] == [10, 5, 10]
        assert all(call[0][5] == 0 for call in calls[1:-1])
        for fail_at in range(1, 6):
            calls.clear()
            assert point.run(arm, valid, stop) == point.STOPPED and len(calls) == fail_at
        fail_at = None
        calls.clear()
        stop.wait = lambda seconds: True
        assert point.run(arm, valid, stop) == point.STOPPED and len(calls) == 3


def test_voice():
    commands, spoken = [], []
    found = []
    with tempfile.TemporaryDirectory() as temporary:
        scope = {"sys": sys, "Path": Path, "json": json, "os": os,
                 "__file__": str(Path(temporary) / "voice/route.py"), "speak": spoken.append,
                 "by_model": lambda *args: {"skill": "point", "params": {"object": "brick"}},
                 "locate": lambda thing: (found, None),
                 "send": lambda command: commands.append(command) or
                     ([{"name": "point"}] if command == "list" else {"ok": True})}
        functions("voice/route.py", {"main"}, scope)
        item = {"object": "red brick", "u": .2, "v": .7, "lift": .5, "turn": 90}
        for found in ([], [item, item], [item]):
            commands.clear()
            with patch.object(sys, "argv", ["route", "point at the red brick"]), \
                    contextlib.redirect_stdout(io.StringIO()):
                scope["main"]()
            expected = ["list"]
            if len(found) == 1:
                expected.append("run point " + json.dumps({k: item[k] for k in ("object", "u", "v")}))
                assert spoken[-1] == "That's the red brick."
            assert commands == expected, commands


if __name__ == "__main__":
    test_point()
    test_voice()
    print("point boundaries ok")
