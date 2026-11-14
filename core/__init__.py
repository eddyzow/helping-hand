"""Shared by the dispatcher and the skills. They live here, not in core/dispatcher.py, because
`python -m core.dispatcher` runs that file as __main__: a skill importing core.dispatcher would
get a second copy of the module, with its own events that nobody sets."""
import collections
import threading
import time

cue = threading.Event()      # 'start now' from outside, such as the game's restart key
waiting = threading.Event()  # set while a skill is waiting for that cue
key_down = threading.Event()  # the keypad's jump key is held down right now (reported by keypad/listen.py)
key_events = [0]              # how many such reports have arrived; 0 means no listener is feeding us

# Real time. Measured on 14 Nov: the clock inside WSL ran 4.2% fast against Windows (10 s here was
# 9.6 s there). A macro recorded on Windows and replayed on this clock came out 4% early, more with
# every second. So anything that must match the real world (the game, a recording) uses real_now(),
# which follows the Windows clock that keypad/listen.py reports several times a second.
_ticks = collections.deque(maxlen=600)  # (Windows seconds, our seconds when it arrived): about a minute
_ticks_lock = threading.Lock()


def clock_tick(windows_s: float) -> None:
    with _ticks_lock:
        _ticks.append((windows_s, time.perf_counter()))


def clock_rate() -> float:
    """Our seconds per real second, from the ticks of the last few seconds. 1.0 with no listener."""
    with _ticks_lock:
        if len(_ticks) < 8:
            return 1.0
        (w0, l0), (w1, l1) = _ticks[0], _ticks[-1]
    rate = (l1 - l0) / (w1 - w0) if w1 - w0 > 1.0 else 1.0
    return rate if 0.8 < rate < 1.25 else 1.0  # a wild value means a bad tick, not a real clock


def real_now() -> float:
    """Seconds on the Windows clock, extended from the newest tick. Falls back to our own clock."""
    with _ticks_lock:
        recent = list(_ticks)[-20:]
    here = time.perf_counter()
    if not recent or here - recent[-1][1] > 2.0:  # no listener, or it went quiet
        return here
    rate = clock_rate()
    # A tick can arrive a few milliseconds late but never early, so the least-delayed of the last
    # two seconds is the truest one to measure from. This keeps one slow tick from shifting the time.
    windows_s, arrived = min(recent, key=lambda tick: tick[1] - tick[0] * rate)
    return windows_s + (here - arrived) / rate
