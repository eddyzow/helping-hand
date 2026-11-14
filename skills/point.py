"""Point at an object on the table: hover over it, dip towards it, hold, lift, go home. No gripping.

For an arm too weak to pick things up: it shows the arm knows which object was meant, and it only has
to land within a couple of centimetres. voice/route.py finds the object with the camera and passes its
position on the taught table grid, as for fetch.

    run point {"u": 0.5, "v": 0.5}      # try without a camera
    python -m skills.point              # self-check on a mock arm, no hardware

Needs the same taught grid as fetch: python arm.py teach table
UNTESTED ON HARDWARE.
"""
import json
import math
import os

import core.arm
from core.arm import JOINTS
from skills import fetch

NAME = "point"
DESCRIPTION = "Point at an object on the table without picking it up"
PARAMS = {"object": "what to point at, in the person's own words, e.g. 'the red brick'",
          "u": "filled in by voice/route.py from the camera", "v": "filled in by voice/route.py"}

POINT_GRIP = float(os.environ.get("POINT_GRIP", "0"))    # jaws closed, like a finger
POINT_DIP = float(os.environ.get("POINT_DIP", "0.5"))    # how far down from the lifted layer to dip: 1 = to the table layer
POINT_SECONDS = float(os.environ.get("POINT_SECONDS", "2"))
STOPPED = {"ok": False, "reason": "stopped"}


def run(arm, params, stop):
    # everything is checked before the first move, as in fetch
    if not (math.isfinite(POINT_GRIP) and 0 <= POINT_GRIP <= 100 and math.isfinite(POINT_DIP) and 0 <= POINT_DIP <= 1
            and math.isfinite(POINT_SECONDS) and 0 <= POINT_SECONDS <= 30):
        return {"ok": False, "reason": "POINT_GRIP must be 0 to 100, POINT_DIP 0 to 1, POINT_SECONDS 0 to 30"}
    u, v = params.get("u"), params.get("v")
    if not all(type(n) in (int, float) and math.isfinite(n) for n in (u, v)):
        return {"ok": False, "reason": "point needs numbers u and v (voice/route.py supplies them)"}
    if not (-fetch.EDGE <= u <= 1 + fetch.EDGE and -fetch.EDGE <= v <= 1 + fetch.EDGE):
        return {"ok": False, "reason": f"out of reach: u={u:.2f} v={v:.2f}"}
    table_file = core.arm.POSES / "table.json"
    if not table_file.exists():
        return {"ok": False, "reason": "No table grid. Teach it: python arm.py teach table"}
    aimed = fetch._aim(json.loads(table_file.read_text()), u, v, 0, 1 - POINT_DIP)
    if isinstance(aimed, str):
        return {"ok": False, "reason": aimed}
    above, dipped = ([pose[f"{j}.pos"] for j in JOINTS[:5]] + [POINT_GRIP] for pose in aimed)
    try:  # a bad taught pose must fail here, before the arm has moved at all
        for joints in (above, dipped):
            core.arm._checked(joints)
    except (ValueError, TypeError) as err:
        return {"ok": False, "reason": f"bad taught pose: {err}"}
    if not (arm.home() and arm.move_joints(above, 1.5) and arm.move_joints(dipped, 0.7)):
        return STOPPED
    if stop.wait(POINT_SECONDS):
        return STOPPED
    if not (arm.move_joints(above, 0.7) and arm.home()):
        return STOPPED
    return {"ok": True, "reason": ""}


if __name__ == "__main__":
    import tempfile
    import threading
    from pathlib import Path

    from core.arm import MockArm

    def pose(base):
        return {f"{j}.pos": float(base + i) for i, j in enumerate(JOINTS)}

    core.arm.POSES = Path(tempfile.mkdtemp())
    (core.arm.POSES / "home.json").write_text(json.dumps(pose(0)))
    arm, stop = MockArm(), threading.Event()
    here = arm.get_joints()
    assert not run(arm, {"u": 0.5, "v": 0.5}, stop)["ok"] and arm.get_joints() == here, "no grid: must not move"
    (core.arm.POSES / "table.json").write_text(json.dumps(
        {"n": 3, "down": [pose(10 * k) for k in range(9)], "up": [pose(10 * k + 5) for k in range(9)]}))
    for bad in ({}, {"u": 0.5}, {"u": "0.5", "v": 0.5}, {"u": float("nan"), "v": 0.5}, {"u": 3, "v": 0.5}):
        assert not run(arm, bad, stop)["ok"] and arm.get_joints() == here, f"{bad!r} must not move"
    aims, move = [], arm.move_joints
    arm.move_joints = lambda joints, seconds: aims.append(list(joints)) or move(joints, seconds)
    POINT_SECONDS = 0.0
    assert run(arm, {"object": "red brick", "u": 0.5, "v": 0.5}, stop) == {"ok": True, "reason": ""}
    over = [a for a in aims if a[0] > 30]  # the moves over the object (home is at 0)
    assert [round(a[0], 3) for a in over] == [45.0, 42.5, 45.0], "hover, dip halfway to the table layer (40), lift"
    assert all(a[5] == POINT_GRIP for a in over), "jaws closed while pointing"
    assert all(abs(a - b) < 1e-6 for a, b in zip(arm.get_joints(), arm.load_pose("home"))), "ends at home"
    stop.set()
    assert run(arm, {"u": 0.5, "v": 0.5}, stop) == STOPPED
    print("point ok")
