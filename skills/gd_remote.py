"""Carry out taps sent from Windows, the instant they arrive. No timing is done here.

    run gd_remote

The arm goes over the jump key and waits. keypad/geometry_dash/arm_play.py, running on Windows,
keeps the time on the Windows clock (the one the macro was recorded on) and sends
"tap press" / "tap release" / "tap end". The clock inside WSL was measured unsteady, 4 to 6% fast,
so a replay timed here drifted by tenths of a second.
"""
import queue
import time

NAME = "gd_remote"
DESCRIPTION = "Hold the arm over the jump key and carry out taps sent by the Windows sequencer"
PARAMS = {"idle_s": "float: go home after this long with no tap (default 20)"}

STOPPED = {"ok": False, "reason": "stopped"}


def run(arm, params, stop):
    from core import remote, remote_ready

    idle_s = params.get("idle_s", 20)
    if type(idle_s) not in (int, float) or not 1 <= idle_s <= 300:
        return {"ok": False, "reason": "idle_s must be 1 to 300"}
    while not remote.empty():  # nothing left over from an earlier run
        remote.get_nowait()
    if not arm.to_key():
        return STOPPED
    taps, last = 0, time.monotonic()
    remote_ready.set()
    try:
        while not stop.is_set():
            try:
                tap = remote.get(timeout=0.02)
            except queue.Empty:
                if time.monotonic() - last > idle_s:
                    break
                continue
            last = time.monotonic()
            if tap == "end":
                break
            (arm.press if tap == "press" else arm.release)()
            taps += 1
    finally:
        remote_ready.clear()
    if stop.is_set():
        return STOPPED
    return {"ok": bool(arm.release() and arm.from_key()), "reason": "", "taps": taps}
