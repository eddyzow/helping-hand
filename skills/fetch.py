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
          "u": "filled in by voice/route.py from the camera", "v": "filled in by voice/route.py"}

GRIP_OPEN = float(os.environ.get("GRIP_OPEN", "60"))      # gripper value when open, 0 to 100
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

    moves = [
        (_joints(up, GRIP_OPEN), 1.5),
        (_joints(down, GRIP_OPEN), 1.0),
        (_joints(down, GRIP_CLOSED), 0.6),
        (_joints(up, GRIP_CLOSED), 1.0),
        (handover + [GRIP_CLOSED], 2.0),
    ]
    if not arm.home():
        return STOPPED
    for joints, seconds in moves:
        if not arm.move_joints(joints, seconds):
            return STOPPED
    if stop.wait(HOLD_SECONDS):  # the person takes it; a stop here keeps the grip
        return STOPPED
    if not (arm.move_joints(handover + [GRIP_OPEN], 0.6) and arm.home()):
        return STOPPED
    return {"ok": True, "reason": ""}
