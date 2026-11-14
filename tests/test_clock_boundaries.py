"""Clock-feed boundaries, with fake time and no listener or arm connection."""
import math
from unittest.mock import patch

import core
from core import dispatcher


def test_first_tick():
    now = [1000.0]
    core._ticks.clear()
    with patch.object(core.time, "perf_counter", lambda: now[0]):
        before = core.real_now()
        core.clock_tick(100.0)
        joined = core.real_now()
        assert math.isclose(joined, before, abs_tol=0.001), (before, joined)


def test_stale_clock():
    now = [1000.0]
    core._ticks.clear()
    with patch.object(core.time, "perf_counter", lambda: now[0]):
        core.clock_tick(100.0)
        joined = core.real_now()
        now[0] += 2.01
        stale = core.real_now()
        assert math.isclose(stale - joined, 2.01, abs_tol=0.001), (joined, stale)


def test_clock_resumption():
    now = [1000.0]
    core._ticks.clear()
    with patch.object(core.time, "perf_counter", lambda: now[0]):
        core.clock_tick(100.0)
        now[0] += 2.01
        stale = core.real_now()
        core.clock_tick(102.01)
        resumed = core.real_now()
        assert math.isclose(resumed, stale, abs_tol=0.001), (stale, resumed)


def test_invalid_clock_reports():
    failures = []
    with patch.object(core.time, "perf_counter", lambda: 1000.0):
        for value in ("nan", "inf", "-inf", "not-a-number", ""):
            core._ticks.clear()
            before = core.real_now()
            reply = dispatcher.handle("clock " + value)
            reading = core.real_now()
            if reply["ok"] is not False or not math.isfinite(reading) or reading != before:
                failures.append((value, reply, reading))
    assert not failures, failures


def test_clock_rate():
    now = [1000.0]
    core._ticks.clear()
    with patch.object(core.time, "perf_counter", lambda: now[0]):
        for index in range(21):
            now[0] = 1000.0 + index * 0.1042
            core.clock_tick(100.0 + index * 0.1)
        assert math.isclose(core.clock_rate(), 1.042, abs_tol=0.000001)
        before = core.real_now()
        now[0] += 0.1042
        assert math.isclose(core.real_now() - before, 0.1, abs_tol=0.000001)


if __name__ == "__main__":
    failures = []
    for check in (test_first_tick, test_stale_clock, test_clock_resumption,
                  test_invalid_clock_reports, test_clock_rate):
        try:
            check()
            print(check.__name__, "ok")
        except AssertionError as error:
            failures.append(check.__name__)
            print(check.__name__, "FAILED", error)
        finally:
            core._ticks.clear()
    assert not failures, failures
    print("clock boundaries ok")
