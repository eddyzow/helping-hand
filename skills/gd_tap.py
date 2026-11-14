"""Tap the key under the fingertip. The seed of the Geometry Dash skill: timings come later.

Teach ONE pose by hand, fingertip resting on the key: python arm.py pose tap_key
The arm hovers above that pose and each tap comes down to it and lifts again. Tune on the real key:
    run gd_tap {"lift_deg": 3}     how high it hovers (default 3 degrees of elbow, about 1 cm)
    run gd_tap {"press_deg": -1}   stop short of the taught pose if it presses too hard; positive goes deeper
"""
NAME = "gd_tap"
DESCRIPTION = "Tap the jump key for Geometry Dash"
PARAMS = {"times": "int", "gap_s": "float", "lift_deg": "float", "press_deg": "float"}

STOPPED = {"ok": False, "reason": "stopped"}


def run(arm, params, stop):
    times, gap_s = params.get("times", 1), params.get("gap_s", 0.3)  # checked before any motion
    if type(times) is not int or not 1 <= times <= 200:
        return {"ok": False, "reason": "times must be a whole number from 1 to 200"}
    if type(gap_s) not in (int, float) or not 0 <= gap_s <= 10:
        return {"ok": False, "reason": "gap_s must be 0 to 10 seconds"}
    try:  # stays set for later taps and for geometry_dash
        arm.set_tap(params.get("lift_deg"), params.get("press_deg"))
    except ValueError as err:
        return {"ok": False, "reason": str(err)}
    if not (arm.home() and arm.move_joints(arm.hover_pose(), 1.5)):
        return STOPPED
    for _ in range(times):
        if not arm.tap(3.0) or stop.wait(gap_s):  # the wait ends at once on stop
            return STOPPED
    return {"ok": True, "reason": ""} if arm.home() else STOPPED
