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
#
# real_now() is ONE continuous timeline. Only the SPEED of our clock is taken from the ticks; the
# time itself is never set from outside. An earlier version followed the Windows time directly and
# fell back to our own clock when the ticks paused: the two have different starting points, so a
# pause of two seconds threw a replay half a second off. Now a pause just keeps the last known speed.
_ticks = collections.deque(maxlen=300)  # (Windows seconds, our seconds when it arrived): about 30 s
_ticks_lock = threading.Lock()
_rate = [1.0]                           # our seconds per real second
_anchor = [time.perf_counter(), 0.0]    # (our clock, real_now) at the last change of rate
max_tick_gap = [0.0]                    # longest pause between ticks, for diagnosis; a skill may reset it


def _real_at(here: float) -> float:
    return _anchor[1] + (here - _anchor[0]) / _rate[0]


def clock_tick(windows_s: float) -> None:
    """A report of the Windows clock. Raises ValueError for anything that is not a finite number."""
    if not (isinstance(windows_s, float) and windows_s == windows_s and abs(windows_s) != float("inf")):
        raise ValueError("clock needs a finite number")
    here = time.perf_counter()
    with _ticks_lock:
        if _ticks:
            max_tick_gap[0] = max(max_tick_gap[0], here - _ticks[-1][1])
            if windows_s <= _ticks[-1][0]:  # the listener restarted, or a stray report: start measuring afresh
                _ticks.clear()
        _ticks.append((windows_s, here))
        if len(_ticks) < 30 or _ticks[-1][0] - _ticks[0][0] < 3.0:
            return
        # A tick can arrive late but never early, so the least-delayed tick of the first third and of
        # the last third give the truest slope.
        ticks, old = list(_ticks), _rate[0]
        third = len(ticks) // 3
        w0, l0 = min(ticks[:third], key=lambda t: t[1] - t[0] * old)
        w1, l1 = min(ticks[-third:], key=lambda t: t[1] - t[0] * old)
        rate = (l1 - l0) / (w1 - w0)
        if 0.8 < rate < 1.25:  # anything else is a bad measurement, not a real clock
            _anchor[:] = [here, _real_at(here)]  # keep the timeline continuous across the change
            _rate[0] = rate


def clock_rate() -> float:
    """Our seconds per real second. 1.0 until the listener has reported for a few seconds."""
    return _rate[0]


def real_now() -> float:
    """Seconds of real time on one continuous timeline (its zero means nothing; use differences)."""
    with _ticks_lock:
        return _real_at(time.perf_counter())
