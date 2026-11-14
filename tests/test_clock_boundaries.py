"""Clock-feed boundaries, with fake time and no listener or arm connection."""
import ast
import importlib
import math
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import core
from core import dispatcher


def test_first_tick():
    now = [1000.0]
    core._ticks.clear()
    with patch.object(core.time, "perf_counter", lambda: now[0]):
        importlib.reload(core)
        before = core.real_now()
        core.clock_tick(100.0)
        joined = core.real_now()
        assert math.isclose(joined, before, abs_tol=0.001), (before, joined)


def test_stale_clock():
    now = [1000.0]
    core._ticks.clear()
    with patch.object(core.time, "perf_counter", lambda: now[0]):
        importlib.reload(core)
        core.clock_tick(100.0)
        joined = core.real_now()
        now[0] += 2.01
        stale = core.real_now()
        assert math.isclose(stale - joined, 2.01, abs_tol=0.001), (joined, stale)


def test_clock_resumption():
    now = [1000.0]
    core._ticks.clear()
    with patch.object(core.time, "perf_counter", lambda: now[0]):
        importlib.reload(core)
        core.clock_tick(100.0)
        now[0] += 2.01
        stale = core.real_now()
        core.clock_tick(102.01)
        resumed = core.real_now()
        assert math.isclose(resumed, stale, abs_tol=0.001), (stale, resumed)


def test_invalid_clock_reports():
    failures = []
    with patch.object(core.time, "perf_counter", lambda: 1000.0):
        importlib.reload(core)
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
        importlib.reload(core)
        for index in range(41):
            now[0] = 1000.0 + index * 0.1042
            before = core.real_now()
            core.clock_tick(100.0 + index * 0.1)
            assert math.isclose(core.real_now(), before, abs_tol=0.000001)
        assert math.isclose(core.clock_rate(), 1.042, abs_tol=0.000001)
        before = core.real_now()
        now[0] += 0.1042
        assert math.isclose(core.real_now() - before, 0.1, abs_tol=0.000001)
        before = core.real_now()
        now[0] += 2.084
        assert math.isclose(core.real_now() - before, 2., abs_tol=0.000001)
        before = core.real_now()
        core.clock_tick(1.0)  # a restarted listener must not reset the timeline
        assert math.isclose(core.real_now(), before, abs_tol=0.000001)


def test_local_timeout():
    path = Path(__file__).resolve().parents[1] / "skills" / "tap_delay.py"
    node = next(node for node in ast.walk(ast.parse(path.read_text()))
                if isinstance(node, ast.FunctionDef) and node.name == "until")
    local = [0.]

    def sleep(seconds):
        local[0] += .01
        assert local[0] < 1., "feedback wait never timed out"

    scope = {"real_now": lambda: local[0] / 1.24,
             "time": SimpleNamespace(perf_counter=lambda: local[0], sleep=sleep),
             "key_down": SimpleNamespace(is_set=lambda: False),
             "stop": SimpleNamespace(is_set=lambda: False)}
    exec(compile(ast.Module(body=[node], type_ignores=[]), str(path), "exec"), scope)
    assert scope["until"](True) is None
    assert local[0] <= .511, ("external rate changed local half-second timeout", local[0])


if __name__ == "__main__":
    failures = []
    for check in (test_first_tick, test_stale_clock, test_clock_resumption,
                  test_invalid_clock_reports, test_clock_rate, test_local_timeout):
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
