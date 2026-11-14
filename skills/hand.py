"""A third hand: take what a person puts in the claw, hold it, and give it back.

    run hand {"do": "take"}    # reach out, open, wait, close on what was put between the fingers, come home holding it
    run hand {"do": "give"}    # reach out, let go, come home
    run hand {"do": "drop"}    # open the claw where the arm is

No camera and no computed positions: the person brings the object to the claw, at the taught
`handover` pose. Whether the claw holds something is read from the claw itself: closed on nothing
it reads about 5, on a Duplo brick about 16 (measured 14 Nov).
"""
NAME = "hand"
DESCRIPTION = "Take an object a person puts in the claw, hold it, or give it back"
PARAMS = {"do": "take, give or drop",
          "wait": "float, seconds the open claw waits for the object before closing (take only, default 3)"}

OPEN, CLOSED = 60.0, 0.0   # gripper: wide enough for a brick or a marker; closed as far as it goes
HOLDING = 9.0              # a claw that stops above this has something in it
REACH_S, CLOSE_S = 2.5, 1.5
STOPPED = {"ok": False, "reason": "stopped"}


def run(arm, params, stop):
    do = params.get("do")
    wait = params.get("wait", 3.0)
    if do not in ("take", "give", "drop"):
        return {"ok": False, "reason": "do must be take, give or drop"}
    if type(wait) not in (int, float) or not 0 <= wait <= 20:
        return {"ok": False, "reason": "wait must be 0 to 20 seconds"}

    def grip(pose, value):
        pose = list(pose)
        pose[5] = value
        return pose

    if do == "drop":
        if not arm.move_joints(grip(arm.get_joints(), OPEN), 0.6):
            return STOPPED
        return {"ok": True, "reason": "", "holding": False}

    out = arm.load_pose("handover")
    home = arm.load_pose("home")
    if do == "take":
        if not arm.move_joints(grip(out, OPEN), REACH_S) or stop.wait(wait):
            return STOPPED
        if not arm.move_joints(grip(out, CLOSED), CLOSE_S) or stop.wait(0.4):
            return STOPPED
        holding = arm.get_joints()[5] > HOLDING
        if not holding:  # nothing there: do not carry an empty claw home as if it held something
            if not arm.move_joints(grip(out, OPEN), 0.6) or not arm.move_joints(home, REACH_S):
                return STOPPED
            return {"ok": False, "reason": "nothing was in the claw", "holding": False}
        if not arm.move_joints(grip(home, CLOSED), REACH_S):
            return STOPPED
        return {"ok": True, "reason": "", "holding": True}

    # give: carry it out with the same squeeze, pause so a hand can get under it, let go, come home
    held = arm.get_joints()[5] > HOLDING
    if not arm.move_joints(grip(out, CLOSED), REACH_S) or stop.wait(1.0):
        return STOPPED
    if not arm.move_joints(grip(out, OPEN), 0.6) or stop.wait(0.8):
        return STOPPED
    if not arm.move_joints(home, REACH_S):
        return STOPPED
    return {"ok": True, "reason": "" if held else "the claw was empty", "holding": False}
