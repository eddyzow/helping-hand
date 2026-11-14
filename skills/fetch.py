"""Fetch: pick up the object at a spot on the taught table grid and hand it over.

The dispatcher has no camera (it runs in WSL), so voice/route.py finds the object and passes
its grid position: u left to right, v far to near, both 0 to 1.

Teach once by hand:
    python arm.py pose handover     # where the arm holds the object out
    python arm.py teach table       # 3x3 grid: open gripper on the table, then lifted clear
    python arm.py check table       # slow pass between the taught points; watch for dips
Try without a camera:
    run fetch {"u": 0.5, "v": 0.5}
"""
import json
import math
import os

import core.arm
from core.arm import JOINTS
from grid import interpolate

NAME = "fetch"
DESCRIPTION = "Pick up an object from the table and hand it to the person"
PARAMS = {"object": "what to pick up, in the person's own words, e.g. 'the red brick'",
          "u": "filled in by voice/route.py from the camera", "v": "filled in by voice/route.py",
          "to_u": "optional: where to put it down instead of handing it over", "to_v": "optional"}

GRIP_OPEN = float(os.environ.get("GRIP_OPEN", "100"))      # fully open: at 60 the simulated jaw came down on top of a 32 mm brick
GRIP_CLOSED = float(os.environ.get("GRIP_CLOSED", "5"))   # gripper value when squeezing
HOLD_SECONDS = float(os.environ.get("HOLD_SECONDS", "3"))  # how long it holds the object out
EDGE = 0.05  # how far outside the taught grid a target may be
STOPPED = {"ok": False, "reason": "stopped"}


def _joints(pose: dict, grip: float) -> list[float]:
    return [pose[f"{j}.pos"] for j in JOINTS[:5]] + [grip]


def run(arm, params, stop):
    # everything is checked before the first move
    u, v = params.get("u"), params.get("v")
    if not all(type(n) in (int, float) and math.isfinite(n) for n in (u, v)):
        return {"ok": False, "reason": "fetch needs numbers u and v (voice/route.py supplies them)"}
    if not (-EDGE <= u <= 1 + EDGE and -EDGE <= v <= 1 + EDGE):
        return {"ok": False, "reason": f"out of reach: u={u:.2f} v={v:.2f}"}
    table_file = core.arm.POSES / "table.json"  # looked up now, so tests can point it elsewhere
    if not table_file.exists():
        return {"ok": False, "reason": "No table grid. Teach it: python arm.py teach table"}
    table = json.loads(table_file.read_text())
    up = interpolate(table["up"], table["n"], u, v)
    down = interpolate(table["down"], table["n"], u, v)
    handover = arm.load_pose("handover")[:5]
    to_u, to_v = params.get("to_u"), params.get("to_v")
    placing = to_u is not None or to_v is not None
    if placing and not all(type(n) in (int, float) and math.isfinite(n) and -EDGE <= n <= 1 + EDGE
                           for n in (to_u, to_v)):
        return {"ok": False, "reason": "the place to put it down is out of reach"}

    moves = [
        (_joints(up, GRIP_OPEN), 1.5),
        (_joints(down, GRIP_OPEN), 1.0),
        (_joints(down, GRIP_CLOSED), 0.6),
        (_joints(up, GRIP_CLOSED), 1.0),
    ]
    if placing:  # carry it over, set it down, let go, lift clear
        above = interpolate(table["up"], table["n"], to_u, to_v)
        on_table = interpolate(table["down"], table["n"], to_u, to_v)
        after = [(_joints(on_table, GRIP_OPEN), 0.6), (_joints(above, GRIP_OPEN), 1.0)]
        moves += [(_joints(above, GRIP_CLOSED), 2.0), (_joints(on_table, GRIP_CLOSED), 1.0)]
    else:
        after = [(handover + [GRIP_OPEN], 0.6)]
        moves += [(handover + [GRIP_CLOSED], 2.0)]
    try:  # a bad taught pose must fail here, before the arm has moved at all
        for joints, _ in moves + after:
            core.arm._checked(joints)
    except (ValueError, TypeError) as err:
        return {"ok": False, "reason": f"bad taught pose: {err}"}
    if not arm.home():
        return STOPPED
    for joints, seconds in moves:
        if not arm.move_joints(joints, seconds):
            return STOPPED
    if not placing and stop.wait(HOLD_SECONDS):  # the person takes it; a stop here keeps the grip
        return STOPPED
    for joints, seconds in after:
        if not arm.move_joints(joints, seconds):
            return STOPPED
    if not arm.home():
        return STOPPED
    return {"ok": True, "reason": ""}
