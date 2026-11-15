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
    retrying, failure_started = [False], [None]
    follower = SimpleNamespace()
    leader = SimpleNamespace(connect=lambda: None, disconnect=lambda: cleanup.append(("leader", False)))

    def read():
        reads[0] += 1
        if mode == "read_failure" and reads[0] >= 3:
            raise ConnectionError("fake lost leader")
        if mode == "hold_recovery" and reads[0] == 3:
            raise ConnectionError("fake transient lost leader")
        if mode == "link_deadline" and reads[0] >= 3:
            if failure_started[0] is None:
                failure_started[0] = now[0]
            now[0] += .5
            raise ConnectionError("fake half-second read failure")
        if mode in ("stop_during_read", "spoken_off") and reads[0] == 3:
            steady.command("steady off" if mode == "spoken_off" else "stop")
        pan = 5 * math.sin(2 * math.pi * 6 * now[0]) if mode in ("slow_meter", "meter_warmup") else 50
        return dict(zip(steady.KEYS, [pan, 0, 0, 0, 60 if mode == "roll_no_follow" else 0, 80 if mode == "latch_start" else 0]))

    def send(action):
        if mode == "send_deadline" and len(writes) == 1:
            if failure_started[0] is None:
                failure_started[0] = now[0]
            now[0] += .5
            if now[0] - failure_started[0] >= 25:
                steady.state["quit"] = True
            raise ConnectionError("fake persistent send failure")
        if mode == "stop_during_retry" and len(writes) == 1 and not retrying[0]:
            retrying[0] = True
            steady.command("stop")
            raise ConnectionError("fake send failure before write")
        writes.append((steady.state["hold"], dict(action)))
        if mode == "hold_recovery" and len(writes) == 1:
            steady.command("stop")
        if mode in ("hold_during_ease", "hold_grip", "hold_roll") and len(writes) == 2:
            steady.command("hold on")
        if len(writes) >= (205 if mode == "slow_meter" else 50 if mode == "meter_warmup" else 7 if mode == "load_failure" else 3 if mode in ("hold_during_ease", "hold_grip", "hold_roll", "hold_recovery") else 2):
            steady.state["quit"] = True

    def observe():
        values = dict.fromkeys(steady.KEYS, 0.0)
        if mode == "invalid_follower":
            values[steady.KEYS[0]] = float("nan")
        if mode == "hold_grip" and len(writes) >= 2:
            values["gripper.pos"] = 20.0
        if mode == "hold_roll" and len(writes) >= 2:
            values["wrist_roll.pos"] = 20.0
        if mode == "hold_recovery" and len(writes) >= 2:
            values["shoulder_pan.pos"] = 20.0
        if mode == "latch_start":
            values["gripper.pos"] = steady.GRIP_FLOOR
        return values

    leader.get_action = read
    follower.connect = lambda: None
    follower.get_observation = observe
    follower.send_action = send
    follower.disconnect = lambda: cleanup.append(("follower", follower.config.disable_torque_on_disconnect))
    # Cover the default calibration path separately from the optional saved-offset path.
    ranges = {j: SimpleNamespace(range_min=1000, range_max=3000) for j in steady.JOINTS}
    bad = {**ranges, steady.JOINTS[0]: SimpleNamespace(range_min=float("nan"), range_max=3000)}
    follower.bus = SimpleNamespace(sync_read=lambda *args, **kwargs: {}, calibration=ranges)
    leader.bus = SimpleNamespace(calibration=bad if mode == "invalid_calibration" else ranges)
    load_reads = []

    def load_read(*args, **kwargs):
        assert kwargs["num_retry"] == 12
        load_reads.append(args)
        if len(load_reads) > 1:
            raise ConnectionError("fake unavailable load reading")
        return {"gripper": 1000}

    if mode == "load_failure":
        follower.bus.sync_read = load_read
    if mode == "torque_limit":
        follower.bus.sync_write = lambda *args, **kwargs: cleanup.append(("register", args, kwargs))

    def make_follower(config):
        follower.config = config
        return follower

    fake_follower = SimpleNamespace(SO101Follower=make_follower,
        SO101FollowerConfig=lambda **kwargs: SimpleNamespace(**{"disable_torque_on_disconnect": True, **kwargs}))
    fake_leader = SimpleNamespace(SO101Leader=lambda config: leader, SO101LeaderConfig=lambda **kwargs: kwargs)
    server = lambda *args, **kwargs: SimpleNamespace(serve_forever=lambda: None)
    sleeps = [0]

    def sleep(seconds):
        if mode in ("link_deadline", "send_deadline"):
            now[0] += seconds
            if now[0] >= 75:
                steady.state["quit"] = True
            return
        now[0] += .04 if mode in ("slow_meter", "meter_warmup") else 4 if mode in ("stop_during_read", "spoken_off") else 1
        sleeps[0] += 1
        if sleeps[0] >= (210 if mode in ("slow_meter", "meter_warmup") else 8 if mode == "load_failure" else 4):
            steady.state["quit"] = True

    clock = SimpleNamespace(perf_counter=lambda: now[0], strftime=lambda _: "fake", sleep=sleep)
    tip = SimpleNamespace(mm=lambda joints: np.array(joints[:3]) if mode in ("slow_meter", "meter_warmup") else np.zeros(3),
                          chain=lambda joints: [], geoms=lambda joints: [])
    with tempfile.TemporaryDirectory() as temporary:
        offsets = Path(temporary) / "offsets.json"
        values = dict.fromkeys(steady.KEYS, 0.0)
        if mode == "invalid_offset":
            values[steady.KEYS[0]] = float("nan")
        offsets.write_text(json.dumps(values))
        history = Path(temporary) / "sessions.json"
        read_sessions, save_sessions = steady.read_sessions, steady.save_sessions
        with patch.dict(sys.modules, {"lerobot.robots.so_follower": fake_follower,
                "lerobot.teleoperators.so_leader": fake_leader}), \
                patch.object(sys, "argv", ["steady", "--yes"] + (["--shake", "6", "2"] if mode == "shake" else ["--teleop-offset"] if mode == "invalid_offset" else [])), \
                patch.object(steady, "read_sessions", lambda: read_sessions(history)), \
                patch.object(steady, "save_sessions", lambda values: save_sessions(values, history)), \
                patch.object(steady, "OFFSETS", offsets), patch.object(steady, "OUT", Path(temporary) / "out"), \
                patch.object(steady, "USERS", Path(temporary) / "users.json"), \
                patch.object(steady, "Fingertip", lambda: tip), patch.object(steady, "time", clock), \
                patch.object(steady.socketserver, "ThreadingTCPServer", server), \
                patch.object(steady, "HTTPServer", server), \
                patch.object(steady.threading, "Thread", lambda *args, **kwargs: SimpleNamespace(start=lambda: None)), \
                patch.dict(steady.state, steady=True, hold=False, cutoff=2.0, quit=False):
            try:
                steady.main()
            except (ConnectionError, ValueError):
                if mode not in ("read_failure", "link_deadline", "send_deadline", "invalid_offset", "invalid_calibration", "invalid_follower"):
                    raise
    if mode in ("link_deadline", "send_deadline"):
        cleanup.append(("elapsed", now[0] - failure_started[0]))
    return writes, cleanup


