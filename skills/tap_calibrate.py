"""Find the jump key by touch, so nobody has to teach an exact pose.

Before: teach a ROUGH pose with the closed gripper tip pointing down about 1 cm above the jump key
(python arm.py pose tap_key), tape the keypad down, and have keypad/listen.py running on Windows.

    run tap_calibrate

The arm goes above the key and lowers the tip very slowly. The moment the keypad reports the jump
key, it stops: that is the lightest press that works. It then lifts slowly until the key lets go,
saves both (poses/tap_key.json and poses/tap_tune.json) and does three test taps.
If the tip rises instead of lowering it gives up after max_travel and changes nothing.
"""
import json
import time

NAME = "tap_calibrate"
DESCRIPTION = "Find the jump key by touch and save the lightest press that registers"
PARAMS = {"max_travel": "float, how far it may lower before giving up"}

STEP = 0.1        # TAP_JOINT units per step (0.1 degree of elbow is about 0.3 mm at the tip)
STEP_S = 0.05     # so about 6 mm a second
PAST = 0.15       # press this much past the first registration, so every tap registers
CLEAR = 2.5       # wait this much above the point where the key let go; 0.5 left the key reading as held
STOPPED = {"ok": False, "reason": "stopped"}


def run(arm, params, stop):
    import core.arm
    from core import key_down
    from core.arm import JOINTS, POSES, TAP_JOINT

    max_travel = params.get("max_travel", 8.0)
    if type(max_travel) not in (int, float) or not 0.5 <= max_travel <= 20:
        return {"ok": False, "reason": "max_travel must be 0.5 to 20"}
    if key_down.is_set():
        return {"ok": False, "reason": "the jump key already reads as pressed; lift the tip off it first"}

    rough = arm.load_pose("tap_key")
    if not arm.to_key():
        return STOPPED

    start = arm.hover_pose()[TAP_JOINT]
    lowest = rough[TAP_JOINT] + max_travel  # never commanded below this, whatever the hover height was

    def creep(value, step, until_pressed):
        """Move TAP_JOINT in small steps until the key reads pressed (or released). None = not found.
        The next target is checked against the travel limits, and stop is checked, before every write."""
        while key_down.is_set() != until_pressed:
            value += step
            if stop.is_set() or not start - 1e-9 <= value <= lowest + 1e-9:
                return None
            pose = list(rough)
            pose[TAP_JOINT] = value
            arm._write(core.arm._checked(pose))
            stop.wait(STEP_S)
        return value

    pressed_at = creep(start, STEP, True)
    if stop.is_set():
        return STOPPED
    if pressed_at is None:
        arm.from_key()
        return {"ok": False, "reason": f"lowered {max_travel} past the taught pose and the key never registered. "
                "Is keypad/listen.py running? Is the tip over the jump key?"}
    released_at = creep(pressed_at, -STEP, False)
    if released_at is None:
        return STOPPED if stop.is_set() else {"ok": False, "reason": "the key never released while lifting"}

    key = list(rough)
    key[TAP_JOINT] = min(pressed_at + PAST, lowest)  # the saved press obeys the same travel limit
    lift = key[TAP_JOINT] - released_at + CLEAR
    hover = list(key)
    hover[TAP_JOINT] -= lift
    before = (arm.lift, arm.press_extra)
    # Keep the press depth that was in use: calibration finds WHERE the key is, not how firmly to
    # play it (resetting it to 0 made 1 press in 25 stall about 40 ms at the trigger point, 14 Nov).
    # But never shallower than the point that registers, and never past the travel limit of this run.
    press = max(0.0, min(before[1], lowest - key[TAP_JOINT]))
    pressed = list(key)
    pressed[TAP_JOINT] += press  # the pose a tap will really go to; the test taps below use it
    try:  # check the measurement first; only a valid, verified one replaces the saved calibration
        arm.set_tap(lift, press)
        core.arm._checked(key), core.arm._checked(hover), core.arm._checked(pressed)
    except ValueError as err:
        arm.from_key()
        return {"ok": False, "reason": f"measured an odd stroke ({err}); the saved calibration is unchanged"}

    def reaches(pose, want_pressed):
        """Command one pose and wait up to half a second for the key to read as wanted."""
        if stop.is_set():
            return False
        arm._write(pose)
        deadline = time.perf_counter() + 0.5
        while key_down.is_set() != want_pressed and time.perf_counter() < deadline:
            if stop.wait(0.01):
                return False
        return key_down.is_set() == want_pressed

    # three test taps with the new numbers; every press must register AND every lift must release
    taps = 0
    released = reaches(hover, False)
    while released and taps < 3 and reaches(pressed, True):
        taps += 1
        released = reaches(hover, False)
    if stop.is_set():
        arm.set_tap(*before)
        return STOPPED
    if taps < 3 or not released:
        arm.set_tap(*before)
        arm.from_key()
        why = "the key stayed down after a lift" if not released else f"only {taps} of 3 test taps registered"
        return {"ok": False, "reason": f"{why}; the saved calibration is unchanged"}

    (POSES / "tap_key.json").write_text(json.dumps({f"{j}.pos": v for j, v in zip(JOINTS, key)}, indent=1))
    (POSES / "tap_tune.json").write_text(json.dumps({"lift": lift, "press": press}))
    arm._poses.pop("tap_key", None)  # read the new pose from the file next time
    if not arm.from_key():
        return STOPPED
    return {"ok": True, "reason": f"key registers at {pressed_at:.2f}, releases at {released_at:.2f}, "
            f"lift {lift:.2f}, press {press:.2f}; 3 of 3 test taps registered and released"}
