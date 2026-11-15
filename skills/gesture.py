"""Gestures: nod, shake, fist bump, high five and a little dance, all from the taught wave_up pose.

Each one is wave_up plus joint offsets in degrees, the way wave works. No new poses to teach.
The offsets are first guesses: tune them on the real arm. `python -m tests.test_gestures_sim` replays every
gesture through the MuJoCo model and checks the limits below.

No gesture moves wrist_roll: that motor is faulty (overheats holding an error, garbles replies; steady.py).
Every move is paced so no joint is asked to pass MAX_DEG_S, whatever the taught poses are.
"""
from core.arm import HZ

NAME = "gesture"
DESCRIPTION = "Do a friendly gesture: nod, shake, fist bump, high five or a little dance"
PARAMS = {"name": "which gesture: nod, shake, fist_bump, high_five, dance, or next (default) to cycle"}

PAN, LIFT, FLEX = 0, 1, 3  # indexes in JOINTS. In the model at wave_up a bigger lift, elbow or wrist angle each
                           # moves the tip forward and down; a bigger pan moves it to the arm's right (-y)
NOD_DEG = 20       # wrist_flex down and up; a bigger wrist angle bends the hand down
SHAKE_DEG = 20     # shoulder_pan left and right
PUSH_DEG = 15      # shoulder_lift lean toward the person for the fist bump (sign unchecked on the real arm)
RECOIL_DEG = -10   # shoulder_lift lean back after the high five, the opposite way to PUSH_DEG
DANCE_PAN = 15     # shoulder_pan sway each beat
DANCE_FLEX = 15    # wrist_flex bob each beat, against the sway (it was a wrist_roll twist: that motor is faulty)
DANCE_GRIP = (75, 30)  # gripper open, then nearly closed, on alternate beats (75/30 keeps a 0.45 s beat under the cap)
CLOSED, OPEN = 7, 100  # gripper. 7, not 0: the jaws meet at about 5.3 and below that push at full effort (steady.py)
HOLD_S = 2.0       # the high five holds still this long so a person can tap it
TRAVEL_S = 1.5     # wave_up to and from home, the same time wave takes (stretched by the speed cap when needed)
MAX_DEG_S = 120.0  # no joint is asked to move faster than this (the arm carries light things; moves stay smooth)
GRIP_DEG = 1.1     # jaw degrees per gripper unit: 0..100 is the model's -10..100 degree jaw (sim.py, core/tremor.py)
STOPPED = {"ok": False, "reason": "stopped"}

# Each step: (offsets from wave_up by joint index, gripper value or None to keep wave_up's, seconds).
# Steps are 0.3 s or longer: with the motors' soft gain (16) shorter ones barely register.
GESTURES = {
    "nod": [({FLEX: NOD_DEG}, None, 0.35), ({FLEX: -NOD_DEG}, None, 0.35)] * 2,
    "shake": [({PAN: SHAKE_DEG}, None, 0.4), ({PAN: -SHAKE_DEG}, None, 0.4)] * 2,
    "fist_bump": [({}, CLOSED, 0.4), ({LIFT: PUSH_DEG}, CLOSED, 0.4), ({}, CLOSED, 0.4)],
    "high_five": [({}, OPEN, 0.3), ({}, OPEN, HOLD_S), ({LIFT: RECOIL_DEG}, OPEN, 0.3)],
    "dance": [({PAN: DANCE_PAN, FLEX: -DANCE_FLEX}, DANCE_GRIP[0], 0.45),
              ({PAN: -DANCE_PAN, FLEX: DANCE_FLEX}, DANCE_GRIP[1], 0.45)] * 2,
}
_turn = 0  # which gesture `next` plays; it starts over at nod when the dispatcher restarts


def paced(start, target, seconds):
    """seconds, stretched so no joint is asked to pass MAX_DEG_S from start to target (gripper units counted as
    jaw degrees). The extra 1/HZ covers move_joints rounding its step count down."""
    worst = max(abs(b - a) * (GRIP_DEG if i == 5 else 1.0) for i, (a, b) in enumerate(zip(start, target)))
    return max(seconds, worst / MAX_DEG_S + 1 / HZ)


def run(arm, params, stop):
    global _turn
    name = params.get("name", "next")
    if name == "next":
        name = list(GESTURES)[_turn % len(GESTURES)]
        _turn += 1
    if type(name) is not str or name not in GESTURES:
        return {"ok": False, "reason": f"name must be one of {', '.join(GESTURES)} or next"}
    home, up = arm.load_pose("home"), arm.load_pose("wave_up")
    now = arm.get_joints()
    moves = [] if all(abs(a - b) < 3 for a, b in zip(now, home)) else [(home, 2.0)]  # no pause when already home
    moves.append((up, TRAVEL_S))
    for offsets, grip, seconds in GESTURES[name]:
        target = list(up)
        for joint, deg in offsets.items():
            target[joint] += deg
        if grip is not None:
            target[5] = grip
        moves.append((target, seconds))  # the high five's hold is a move to where it already is
    moves += [(up, 0.3), (home, TRAVEL_S)]  # back to wave_up opens the gripper again
    for target, seconds in moves:
        if not arm.move_joints(target, paced(now, target, seconds)):
            return STOPPED
        now = target
    return {"ok": True, "reason": "", "gesture": name}
