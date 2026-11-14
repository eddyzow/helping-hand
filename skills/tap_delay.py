"""Measure how long the arm takes to press and to release the jump key, using the keypad's own events.

    run tap_delay

It taps ten times and times each press (command sent -> key reads down) and each release (command
sent -> key reads up). The medians are the timing leads for the game: the replay sends each command
that much early, so the key changes at the recorded instant.
Needs keypad/listen.py running and a calibrated tap (run tap_calibrate first).
"""
import time
from statistics import median

NAME = "tap_delay"
DESCRIPTION = "Measure the press and release delay of a tap, to sync Geometry Dash"
PARAMS = {"times": "int"}

STOPPED = {"ok": False, "reason": "stopped"}


def run(arm, params, stop):
    from core import key_down, real_now

    times = params.get("times", 10)
    if type(times) is not int or not 3 <= times <= 50:
        return {"ok": False, "reason": "times must be a whole number from 3 to 50"}
    if not arm.to_key():
        return STOPPED

    def until(pressed: bool, start=None):
        """Milliseconds from `start` until the key reads as wanted, or None after half a second or on stop.
        Pass the time taken just BEFORE the command: sending it to the motors takes time too, and the
        replay needs the whole delay from deciding to press until the key changes."""
        start = real_now() if start is None else start
        while key_down.is_set() != pressed:
            if stop.is_set() or real_now() - start > 0.5:
                return None
            time.sleep(0.0005)
        return (real_now() - start) * 1000

    press_ms, release_ms = [], []
    for _ in range(times):
        if stop.wait(0.3) or until(False) is None:
            break
        sent = real_now()
        if not arm.press():
            break
        down = until(True, sent)
        if down is None or stop.wait(0.15):
            break
        sent = real_now()
        if not arm.release():
            break
        up = until(False, sent)
        if up is None:
            break
        press_ms.append(down)
        release_ms.append(up)
    if stop.is_set():
        return STOPPED
    if not arm.from_key():
        return STOPPED
    if len(press_ms) < times:
        return {"ok": False, "reason": f"only {len(press_ms)} of {times} taps registered and released; "
                "re-run tap_calibrate, or raise the lift if the key stays held"}
    p, r = round(median(press_ms)), round(median(release_ms))
    return {"ok": True, "press_ms": p, "release_ms": r,
            "reason": f"press {p} ms (from {min(press_ms):.0f} to {max(press_ms):.0f}), "
                      f"release {r} ms (from {min(release_ms):.0f} to {max(release_ms):.0f}). Now: "
                      f'run geometry_dash {{"first_taps": 5, "press_lead_ms": {p}, "release_lead_ms": {r}}}'}
