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
          "to_u": "optional: where to put it down instead of handing it over", "to_v": "optional",
          "lift": "optional: 0 to 1, how far above the table to grasp it (when it sits on top of something)",
          "to_lift": "optional: 0 to 1, how far above the table to let go (for putting it on top of something)",
          "hold": "optional: seconds to hold it up before letting go",
          "turn": "optional: degrees to turn the jaws to match the object, from pick.jaw_turn",
          "to_turn": "optional: degrees to turn the jaws when putting it down, to line it up with what it goes on"}

GRIP_OPEN = float(os.environ.get("GRIP_OPEN", "100"))      # fully open: at 60 the simulated jaw came down on top of a 32 mm brick
GRIP_CLOSED = float(os.environ.get("GRIP_CLOSED", "5"))   # gripper value when squeezing
HOLD_SECONDS = float(os.environ.get("HOLD_SECONDS", "3"))  # how long it holds the object out
ROLL_SIGN = float(os.environ.get("ROLL_SIGN", "-1"))      # which way wrist_roll turns the jaws; flip if it turns the wrong way
# How far wrist_roll can go, in degrees. Past this the joint stops short and the jaws meet the brick at
# an angle (one on a face, one on a corner), which drops it. Set from the real arm's calibration.
ROLL_MIN = float(os.environ.get("ROLL_MIN", "-150"))
ROLL_MAX = float(os.environ.get("ROLL_MAX", "150"))
# Turning the wrist swings the jaws around its axis, so the grasp point moves. To cancel that, give the
# distance from that axis to the point between the jaws (along the jaws; measure by turning the wrist a
# quarter turn and seeing how far the tip moves) and the taught grid's real size. 0 = no correction.
JAW_ARM_MM = float(os.environ.get("JAW_ARM_MM", "0"))
GRID_WIDTH_MM = float(os.environ.get("GRID_WIDTH_MM", "0"))
GRID_DEPTH_MM = float(os.environ.get("GRID_DEPTH_MM", "0"))
# Where a gripped brick ends up relative to where the jaws were centred, in mm: closing the one moving jaw
# pushes it towards the fixed jaw. "across,along": across = to the arm's right with the jaws as taught,
# along = towards the arm. Used when putting it down, so it lands on the spot. Measure: grip a brick, set it
# down with no turn, and see how far it lands from where you aimed. Needs the grid's size too. 0,0 = off.
HELD_SHIFT_MM = tuple(float(n) for n in os.environ.get("HELD_SHIFT_MM", "0,0").split(","))
EDGE = 0.05  # how far outside the taught grid a target may be
# After putting something down the arm rises this far before it leaves, as a multiple of the gap between the
# taught table layer and lifted layer. 1 = the lifted layer. A two-brick stack is nearly as tall as that
# layer, and on the way home the open jaw swept through the top of it.
EXIT_LIFT = float(os.environ.get("EXIT_LIFT", "1.5"))
STOPPED = {"ok": False, "reason": "stopped"}


def _joints(pose: dict, grip: float) -> list[float]:
    return [pose[f"{j}.pos"] for j in JOINTS[:5]] + [grip]


def _aim(table, u, v, turn, lift, holding=False):
    """The lifted and lowered poses over grid point u, v, with the jaws turned `turn` degrees and the
    lowered pose `lift` of the way up to the lifted one (0 = on the table, for stacks more).
    With `holding`, u and v are where the held object should land, not where the jaws go.
    Returns (up, down), or a sentence saying why the arm cannot do it."""
    if turn:  # jaws closing one way or the opposite way are the same grasp: take the turn the wrist can reach
        taught = [interpolate(table[layer], table["n"], u, v)["wrist_roll.pos"] for layer in ("up", "down")]
        fits = [t for t in (turn, turn - math.copysign(180, turn))
                if all(ROLL_MIN <= roll + ROLL_SIGN * t <= ROLL_MAX for roll in taught)]
        if not fits:
            return "the wrist cannot turn far enough to line up with it"
        turn = fits[0]
    swing = math.radians(turn)
    if holding and any(HELD_SHIFT_MM) and GRID_WIDTH_MM > 0 and GRID_DEPTH_MM > 0:  # the shift turns with the jaws
        across, along = HELD_SHIFT_MM
        u -= (across * math.cos(swing) - along * math.sin(swing)) / GRID_WIDTH_MM
        v -= (across * math.sin(swing) + along * math.cos(swing)) / GRID_DEPTH_MM
    if turn and JAW_ARM_MM and GRID_WIDTH_MM > 0 and GRID_DEPTH_MM > 0:
        u -= (math.cos(swing) - 1) * JAW_ARM_MM / GRID_WIDTH_MM
        v -= math.sin(swing) * JAW_ARM_MM / GRID_DEPTH_MM
    if swing or holding:
        if not (math.isfinite(u) and math.isfinite(v) and -EDGE <= u <= 1 + EDGE and -EDGE <= v <= 1 + EDGE):
            return f"out of reach once the wrist is turned: u={u:.2f} v={v:.2f}"
    up = interpolate(table["up"], table["n"], u, v)
    down = interpolate(table["down"], table["n"], u, v)
    for pose in (up, down):  # the wrist turns before the jaws come down, and stays turned while lifting
        pose["wrist_roll.pos"] += ROLL_SIGN * turn
        if turn and not ROLL_MIN <= pose["wrist_roll.pos"] <= ROLL_MAX:
            return "the wrist cannot turn far enough to line up with it"
    return up, {joint: low + lift * (up[joint] - low) for joint, low in down.items()}


