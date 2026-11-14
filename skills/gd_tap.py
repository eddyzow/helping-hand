"""Tap the key under the fingertip. The seed of the Geometry Dash skill: timings come later.

The arm holds still and only the gripper jaw taps. Teach ONE pose by hand: python arm.py pose tap_key
    gripper lying level just above the keypad, turned so the moving jaw is underneath,
    jaw opened down until its tip rests on the jump key (touching, not pushing).
The jaw waits lifted off the key and each tap opens it back down to the taught spot. Tune on the real key:
    run gd_tap {"press": -2}   lighter: stop 2 units short of the taught spot (positive presses further)
    run gd_tap {"lift": 8}     how far the jaw lifts between taps (default 8 units, about 1 cm at the tip)
"""
NAME = "gd_tap"
DESCRIPTION = "Tap the jump key for Geometry Dash"
PARAMS = {"times": "int", "gap_s": "float", "lift": "float", "press": "float"}

STOPPED = {"ok": False, "reason": "stopped"}


def run(arm, params, stop):
    times, gap_s = params.get("times", 1), params.get("gap_s", 0.3)  # checked before any motion
    if type(times) is not int or not 1 <= times <= 200:
        return {"ok": False, "reason": "times must be a whole number from 1 to 200"}
    if type(gap_s) not in (int, float) or not 0 <= gap_s <= 10:
        return {"ok": False, "reason": "gap_s must be 0 to 10 seconds"}
    try:  # stays set for later taps and for geometry_dash
        arm.set_tap(params.get("lift"), params.get("press"))
    except ValueError as err:
        return {"ok": False, "reason": str(err)}
    if not arm.to_key():
        return STOPPED
    for _ in range(times):
        if not arm.tap(3.0) or stop.wait(gap_s):  # the wait ends at once on stop
            return STOPPED
    return {"ok": True, "reason": ""} if arm.from_key() else STOPPED