def test_stop_during_read():
    writes, _ = scenario("stop_during_read")
    assert len(writes) < 2 or writes[1][1] == writes[0][1], ("new target after stop", writes)


def test_hold_during_ease():
    writes, _ = scenario("hold_during_ease")
    assert len(writes) < 3 or writes[2][1] == writes[1][1], ("hold changed target", writes)


def test_spoken_off():
    writes, _ = scenario("spoken_off")
    assert len(writes) < 2 or (writes[1][0] and writes[1][1] == writes[0][1]), writes


def test_failure_cleanup():
    _, cleanup = scenario("read_failure")
    assert ("follower", True) not in cleanup, ("unconfirmed torque-off after read failure", cleanup)


def test_stop_during_retry():
    writes, _ = scenario("stop_during_retry")
    assert len(writes) < 2 or writes[1][1] == writes[0][1], ("pending target retried after stop", writes)


def test_link_deadline():
    _, cleanup = scenario("link_deadline")
    elapsed = next(value for key, value in cleanup if key == "elapsed")
    assert elapsed <= steady.LINK_WAIT_S + .5, ("read time excluded from recovery deadline", elapsed)


def test_send_deadline():
    _, cleanup = scenario("send_deadline")
    elapsed = next(value for key, value in cleanup if key == "elapsed")
    assert elapsed <= steady.LINK_WAIT_S + .5, ("send failures have no recovery deadline", elapsed)


