"""The fetch skill against the mock arm. Run: python -m tests.test_fetch  (or pytest)"""
import json
import tempfile
import threading
from pathlib import Path

import core.arm
from core.arm import JOINTS, get_arm
from skills import fetch


def pose(base):
    return {f"{j}.pos": float(base + i) for i, j in enumerate(JOINTS)}


def test_fetch():
    core.arm.POSES = Path(tempfile.mkdtemp())
    fetch.HOLD_SECONDS = 0.01
    for name, base in {"home": 0, "handover": 50}.items():
        (core.arm.POSES / f"{name}.json").write_text(json.dumps(pose(base)))
    arm, stop = get_arm(mock=True), threading.Event()
    arm.halt = stop
    start = arm.get_joints()

    # no grid taught yet: refused, nothing moves
    assert "teach table" in fetch.run(arm, {"u": 0.5, "v": 0.5}, stop)["reason"]
    grid = {"n": 3, "down": [pose(10 * k) for k in range(9)], "up": [pose(10 * k + 5) for k in range(9)]}
    (core.arm.POSES / "table.json").write_text(json.dumps(grid))

    # bad or out-of-reach positions are refused before any move
    for bad in [{}, {"u": "0.5", "v": 0.5}, {"u": float("nan"), "v": 0.5}, {"u": 1.5, "v": 0.5}]:
        assert fetch.run(arm, bad, stop)["ok"] is False and arm.get_joints() == start, bad

    # a good request: closes on the centre cell of the lower layer, ends open at home
    seen = []
    write = arm._write
    arm._write = lambda joints: (seen.append(list(joints)), write(joints))
    assert fetch.run(arm, {"object": "red brick", "u": 0.5, "v": 0.5}, stop) == {"ok": True, "reason": ""}
    grasp = [40.0, 41.0, 42.0, 43.0, 44.0, fetch.GRIP_CLOSED]
    assert any(all(abs(a - b) < 1e-6 for a, b in zip(j, grasp)) for j in seen)
    assert all(abs(a - b) < 1e-6 for a, b in zip(arm.get_joints(), arm.load_pose("home")))

    # stop during the run: it reports stopped and does not go on to open the gripper at handover
    stop.set()
    assert fetch.run(arm, {"u": 0.5, "v": 0.5}, stop) == fetch.STOPPED
    print("fetch ok")


if __name__ == "__main__":
    test_fetch()
