"""Fake clocks, arms and leader factory only: python -B -m tests.test_steady_boundaries."""
import json
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import arm as root_arm
import core.arm
from core.arm import HZ, JOINTS, MockArm
from skills import steady


class Flag:
    def __init__(self, time):
        self.time, self.on = time, False

    def is_set(self):
        return self.on

    def wait(self, seconds):
        if not self.on:
            self.time[0] += seconds
        return self.on


class Spy(MockArm):
    def __init__(self, time, delay=0):
        super().__init__()
        self.halt, self.writes, self.time, self.delay = Flag(time), [], time, delay
        self.calls = []

    def _write(self, joints):
        self.time[0] += self.delay
        self.writes.append((self.time[0], list(joints)))
        super()._write(joints)

    def move_joints(self, joints, seconds):
        before = len(self.writes)
        result = super().move_joints(joints, seconds)
        self.calls.append((seconds, len(self.writes) - before))
        return result


def test_zero_duration():
    time = [0.0]
    arm = Spy(time, .2)
    assert arm.move_joints([1] * 6, 0)
    assert len(arm.writes) == 1 and abs(time[0] - (.2 + 1 / HZ)) < 1e-9
    arm.halt.on = True
    assert not arm.move_joints([2] * 6, 0) and len(arm.writes) == 1


def follow(leader_pan, read_delay=0, write_delay=0, max_dps=120):
    time, reads, disconnected = [0.0], [], []
    arm = Spy(time, write_delay)

    def read():
        time[0] += read_delay
        reads.append(time[0])
        return dict(zip((name + ".pos" for name in JOINTS), [leader_pan, 0, 0, 0, 0, 0]))

    leader = SimpleNamespace(get_action=read, disconnect=lambda: disconnected.append(1))
    with patch.object(steady, "clock", lambda: time[0]), patch.object(steady, "open_leader", lambda _: leader):
        result = steady.run(arm, {"seconds": 1, "max_dps": max_dps}, arm.halt)
    assert result["ok"] and disconnected == [1]
    return arm, reads, json.loads(steady.TRACE.read_text())["rows"]


def test_slow_io():
    arm, reads, rows = follow(10, .2, .1)
    stream = [(duration, count) for duration, count in arm.calls if duration == 0]
    assert len(stream) == len(rows) == len(reads) - 3
    assert all(count == 1 for _, count in stream)
    assert 1 <= len(rows) <= 4, len(rows)
    assert all(b[0] - a[0] >= .3 for a, b in zip(rows, rows[1:])), rows
    print("slow-I/O stream samples:", len(rows), "; one read and one write per sample, no catch-up burst")


def test_glide_limit(leader_pan=100, home_pan=-100, max_dps=120):
    with patch.object(MockArm, "load_pose", return_value=[home_pan, 0, 0, 0, 0, 0]):
        arm, _, _ = follow(leader_pan, max_dps=max_dps)
    duration = arm.calls[1][0]  # first call is home; second is the initial leader glide.
    distance = abs(leader_pan - home_pan)
    bound = min(steady.GLIDE_DPS, max_dps)
    assert distance / duration <= bound + 1e-9, (distance, duration, distance / duration, bound)


def test_slow_glide():
    test_glide_limit(40, 0, 10)


def test_port_identity():
    opened = []
    teleop = SimpleNamespace(connect=lambda: opened.append("connect"), disconnect=lambda: None)
    fake = SimpleNamespace(SO101LeaderConfig=lambda **kwargs: kwargs,
                           SO101Leader=lambda config: opened.append(config) or teleop)
    with patch.object(root_arm, "LEADER_PORT", "/dev/ttyACM1"), \
            patch.object(root_arm, "FOLLOWER_PORT", "/dev/ttyACM1"), \
            patch.dict(sys.modules, {"lerobot.teleoperators.so_leader": fake}):
        try:
            steady.open_leader(SimpleNamespace(REAL=True))
        except ValueError:
            pass
    assert not opened, ("leader attempted the follower port", opened)


if __name__ == "__main__":
    with tempfile.TemporaryDirectory() as temporary, patch.object(core.arm, "POSES", Path(temporary)), \
            patch.object(steady, "TRACE", Path(temporary) / "trace.json"):
        (Path(temporary) / "home.json").write_text(json.dumps({name + ".pos": 0.0 for name in JOINTS}))
        steady._selfcheck()
        test_zero_duration()
        test_slow_io()
        print("duration-zero and slow-I/O controls pass")
        failures = []
        for test in (test_glide_limit, test_slow_glide, test_port_identity):
            try:
                test()
                print("PASS", test.__name__)
            except AssertionError as error:
                failures.append((test.__name__, str(error)))
                print("FAIL", test.__name__, error)
        assert not failures, failures
