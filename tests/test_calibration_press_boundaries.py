"""Fake arm/key/clock and temporary poses only: python -B -m tests.test_calibration_press_boundaries."""
import json
import tempfile
import threading
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import core
import core.arm as arms
from skills import tap_calibrate


def calibrated(press):
    key, clock, writes = threading.Event(), [0.0], []
    joint = arms.TAP_JOINT

    def wait(seconds):
        clock[0] += seconds
        return False

    class Arm(arms.MockArm):
        def __init__(self):
            self.halt = SimpleNamespace(is_set=lambda: False, wait=wait)
            self._poses = {"tap_key": [40.0] * 6}
            self._joints = [40.0] * 6
            self.lift, self.press_extra = 3.0, press

        def to_key(self): return True
        def from_key(self): return True

        def _write(self, pose):
            writes.append(pose[joint])
            if pose[joint] >= 40.88:
                key.set()
            elif pose[joint] < 40.7:
                key.clear()

    with tempfile.TemporaryDirectory() as temporary, \
            patch.object(arms, "POSES", Path(temporary)), patch.object(core, "key_down", key), \
            patch.object(tap_calibrate, "time", SimpleNamespace(perf_counter=lambda: clock[0])):
        arm = Arm()
        result = tap_calibrate.run(arm, {"max_travel": 1}, arm.halt)
        if not result["ok"]:
            assert not list(Path(temporary).iterdir()), "rejected calibration changed saved files"
            assert (arm.lift, arm.press_extra) == (3.0, press), "rejected calibration changed live tune"
            return None, False, result
        tune = json.loads((Path(temporary) / "tap_tune.json").read_text())
        assert tune["press"] == arm.press_extra, tune
        assert max(writes) <= 41.0 + 1e-9, writes
        arm.press()
        return writes[-1], key.is_set(), result


def test_zero_control():
    target, registered, result = calibrated(0.0)
    assert result["ok"] and target <= 41.0 + 1e-9 and registered, (target, registered, result)


def test_retained_press_travel():
    target, _, result = calibrated(1.0)
    assert not result["ok"] or target <= 41.0 + 1e-9, f"saved effective press {target} exceeds calibration limit 41: {result}"


def test_retained_press_registers():
    target, registered, result = calibrated(-1.0)
    assert not result["ok"] or registered, f"successful calibration retained a non-registering press at {target}: {result}"


if __name__ == "__main__":
    failed = 0
    for check in (test_zero_control, test_retained_press_travel, test_retained_press_registers):
        try:
            check()
            print(check.__name__, "ok")
        except AssertionError as error:
            failed += 1
            print(check.__name__, "FAILED:", error)
    raise SystemExit(bool(failed))
