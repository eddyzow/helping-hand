"""Wave: lift to the taught wave_up pose, swing the wrist, go home.

Teach the pose once by hand: python arm.py pose wave_up
"""
NAME = "wave"
DESCRIPTION = "Wave hello to the person in front of the arm"
PARAMS = {}

SWING_DEG = 45  # wrist_roll twist to each side
SWEEP_S = 0.35  # seconds per sweep; the servo tops out near 270 degrees a second
WAVES = 4
STOPPED = {"ok": False, "reason": "stopped"}


def run(arm, params, stop):
    up = arm.load_pose("wave_up")
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
