"""Wave: lift to the taught wave_up pose, swing the wrist, go home.

Teach the pose once by hand: python arm.py pose wave_up
"""
NAME = "wave"
DESCRIPTION = "Wave hello to the person in front of the arm"
PARAMS = {"roll": "float, degrees to turn the hand before waving"}

SWING_DEG = 45  # wrist_roll twist to each side
SWEEP_S = 0.35  # seconds per sweep; the servo tops out near 270 degrees a second
WAVES = 4
ROLL = 0.0  # default turn of the hand; try others live with: run wave {"roll": 90}
STOPPED = {"ok": False, "reason": "stopped"}


def run(arm, params, stop):
    roll = params.get("roll", ROLL)
    if type(roll) not in (int, float) or not -180 <= roll <= 180:
        return {"ok": False, "reason": "roll must be -180 to 180 degrees"}
    up = arm.load_pose("wave_up")
    up[4] += roll
    if not (arm.home() and arm.move_joints(up, 1.5)):
        return STOPPED
    for _ in range(WAVES):
        for side in (SWING_DEG, -SWING_DEG):
            target = list(up)
            target[4] += side
            if not arm.move_joints(target, SWEEP_S):
                return STOPPED
    if not (arm.move_joints(up, 0.3) and arm.home()):
        return STOPPED
    return {"ok": True, "reason": ""}
