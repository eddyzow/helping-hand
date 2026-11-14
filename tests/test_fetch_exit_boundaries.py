"""Placement exit configuration with a temporary grid and fake arm only."""
import json
import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import core.arm
from skills import fetch


def test_exit_lift():
    calls, failures = [], []
    arm = SimpleNamespace(load_pose=lambda name: [0.] * 6,
                          home=lambda: calls.append("home") or True,
                          move_joints=lambda joints, seconds: calls.append(joints) or True)
    stop = SimpleNamespace(wait=lambda seconds: False)
    with tempfile.TemporaryDirectory() as directory:
        folder = Path(directory)
        down = {name + ".pos": 0. for name in core.arm.JOINTS}
        up = {name: 10. for name in down}
        (folder / "table.json").write_text(json.dumps({"n": 2, "up": [up] * 4, "down": [down] * 4}))
        with patch.object(core.arm, "POSES", folder):
            for value in (-1., 0., float("nan"), float("inf")):
                calls.clear()
                with patch.object(fetch, "EXIT_LIFT", value):
                    reply = fetch.run(arm, {"u": .5, "v": .5, "to_u": .5, "to_v": .5}, stop)
                if reply["ok"] or calls:
                    failures.append((value, reply, len(calls), [call[0] for call in calls if isinstance(call, list)]))
            calls.clear()
            with patch.object(fetch, "EXIT_LIFT", 1.5):
                assert fetch.run(arm, {"u": .5, "v": .5, "to_u": .5, "to_v": .5}, stop)["ok"]
                assert [15.] * 5 + [fetch.GRIP_OPEN] in calls
    assert not failures, ("invalid exit lift moved", failures)


if __name__ == "__main__":
    test_exit_lift()
    print("fetch exit boundaries ok")
