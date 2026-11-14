"""Play Jonathan's recorded Stereo Madness key presses on the jump key, holds included.

    run geometry_dash {"first_taps": 5}

Be inside the level first. The arm hovers over the key and waits; the keypad listener then presses R
(restart) in the game and the replay clock starts at that instant, so the game and the arm start
together. Pressing R yourself does the same, and R again mid-run restarts the replay.
Needs the taught tap_key pose; tune the tap first with gd_tap (see skills/gd_tap.py). The recording and its reader are
Jonathan's: keypad/geometry_dash/.
"""
import sys
import time
from pathlib import Path

GD = Path(__file__).parent.parent / "keypad" / "geometry_dash"
sys.path.insert(0, str(GD))

NAME = "geometry_dash"
DESCRIPTION = "Play the start of Geometry Dash (Stereo Madness) by tapping the jump key"
PARAMS = {"first_taps": "int", "press_lead_ms": "float", "release_lead_ms": "float", "pattern": "str"}

STOPPED = {"ok": False, "reason": "stopped"}
CUE_WAIT_S = 120


def run(arm, params, stop):
    from core import cue, waiting
    from tap_pattern import command_times, read_pattern

    # everything is read and checked before the arm moves
    first = params.get("first_taps")
    if first is not None and (type(first) is not int or first < 1):
        return {"ok": False, "reason": "first_taps must be a whole number, 1 or more"}
    name = params.get("pattern", "stereo_madness.csv")
    if type(name) is not str or Path(name).name != name:
        return {"ok": False, "reason": "pattern must be a file name inside keypad/geometry_dash"}
    try:
        events = read_pattern(GD / name)
        if first:
            events = events[:2 * first]
        commands = command_times(events, params.get("press_lead_ms", 0), params.get("release_lead_ms", 0))
    except (OSError, ValueError, TypeError) as err:
        return {"ok": False, "reason": str(err)}
    if commands[0].at < 0:
        return {"ok": False, "reason": "the timing lead is longer than the wait before the first press"}

    if not arm.to_key():
        return STOPPED
    cue.clear()
    print(f"[geometry_dash] ready: {len(commands) // 2} presses, waiting for the restart key.", flush=True)
    try:
        while True:
            waiting.set()
            began = time.perf_counter()
            while not cue.wait(0.05):
                if stop.is_set():
                    return STOPPED
                if time.perf_counter() - began > CUE_WAIT_S:
                    return _finish(arm, "no restart key within 2 minutes")
            waiting.clear()
            cue.clear()
            start = time.perf_counter()
            for event in commands:
                while not cue.is_set() and (left := event.at - (time.perf_counter() - start)) > 0:
                    if stop.wait(min(left, 0.02)):
                        return STOPPED      # hold where it is; stop never commands a move
                if cue.is_set():            # the level was restarted: let go and start the clock again
                    arm.release()
                    break
                (arm.press if event.down else arm.release)()
            else:
                return _finish(arm, "")
    finally:
        waiting.clear()


def _finish(arm, reason):
    done = arm.release() and arm.from_key()
    return {"ok": bool(done and not reason), "reason": reason if done else "stopped"}
