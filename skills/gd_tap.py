"""Tap the key under the fingertip. The seed of the Geometry Dash skill: timings come later.

Teach the pose once by hand, fingertip a millimetre or two above the key: python arm.py pose tap_up
Tune the tap with TAP_DEG_PER_MM and TAP_SECONDS (see core/arm.py).
"""
NAME = "gd_tap"
DESCRIPTION = "Tap the jump key for Geometry Dash"
PARAMS = {"times": "int", "gap_s": "float"}

STOPPED = {"ok": False, "reason": "stopped"}


def run(arm, params, stop):
    times, gap_s = params.get("times", 1), params.get("gap_s", 0.3)  # checked before any motion
    if type(times) is not int or not 1 <= times <= 200:
        return {"ok": False, "reason": "times must be a whole number from 1 to 200"}
    if type(gap_s) not in (int, float) or not 0 <= gap_s <= 10:
        return {"ok": False, "reason": "gap_s must be 0 to 10 seconds"}
    if not (arm.home() and arm.move_joints(arm.load_pose("tap_up"), 1.5)):
        return STOPPED
    for _ in range(times):
        if not arm.tap(3.0) or stop.wait(gap_s):  # the wait ends at once on stop
            return STOPPED
    return {"ok": True, "reason": ""} if arm.home() else STOPPED
