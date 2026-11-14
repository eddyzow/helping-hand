"""Tap the key under the fingertip. The seed of the Geometry Dash skill: timings come later.

Teach the pose once by hand, fingertip a millimetre or two above the key: python arm.py pose tap_up
Tune the tap with TAP_DEG_PER_MM and TAP_SECONDS (see core/arm.py).
"""
NAME = "gd_tap"
DESCRIPTION = "Tap the jump key for Geometry Dash"
PARAMS = {"times": "int", "gap_s": "float"}

STOPPED = {"ok": False, "reason": "stopped"}


def run(arm, params, stop):
    if not (arm.home() and arm.move_joints(arm.load_pose("tap_up"), 1.5)):
        return STOPPED
    for _ in range(int(params.get("times", 1))):
        if not arm.tap(3.0) or stop.wait(min(float(params.get("gap_s", 0.3)), 0.5)):
            return STOPPED
    return {"ok": True, "reason": ""} if arm.home() else STOPPED
