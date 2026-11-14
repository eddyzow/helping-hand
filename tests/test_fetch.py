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

    # a taught grid holding a NaN is refused before home: nothing moves
    broken = json.loads(json.dumps(grid))
    broken["down"][4]["elbow_flex.pos"] = float("nan")
    (core.arm.POSES / "table.json").write_text(json.dumps(broken))
    assert "bad taught pose" in fetch.run(arm, {"u": 0.5, "v": 0.5}, stop)["reason"] and arm.get_joints() == start
    (core.arm.POSES / "table.json").write_text(json.dumps(grid))

    # a good request: closes on the centre cell of the lower layer, ends open at home
    seen = []
    write = arm._write
    arm._write = lambda joints: (seen.append(list(joints)), write(joints))
    assert fetch.run(arm, {"object": "red brick", "u": 0.5, "v": 0.5}, stop) == {"ok": True, "reason": ""}
    grasp = [40.0, 41.0, 42.0, 43.0, 44.0, fetch.GRIP_CLOSED]
    assert any(all(abs(a - b) < 1e-6 for a, b in zip(j, grasp)) for j in seen)
    assert all(abs(a - b) < 1e-6 for a, b in zip(arm.get_joints(), arm.load_pose("home")))

    # put it down somewhere instead of handing it over: opens on the far-right cell, never visits handover
    seen.clear()
    assert fetch.run(arm, {"u": 0.5, "v": 0.5, "to_u": 1.0, "to_v": 0.0}, stop) == {"ok": True, "reason": ""}
    set_down = [20.0, 21.0, 22.0, 23.0, 24.0, fetch.GRIP_OPEN]
    assert any(all(abs(a - b) < 1e-6 for a, b in zip(j, set_down)) for j in seen)
    assert not any(abs(j[0] - 50.0) < 1e-6 for j in seen)
    # a put-down spot off the grid is refused before any move
    here = arm.get_joints()
    assert fetch.run(arm, {"u": 0.5, "v": 0.5, "to_u": 3.0, "to_v": 0.0}, stop)["ok"] is False and arm.get_joints() == here

    # "on top of": it lets go partway between the table layer and the lifted layer; bad values are refused
    seen.clear()
    assert fetch.run(arm, {"u": 0.5, "v": 0.5, "to_u": 0.0, "to_v": 0.0, "to_lift": 0.5}, stop)["ok"]
    assert any(abs(j[0] - 2.5) < 1e-6 for j in seen), "halfway between the corner's down (0) and up (5) poses"
    seen.clear()  # picking it off a stack: it closes partway up, at 42.5 between down (40) and up (45)
    assert fetch.run(arm, {"u": 0.5, "v": 0.5, "lift": 0.5}, stop)["ok"]
    assert any(abs(j[0] - 42.5) < 1e-6 and abs(j[5] - fetch.GRIP_CLOSED) < 1e-6 for j in seen)
    here = arm.get_joints()
    for bad in [{"to_u": 0.0, "to_v": 0.0, "to_lift": 2}, {"lift": -0.1}, {"lift": "0.5"}, {"hold": -1}, {"hold": "3"}]:
        assert fetch.run(arm, {"u": 0.5, "v": 0.5, **bad}, stop)["ok"] is False and arm.get_joints() == here, bad

    # settings out of range are refused before any move
    here = arm.get_joints()
    for name, bad in [("GRIP_OPEN", 101.0), ("GRIP_CLOSED", -1.0), ("HOLD_SECONDS", -1.0), ("HOLD_SECONDS", float("nan"))]:
        good = getattr(fetch, name)
        setattr(fetch, name, bad)
        assert fetch.run(arm, {"u": 0.5, "v": 0.5}, stop)["ok"] is False and arm.get_joints() == here, name
        setattr(fetch, name, good)
    # a wrist turn that would carry the corrected target off the grid is refused, not clamped
    fetch.JAW_ARM_MM, fetch.GRID_WIDTH_MM, fetch.GRID_DEPTH_MM = 20.0, 100.0, 100.0
    assert "wrist" in fetch.run(arm, {"u": 1.0, "v": 0.5, "turn": 90}, stop)["reason"] and arm.get_joints() == here
    fetch.JAW_ARM_MM = 0.0
    # a turn past the wrist's limit goes the other way round (same grasp); with no way round it is refused
    fetch.ROLL_MIN, fetch.ROLL_MAX = -20.0, 150.0
    rolls = []
    move = arm.move_joints
    arm.move_joints = lambda joints, seconds: rolls.append(joints[4]) or move(joints, seconds)
    # the taught roll at the centre is 44 on the table: a turn of 80 means 44 - 80 = -36, past the limit,
    # so it goes 100 the other way, to 144
    assert fetch.run(arm, {"u": 0.5, "v": 0.5, "turn": 80}, stop)["ok"]
    assert all(-20 <= r <= 150 for r in rolls) and 144.0 in rolls, rolls
    fetch.ROLL_MAX, here = 100.0, arm.get_joints()
    assert "wrist" in fetch.run(arm, {"u": 0.5, "v": 0.5, "turn": 80}, stop)["reason"] and arm.get_joints() == here
    arm.move_joints, fetch.ROLL_MIN, fetch.ROLL_MAX = move, -150.0, 150.0

    # stop during the run: it reports stopped and does not go on to open the gripper at handover
    stop.set()
    assert fetch.run(arm, {"u": 0.5, "v": 0.5}, stop) == fetch.STOPPED
    print("fetch ok")


if __name__ == "__main__":
    test_fetch()