def run(arm, params, stop):
    # everything is checked before the first move, settings included: they come from the environment
    if not all(math.isfinite(g) and 0 <= g <= 100 for g in (GRIP_OPEN, GRIP_CLOSED)):
        return {"ok": False, "reason": "GRIP_OPEN and GRIP_CLOSED must be numbers from 0 to 100"}
    if not (math.isfinite(HOLD_SECONDS) and HOLD_SECONDS >= 0):
        return {"ok": False, "reason": "HOLD_SECONDS must be a number, 0 or more"}
    u, v = params.get("u"), params.get("v")
    if not all(type(n) in (int, float) and math.isfinite(n) for n in (u, v)):
        return {"ok": False, "reason": "fetch needs numbers u and v (voice/route.py supplies them)"}
    if not (-EDGE <= u <= 1 + EDGE and -EDGE <= v <= 1 + EDGE):
        return {"ok": False, "reason": f"out of reach: u={u:.2f} v={v:.2f}"}
    table_file = core.arm.POSES / "table.json"  # looked up now, so tests can point it elsewhere
    if not table_file.exists():
        return {"ok": False, "reason": "No table grid. Teach it: python arm.py teach table"}
    turn, to_turn = params.get("turn", 0), params.get("to_turn", 0)
    if not all(type(n) in (int, float) and math.isfinite(n) and -90 <= n <= 90 for n in (turn, to_turn)):
        return {"ok": False, "reason": "turn and to_turn must be numbers of degrees from -90 to 90"}
    grasp_lift, lift, hold = params.get("lift", 0), params.get("to_lift", 0), params.get("hold", HOLD_SECONDS)
    if not all(type(n) in (int, float) and math.isfinite(n) and 0 <= n <= 1 for n in (grasp_lift, lift)):
        return {"ok": False, "reason": "lift and to_lift must be numbers from 0 to 1"}
    if not (type(hold) in (int, float) and math.isfinite(hold) and 0 <= hold <= 30):
        return {"ok": False, "reason": "hold must be a number of seconds from 0 to 30"}
    to_u, to_v = params.get("to_u"), params.get("to_v")
    placing = to_u is not None or to_v is not None
    if placing and not all(type(n) in (int, float) and math.isfinite(n) and -EDGE <= n <= 1 + EDGE
                           for n in (to_u, to_v)):
        return {"ok": False, "reason": "the place to put it down is out of reach"}
    table = json.loads(table_file.read_text())
    aimed = [_aim(table, u, v, turn, grasp_lift)] + ([_aim(table, to_u, to_v, to_turn, lift, holding=True), _aim(table, to_u, to_v, to_turn, lift),
                                                  _aim(table, to_u, to_v, to_turn, EXIT_LIFT)] if placing else [])
    for problem in aimed:
        if isinstance(problem, str):
            return {"ok": False, "reason": problem}
    up, down = aimed[0]
    handover = arm.load_pose("handover")[:5]

    moves = [
        (_joints(up, GRIP_OPEN), 1.5),
        (_joints(down, GRIP_OPEN), 1.0),
        (_joints(down, GRIP_CLOSED), 0.6),
        (_joints(up, GRIP_CLOSED), 1.0),
    ]
    if placing:  # carry it over, set it down, let go, lift clear
        above, on_table = aimed[1]
        clear_up, clear = aimed[2]  # jaws centred on the piece: the fixed jaw backs off it before the arm lifts,
        after = [(_joints(on_table, GRIP_OPEN), 0.6), (_joints(clear, GRIP_OPEN), 0.4),  # or it drags it off a stack
                 (_joints(clear_up, GRIP_OPEN), 1.0), (_joints(aimed[3][1], GRIP_OPEN), 0.6)]
        moves += [(_joints(above, GRIP_CLOSED), 2.0), (_joints(on_table, GRIP_CLOSED), 1.0)]
    else:
        after = [(handover + [GRIP_OPEN], 0.6)]
        moves += [(handover + [GRIP_CLOSED], 2.0)]
    if placing:  # leave with the jaws still open: closing them on the way out swept the moving jaw through the stack
        after += [(arm.load_pose("home")[:5] + [GRIP_OPEN], 1.5)]
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
    if not placing and stop.wait(hold):  # the person takes it; a stop here keeps the grip
        return STOPPED
    for joints, seconds in after:
        if not arm.move_joints(joints, seconds):
            return STOPPED
    if not arm.home():
        return STOPPED
    return {"ok": True, "reason": ""}