def test_hold_recovery():
    writes, _ = scenario("hold_recovery")
    assert len(writes) == 3 and all(action == writes[0][1] for _, action in writes), (
        "recovery replaced held target", writes)


def test_invalid_offset():
    writes, _ = scenario("invalid_offset")
    assert not writes, ("invalid offset reached send_action", writes)


def test_invalid_calibration():
    writes, _ = scenario("invalid_calibration")
    assert not writes, ("invalid calibration reached send_action", writes)


def test_load_failure():
    writes, _ = scenario("load_failure")
    assert len(writes) == 7, "load-only failure stopped following"
    assert steady.shared["grip_effort"] == 100.0, "last load reading was not retained"


def test_meter_timestamps():
    scenario("slow_meter")  # Six-Hz input sampled at 25 Hz, not the nominal 50 Hz.
    assert abs(steady.shared["tremor_hz"] - 6) < .3, ("six-Hz input reported as", steady.shared["tremor_hz"])


def test_invalid_follower():
    writes, _ = scenario("invalid_follower")
    assert not writes, ("invalid initial follower reading reached send_action", writes)


def test_hold_grip():
    writes, _ = scenario("hold_grip")
    assert len(writes) < 3 or writes[2][1] == writes[1][1], ("held grip target changed", writes)


def test_hold_roll():
    writes, _ = scenario("hold_roll")
    assert len(writes) == 3 and writes[2][0] and steady.shared["roll_follows"] is False
    assert writes[1][1]["wrist_roll.pos"] == 0 and writes[2][1]["wrist_roll.pos"] == 20
    assert all(writes[2][1][key] == writes[1][1][key] for key in steady.KEYS if key != "wrist_roll.pos"), writes


def test_roll_no_follow():
    writes, _ = scenario("roll_no_follow")
    assert writes and all(action["wrist_roll.pos"] == 0 for _, action in writes)


def test_hold_roll_enabled():
    with patch.object(steady, "ROLL_FOLLOWS", True):
        writes, _ = scenario("hold_roll")
    assert len(writes) == 3 and steady.shared["roll_follows"] is True
    assert writes[2][1] == writes[1][1], writes


def test_torque_limit():
    _, cleanup = scenario("torque_limit")
    registers = [entry for entry in cleanup if entry[0] == "register"]
    assert registers == [("register", ("Torque_Limit", dict.fromkeys(steady.JOINTS[:5], 600)),
                          {"normalize": False, "num_retry": 5})], registers


def test_shake():
    writes, _ = scenario("shake")
    assert writes and all(math.isfinite(value) for _, action in writes for value in action.values())


def test_meter_warmup():
    scenario("meter_warmup")
    assert steady.shared["tremor_hz"] == 0 or abs(steady.shared["tremor_hz"] - 6) < .3, steady.shared["tremor_hz"]


def test_latch_start():
    writes, _ = scenario("latch_start")
    assert all(action["gripper.pos"] == steady.GRIP_FLOOR for _, action in writes), (
        "latch opens a previously closed claw without a squeeze", writes)


if __name__ == "__main__":
    normal, _ = scenario("normal")
    assert normal and all(math.isfinite(value) for _, action in normal for value in action.values())
    print("finite normal-loop control passes")
    failures = []
    for test in (test_stop_during_read, test_hold_during_ease, test_failure_cleanup, test_invalid_offset,
                 test_meter_timestamps, test_invalid_follower, test_hold_grip, test_shake, test_meter_warmup,
                 test_spoken_off, test_latch_start, test_invalid_calibration, test_load_failure,
                 test_hold_roll, test_roll_no_follow, test_hold_roll_enabled, test_torque_limit,
                 test_stop_during_retry, test_link_deadline, test_hold_recovery, test_send_deadline):
        try:
            test()
            print("PASS", test.__name__)
        except (AssertionError, NameError) as error:
            failures.append(test.__name__)
            print("FAIL", test.__name__, error)
    assert not failures, failures
