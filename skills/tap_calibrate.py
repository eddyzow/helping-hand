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
CLEAR = 0.5       # wait this much above the point where the key let go
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

    def creep(value, step, until_pressed, limit):
        """Move TAP_JOINT in small steps until the key reads pressed (or released). None = not found."""
        while key_down.is_set() != until_pressed:
            if abs(value - rough[TAP_JOINT]) > limit:
                return None
            value += step
            pose = list(rough)
            pose[TAP_JOINT] = value
            arm._write(core.arm._checked(pose))
            if stop.wait(STEP_S):
                return None
        return value

    start = arm.hover_pose()[TAP_JOINT]
    pressed_at = creep(start, STEP, True, max_travel + arm.lift)
    if stop.is_set():
        return STOPPED
    if pressed_at is None:
        arm.from_key()
        return {"ok": False, "reason": f"lowered {max_travel} past the taught pose and the key never registered. "
                "Is keypad/listen.py running? Is the tip over the jump key?"}
    released_at = creep(pressed_at, -STEP, False, max_travel + arm.lift)
    if released_at is None:
        return STOPPED if stop.is_set() else {"ok": False, "reason": "the key never released while lifting"}

    key = list(rough)
    key[TAP_JOINT] = pressed_at + PAST
    lift = abs(key[TAP_JOINT] - released_at) + CLEAR
    (POSES / "tap_key.json").write_text(json.dumps({f"{j}.pos": v for j, v in zip(JOINTS, key)}, indent=1))
    (POSES / "tap_tune.json").write_text(json.dumps({"lift": lift, "press": 0.0}))
    try:
        arm.set_tap(lift, 0.0)
    except ValueError as err:
        return {"ok": False, "reason": f"measured an odd stroke ({err}); nothing changed for this session"}

    seen = 0
    if not arm.release():
        return STOPPED
    for _ in range(3):
        if stop.wait(0.4) or not arm.press():
            return STOPPED
        deadline = time.perf_counter() + 0.5
        while time.perf_counter() < deadline and not key_down.is_set():
            if stop.wait(0.01):
                return STOPPED
        seen += key_down.is_set()
        if not arm.release():
            return STOPPED
    if not arm.from_key():
        return STOPPED
    return {"ok": seen == 3, "reason": f"key registers at {pressed_at:.2f}, releases at {released_at:.2f}, "
            f"lift {lift:.2f}; {seen} of 3 test taps registered"}
