"""Gestures: nod, shake, fist bump, high five and a little dance, all from the taught wave_up pose.

Each one is wave_up plus joint offsets in degrees, the way wave works. No new poses to teach.
The offsets are first guesses: tune them on the real arm.
"""
NAME = "gesture"
DESCRIPTION = "Do a friendly gesture: nod, shake, fist bump, high five or a little dance"
PARAMS = {"name": "which gesture: nod, shake, fist_bump, high_five, dance, or next (default) to cycle"}

PAN, LIFT, FLEX, ROLL = 0, 1, 3, 4  # indexes in JOINTS
NOD_DEG = 20       # wrist_flex down and up; a bigger wrist angle bends the hand down
SHAKE_DEG = 20     # shoulder_pan left and right
PUSH_DEG = 15      # shoulder_lift lean toward the person for the fist bump (sign unchecked on the real arm)
RECOIL_DEG = -10   # shoulder_lift lean back after the high five, the opposite way to PUSH_DEG
DANCE_PAN = 15     # shoulder_pan sway each beat
DANCE_ROLL = 30    # wrist_roll twist each beat
DANCE_GRIP = (80, 20)  # gripper open, then nearly closed, on alternate beats
CLOSED, OPEN = 0, 100  # gripper
HOLD_S = 2.0       # the high five holds still this long so a person can tap it
TRAVEL_S = 1.5     # wave_up to and from home, the same time wave takes
STOPPED = {"ok": False, "reason": "stopped"}

# Each step: (offsets from wave_up by joint index, gripper value or None to keep wave_up's, seconds).
GESTURES = {
    "nod": [({FLEX: NOD_DEG}, None, 0.35), ({FLEX: -NOD_DEG}, None, 0.35)] * 2,
    "shake": [({PAN: SHAKE_DEG}, None, 0.4), ({PAN: -SHAKE_DEG}, None, 0.4)] * 2,
    "fist_bump": [({}, CLOSED, 0.4), ({LIFT: PUSH_DEG}, CLOSED, 0.4), ({}, CLOSED, 0.4)],
    "high_five": [({}, OPEN, 0.3), ({}, OPEN, HOLD_S), ({LIFT: RECOIL_DEG}, OPEN, 0.3)],
    "dance": [({PAN: DANCE_PAN, ROLL: DANCE_ROLL}, DANCE_GRIP[0], 0.45),
              ({PAN: -DANCE_PAN, ROLL: -DANCE_ROLL}, DANCE_GRIP[1], 0.45)] * 2,
}
_turn = 0  # which gesture `next` plays; it starts over at nod when the dispatcher restarts


def run(arm, params, stop):
    global _turn
    name = params.get("name", "next")
    if name == "next":
        name = list(GESTURES)[_turn % len(GESTURES)]
        _turn += 1
    if type(name) is not str or name not in GESTURES:
        return {"ok": False, "reason": f"name must be one of {', '.join(GESTURES)} or next"}
    up = arm.load_pose("wave_up")
    at_home = all(abs(a - b) < 3 for a, b in zip(arm.get_joints(), arm.load_pose("home")))
    if not ((at_home or arm.home()) and arm.move_joints(up, TRAVEL_S)):  # no pause when already home
        return STOPPED
    for offsets, grip, seconds in GESTURES[name]:
        target = list(up)
        for joint, deg in offsets.items():
            target[joint] += deg
        if grip is not None:
            target[5] = grip
        if not arm.move_joints(target, seconds):  # the high five's hold is a move to where it already is
            return STOPPED
    if not (arm.move_joints(up, 0.3) and arm.home(TRAVEL_S)):  # back to wave_up opens the gripper again
        return STOPPED
    return {"ok": True, "reason": "", "gesture": name}
