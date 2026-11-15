"""Run actual standalone main with fake devices/servers/clock; no ports, MuJoCo or hardware."""
import json
import math
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import numpy as np
import steady


def scenario(mode):
    now, reads, writes, cleanup = [0.0], [0], [], []
    follower = SimpleNamespace()
    leader = SimpleNamespace(connect=lambda: None, disconnect=lambda: cleanup.append(("leader", False)))

    def read():
        reads[0] += 1
        if mode == "read_failure" and reads[0] == 3:
            raise ConnectionError("fake lost leader")
        if mode == "stop_during_read" and reads[0] == 3:
            steady.command("stop")
        return dict(zip(steady.KEYS, [50, 0, 0, 0, 0, 0]))

    def send(action):
        writes.append((steady.state["hold"], dict(action)))
        if mode == "hold_during_ease" and len(writes) == 2:
            steady.command("hold on")
        if len(writes) >= (3 if mode == "hold_during_ease" else 2):
            steady.state["quit"] = True

    leader.get_action = read
    follower.connect = lambda: None
    follower.get_observation = lambda: dict.fromkeys(steady.KEYS, 0.0)
    follower.send_action = send
    follower.disconnect = lambda: cleanup.append(("follower", follower.config.disable_torque_on_disconnect))
    follower.bus = SimpleNamespace(sync_read=lambda *args, **kwargs: {})

    def make_follower(config):
        follower.config = config
        return follower

    fake_follower = SimpleNamespace(SO101Follower=make_follower,
        SO101FollowerConfig=lambda **kwargs: SimpleNamespace(disable_torque_on_disconnect=True, **kwargs))
    fake_leader = SimpleNamespace(SO101Leader=lambda config: leader, SO101LeaderConfig=lambda **kwargs: kwargs)
    server = lambda *args, **kwargs: SimpleNamespace(serve_forever=lambda: None)
    clock = SimpleNamespace(perf_counter=lambda: now[0], strftime=lambda _: "fake",
        sleep=lambda seconds: now.__setitem__(0, now[0] + (4 if mode == "stop_during_read" else 1)))
    tip = SimpleNamespace(mm=lambda joints: np.zeros(3), chain=lambda joints: [], geoms=lambda joints: [])
    with tempfile.TemporaryDirectory() as temporary:
        offsets = Path(temporary) / "offsets.json"
        values = dict.fromkeys(steady.KEYS, 0.0)
        if mode == "invalid_offset":
            values[steady.KEYS[0]] = float("nan")
        offsets.write_text(json.dumps(values))
        with patch.dict(sys.modules, {"lerobot.robots.so_follower": fake_follower,
                "lerobot.teleoperators.so_leader": fake_leader}), \
                patch.object(sys, "argv", ["steady", "--yes"]), \
                patch.object(steady, "OFFSETS", offsets), patch.object(steady, "OUT", Path(temporary) / "out"), \
                patch.object(steady, "Fingertip", lambda: tip), patch.object(steady, "time", clock), \
                patch.object(steady.socketserver, "ThreadingTCPServer", server), \
                patch.object(steady, "HTTPServer", server), \
                patch.object(steady.threading, "Thread", lambda *args, **kwargs: SimpleNamespace(start=lambda: None)), \
                patch.dict(steady.state, steady=True, hold=False, cutoff=2.0, quit=False):
            try:
                steady.main()
            except (ConnectionError, ValueError):
                if mode not in ("read_failure", "invalid_offset"):
                    raise
    return writes, cleanup


def test_stop_during_read():
    writes, _ = scenario("stop_during_read")
    assert len(writes) < 2 or writes[1][1] == writes[0][1], ("new target after stop", writes)


def test_hold_during_ease():
    writes, _ = scenario("hold_during_ease")
    assert len(writes) < 3 or writes[2][1] == writes[1][1], ("hold changed target", writes)


def test_failure_cleanup():
    _, cleanup = scenario("read_failure")
    assert ("follower", True) not in cleanup, ("unconfirmed torque-off after read failure", cleanup)


def test_invalid_offset():
    writes, _ = scenario("invalid_offset")
    assert not writes, ("invalid offset reached send_action", writes)


if __name__ == "__main__":
    normal, _ = scenario("normal")
    assert normal and all(math.isfinite(value) for _, action in normal for value in action.values())
    print("finite normal-loop control passes")
    failures = []
    for test in (test_stop_during_read, test_hold_during_ease, test_failure_cleanup, test_invalid_offset):
        try:
            test()
        except AssertionError as error:
            failures.append((test.__name__, str(error)))
            print("FAIL", test.__name__, error)
    assert not failures, failures
