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
PARAMS = {"first_taps": "int", "press_lead_ms": "float", "release_lead_ms": "float", "pattern": "str",
          "enter": "bool: the arm's own first press starts the level", "enter_delay_ms": "float",
          "then_restart_ms": "float: after entering, wait this long, restart, and play from the restart",
          "offset_ms": "float: shift every jump; plus is later, minus is earlier"}

STOPPED = {"ok": False, "reason": "stopped"}
CUE_WAIT_S = 120


def run(arm, params, stop):
    from core import cue, key_down, key_events, waiting
    from tap_pattern import command_times, read_pattern

    # "enter" mode: with the game on the level's Play screen, the arm's first press starts the level
    # and the replay clock starts from that same press, enter_delay_ms later (the game's own
    # fade-in before the level begins; tune it once by watching whether the jumps are early or late).
    enter, enter_delay_ms = params.get("enter", False), params.get("enter_delay_ms", 0)
    if type(enter) is not bool:
        return {"ok": False, "reason": "enter must be true or false"}
    if type(enter_delay_ms) not in (int, float) or not 0 <= enter_delay_ms <= 10000:
        return {"ok": False, "reason": "enter_delay_ms must be 0 to 10000"}
    # "then_restart_ms": after the arm's click on Play, wait this long for the level to load, then
    # restart it (R) and play from that restart. Use it with a macro recorded from the restart key.
    offset_ms = params.get("offset_ms", 0)
    if type(offset_ms) not in (int, float) or not -1000 <= offset_ms <= 1000:
        return {"ok": False, "reason": "offset_ms must be -1000 to 1000"}
    then_restart_ms = params.get("then_restart_ms")
    if then_restart_ms is not None and (type(then_restart_ms) not in (int, float) or not 0 <= then_restart_ms <= 20000):
        return {"ok": False, "reason": "then_restart_ms must be 0 to 20000"}

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
    feels_key = key_events[0] > 0  # the keypad listener has been reporting the jump key to this dispatcher
    print(f"[geometry_dash] ready: {len(commands) // 2} presses, waiting for the restart key.", flush=True)
    try:
        while True:
            began = time.perf_counter()
            if enter:
                enter = False  # only the first round; a later restart (R) uses the cue as usual
                if not arm.press():
                    return STOPPED
                while not key_down.is_set():  # the clock starts when the key really registers
                    if stop.is_set():
                        return STOPPED
                    if time.perf_counter() - began > 0.5:
                        return _finish(arm, "the entering press did not register; run tap_calibrate")
                    time.sleep(0.0005)
                start = time.perf_counter() + enter_delay_ms / 1000
                feels_key = True  # the keypad listener is reporting the jump key to us
                if stop.wait(0.08) or not arm.release():
                    return STOPPED
                if then_restart_ms is not None:
                    # The click on Play has started the level. Let it load, then take the clock from a
                    # restart, which begins the level at once and is where a restart-recorded macro starts.
                    if stop.wait(then_restart_ms / 1000):
                        return STOPPED
                    cue.clear()
                    start = None
            else:
                start = None
            if start is None:
                began = time.perf_counter()
                waiting.set()
                while not cue.wait(0.05):
                    if stop.is_set():
                        return STOPPED
                    if time.perf_counter() - began > CUE_WAIT_S:
                        return _finish(arm, "no restart key within 2 minutes")
                start = time.perf_counter()
                waiting.clear()
                cue.clear()
            start += offset_ms / 1000  # the one knob: plus makes every jump later, minus earlier
            seen, last = [], [key_down.is_set()]  # what the keypad really did, to report after the run

            def watch():
                state = key_down.is_set()
                if state != last[0]:
                    last[0] = state
                    seen.append((time.perf_counter() - start, state))

            for event in commands:
                while not cue.is_set() and (left := event.at - (time.perf_counter() - start)) > 0:
                    watch()
                    if stop.wait(min(left, 0.002)):
                        # hold where it is; stop never commands a move
                        return {**STOPPED, "timing": _timing(seen, events) if feels_key else ""}
                if cue.is_set():            # the level was restarted: let go and start the clock again
                    arm.release()
                    break
                if event.down:
                    arm.press()
                    continue
                # A short tap's release can come due before the press has even registered (the press
                # takes 110 to 164 ms on this arm), and lifting then cancels the jump. When the keypad
                # reports its key to us, hold the press until it registers, at most 0.2 s longer.
                limit = time.perf_counter() + 0.2
                while feels_key and not key_down.is_set() and time.perf_counter() < limit:
                    if stop.is_set():
                        return STOPPED
                    if cue.is_set():
                        break
                    time.sleep(0.0005)
                watch()  # the press may have registered during that wait: note it before releasing
                arm.release()
            else:
                settle = time.perf_counter() + 0.3  # catch the last release
                while feels_key and time.perf_counter() < settle and not stop.is_set():
                    watch()
                    time.sleep(0.002)
                result = _finish(arm, "")
                if feels_key:
                    result["timing"] = _timing(seen, events)
                return result
    finally:
        waiting.clear()


def _timing(seen, events) -> str:
    """Compare what the keypad reported with the recording: counts, and how early or late in ms."""
    seen = [(t, down) for t, down in seen if t > events[0].at - 0.5]  # not the level-entering press
    lines = []
    for down, word in ((True, "presses"), (False, "releases")):
        got = [t for t, d in seen if d == down]
        want = [e.at for e in events if e.down == down]
        if len(got) < len(want) and all(abs(g - w) < 0.25 for g, w in zip(got, want)) and got:
            # cut short (stopped, or the cube died): still say how the ones that happened were timed
            err = [(g - w) * 1000 for g, w in zip(got, want)]
            lines.append(f"{word}: first {len(got)} of {len(want)} seen, average {sum(err) / len(err):+.0f} ms "
                         f"(from {min(err):+.0f} to {max(err):+.0f})")
        elif len(got) != len(want):
            off = next((i for i, (g, w) in enumerate(zip(got, want)) if abs(g - w) > 0.25), min(len(got), len(want)))
            lines.append(f"{word}: keypad saw {len(got)}, recording has {len(want)}; first difference at "
                         f"number {off + 1}, {want[off]:.2f} s into the level" if off < len(want) else
                         f"{word}: keypad saw {len(got)}, recording has {len(want)}; extra ones at the end")
        elif got:
            err = [(g - w) * 1000 for g, w in zip(got, want)]
            worst = max(range(len(err)), key=lambda i: abs(err[i]))
            lines.append(f"{word}: all {len(got)} seen, average {sum(err) / len(err):+.0f} ms "
                         f"(from {min(err):+.0f} to {max(err):+.0f}; worst is number {worst + 1} at {want[worst]:.2f} s)")
    return "; ".join(lines) + ". Plus means late."


def _finish(arm, reason):
    done = arm.release() and arm.from_key()
    return {"ok": bool(done and not reason), "reason": reason if done else "stopped"}
