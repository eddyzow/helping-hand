"""Fake blocked jaw and no-wait clock only: python -B -m tests.test_grip_history."""
import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import core.arm as arms


class Arm(arms.MockArm):
    def __init__(self):
        super().__init__()
        self.halt = SimpleNamespace(is_set=lambda: False, wait=lambda seconds: False)
        self.sent = []

    def _write(self, joints):
        self.sent.append(joints[5])
        super()._write(joints)
        self._joints[5] = max(19.0, joints[5])  # the object stops a closing jaw at 19


def pose(grip):
    return [0.0] * 5 + [float(grip)]


def test_consecutive_moves():
    arm = Arm()
    assert arm.move_joints(pose(5), .1)
    arm.sent.clear()
    assert arm.move_joints(pose(5), .1)
    assert arm.sent and all(value == 5 for value in arm.sent), arm.sent


def test_failed_write_keeps_history():
    arm = Arm()
    assert arm.move_joints(pose(5), .1)
    with patch.object(arm, "_write", side_effect=RuntimeError("fake write failed before sending")):
        try:
            arm.move_joints(pose(60), .1)
        except RuntimeError:
            pass
        else:
            raise AssertionError("write failure was swallowed")
    arm.sent.clear()
    assert arm.move_joints(pose(5), .1)
    assert arm.sent and all(value == 5 for value in arm.sent), \
        f"failed opening write replaced the successful held-grip history: {arm.sent}"


def test_play_then_hold():
    arm = Arm()
    assert arm.play([(0, pose(60)), (.1, pose(5))])
    arm.sent.clear()
    assert arm.move_joints(pose(5), .1)
    assert arm.sent and all(value == 5 for value in arm.sent), \
        f"play closed at 5, but next same-grip move relaxed the jaw: {arm.sent}"


def test_play_then_close():
    arm = Arm()
    assert arm.play([(0, pose(5)), (.1, pose(60))])
    arm.sent.clear()
    assert arm.move_joints(pose(5), .1)
    assert 5 < arm.sent[0] < 60 and arm.sent[-1] == 5, \
        f"play opened to 60, but next close skipped the requested ramp: {arm.sent}"


if __name__ == "__main__":
    failed = 0
    with tempfile.TemporaryDirectory() as temporary, patch.object(arms, "POSES", Path(temporary)):
        for check in (test_consecutive_moves, test_failed_write_keeps_history, test_play_then_hold, test_play_then_close):
            try:
                check()
                print(check.__name__, "ok")
            except AssertionError as error:
                failed += 1
                print(check.__name__, "FAILED:", error)
    raise SystemExit(bool(failed))
