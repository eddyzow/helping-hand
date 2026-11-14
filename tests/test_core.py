"""Dispatcher and skills against the mock arm. Run: python -m tests.test_core  (or pytest)"""
import json
import tempfile
import time
from pathlib import Path

import core.arm
from core import dispatcher
from core.arm import JOINTS, get_arm
from voice.route import by_keyword


def close(a, b):
    return all(abs(x - y) < 1e-6 for x, y in zip(a, b))


def test_core():
    # the same made-up poses on every machine, whatever is taught in the real poses/ folder
    core.arm.TAP_JOINT = 2                                     # these tests tap with the elbow (index 2)
    core.arm.POSES = Path(tempfile.mkdtemp())
    for name, joints in {"home": [0, -100, 90, 60, 0, 0], "wave_up": [0, -30, 20, 0, 0, 80],
                         "tap_key": [10, -20, 40, 70, 0, 30]}.items():
        (core.arm.POSES / f"{name}.json").write_text(json.dumps({f"{j}.pos": v for j, v in zip(JOINTS, joints)}))
    arm = get_arm(mock=True)
    dispatcher.load(arm)
    names = {s["name"] for s in dispatcher.list_skills()}
    assert {"wave", "gd_tap", "geometry_dash", "tap_calibrate", "tap_place"} <= names

    assert dispatcher.dispatch("nope")["ok"] is False
    assert dispatcher.handle("run wave {bad json")["reason"] == "params must be JSON"

    # one skill at a time
    assert dispatcher.dispatch("wave")["ok"] is True
    assert dispatcher.dispatch("gd_tap")["reason"] == "busy"

    # stop interrupts a running skill within half a second, and the arm holds where it was
    time.sleep(0.5)
    t0 = time.time()
    dispatcher.stop_all()
    dispatcher._worker.join(1)
    assert not dispatcher._worker.is_alive() and time.time() - t0 < 0.5
    held = arm.get_joints()
    time.sleep(0.1)
    assert arm.get_joints() == held

    # after a stop the next skill runs to the end and finishes at home
    assert dispatcher.handle('run gd_tap {"times": 2, "gap_s": 0.05}')["ok"] is True
    dispatcher._worker.join(25)
    assert not dispatcher._worker.is_alive() and close(arm.get_joints(), arm.load_pose("home"))

    # a tap goes down and comes back
    hover = [10, -20, 37, 70, 0, 30]                           # tap_key with the elbow raised 3 degrees
    assert arm.tap(3.0) and close(arm.get_joints(), hover)
    pressed = arm.load_pose("tap_key")                         # a press comes down to the saved pose, no further
    assert arm.press() and close(arm.get_joints(), pressed)
    assert dispatcher.handle('run wave {"roll": 999}')["ok"] is True  # refused inside the skill, before motion
    dispatcher._worker.join(2)
    assert close(arm.get_joints(), pressed)
    assert dispatcher.handle('run gd_tap {"press": 50}')["ok"] is True  # too deep: refused, no motion
    dispatcher._worker.join(2)
    assert close(arm.get_joints(), pressed) and arm.press_extra == 0.0
    assert dispatcher.handle('run gd_tap {"lift": 0}')["ok"] is True     # no lift: refused
    dispatcher._worker.join(2)
    assert close(arm.get_joints(), pressed) and arm.lift == 3.0

    # Geometry Dash replay: waits for the cue, then presses and releases on the recording's clock
    log = []
    real_write = arm._write
    arm._write = lambda joints: (log.append((time.perf_counter(), joints[2])), real_write(joints))
    assert dispatcher.handle("ready")["ok"] is False
    assert dispatcher.handle('run geometry_dash {"pattern": "demo_taps.csv", "first_taps": 2}')["ok"] is True
    for _ in range(100):                                        # home, approach, then it waits
        if dispatcher.handle("ready")["ok"]:
            break
        time.sleep(0.1)
    assert dispatcher.handle("ready")["ok"] is True and dispatcher._worker.is_alive()
    log.clear()
    t0 = time.perf_counter()
    assert dispatcher.handle("cue")["ok"] is True
    dispatcher._worker.join(8)
    assert not dispatcher._worker.is_alive() and dispatcher.handle("ready")["ok"] is False
    presses = [(round(t - t0, 2), elbow) for t, elbow in log[:4]]
    assert [e for _, e in presses] == [40, 37, 40, 37], presses          # down, up, down, up
    assert all(abs(t - want) < 0.06 for (t, _), want in zip(presses, (0.30, 0.38, 0.68, 0.76))), presses
    arm._write = real_write
    before_gd = arm.get_joints()
    late = '{"pattern": "demo_taps.csv", "first_taps": 1, "press_lead_ms": 1000, "release_lead_ms": 1000}'
    assert dispatcher.handle(f"run geometry_dash {late}")["ok"] is True
    dispatcher._worker.join(2)                                 # a press before the cue is refused, no motion
    assert not dispatcher._worker.is_alive() and arm.get_joints() == before_gd
    assert dispatcher.handle('run geometry_dash {"pattern": "../../see.py"}')["ok"] is True
    dispatcher._worker.join(2)
    assert not dispatcher._worker.is_alive()                   # refused at once, no motion, no waiting

    # bad input is refused before anything moves
    arm.halt.clear()
    before = arm.get_joints()
    for call, bad in ([arm.move_joints, ([1.0], 0.1)], [arm.move_joints, ([float("nan")] * 6, 0.1)],
                      [arm.move_joints, ([0, 0, 0, 0, 0, "x"], 0.1)], [arm.move_joints, ([0] * 6, float("inf"))],
                      [arm.play, ([(0, [0] * 6), (1, [0] * 5)],)], [arm.play, ([(1, [0] * 6), (0, [0] * 6)],)],
                      [arm.play, ([],)]):
        try:
            call(*bad)
            raise AssertionError(f"accepted {bad}")
        except ValueError:
            pass
    assert arm.get_joints() == before
    assert dispatcher.handle("run wave [1, 2]")["reason"] == "params must be a JSON object"
    from skills import gd_tap
    for bad in ({"times": "many"}, {"times": 0}, {"gap_s": float("inf")}, {"gap_s": -1}):
        assert gd_tap.run(arm, bad, arm.halt)["ok"] is False and arm.get_joints() == before

    # stop then shutdown never moves the arm and never restarts the skill
    calls = []

    class Spy(type(arm)):
        REAL = True  # shutdown treats it as a real arm

        def _write(self, joints):
            calls.append("write")
            super()._write(joints)

        def close(self, release=True):
            calls.append(("close", release))

    spy = Spy()
    dispatcher.load(spy)
    assert dispatcher.dispatch("wave")["ok"]
    time.sleep(0.3)
    assert "write" in calls                                  # the skill really was moving
    dispatcher.stop_all()
    dispatcher._worker.join(1)
    calls.clear()

    def confirm(prompt):  # a command arriving while the operator holds the arm must be refused
        asked.append(prompt)
        assert dispatcher.handle("home")["reason"] == "shutting down"
        assert dispatcher.handle("run wave")["reason"] == "shutting down"

    asked = []
    dispatcher.shutdown(confirm=confirm)
    assert spy.halt.is_set() and calls == [("close", True)], calls  # no move between stop and motors off
    assert len(asked) == 1                                   # the operator is asked to hold the arm first

    # no confirmation (closed input, Ctrl+C): the motors stay on, nothing is released
    def no_answer(prompt):
        raise EOFError

    dispatcher.load(spy)
    calls.clear()
    dispatcher.shutdown(confirm=no_answer)
    assert calls == [("close", False)], calls

    # the real Arm.close(release=False) tells LeRobot not to cut torque, on this and any later disconnect
    from types import SimpleNamespace

    class FakeRobot:
        config = SimpleNamespace(disable_torque_on_disconnect=True)
        log = []

        def disconnect(self):
            self.log.append(self.config.disable_torque_on_disconnect)

    real = core.arm.Arm.__new__(core.arm.Arm)
    real._robot = FakeRobot()
    real.close(release=False)
    real._robot.disconnect()  # what LeRobot's destructor does later
    assert FakeRobot.log == [False, False], FakeRobot.log

    dispatcher.load(arm)
    assert dispatcher.handle("home")["ok"] is True           # homing is its own operator command
    dispatcher._worker.join(5)

    # a bad tap default from the environment is refused when the arm is created, not at the first press
    for name, bad in (("PRESS", float("nan")), ("PRESS", 50.0), ("LIFT", float("nan")), ("LIFT", 0.0)):
        good = getattr(core.arm, name)
        setattr(core.arm, name, bad)
        try:
            get_arm(mock=True)
            raise AssertionError(f"accepted {name}={bad}")
        except ValueError:
            pass
        finally:
            setattr(core.arm, name, good)
    odd = get_arm(mock=True)
    odd.press_extra = float("nan")                               # even set behind the setter's back
    try:
        odd.press()
        raise AssertionError("pressed with a NaN depth")
    except ValueError:
        assert odd.get_joints() == [0.0] * 6

    # tap_calibrate: a pretend key that registers at elbow 41.0 and lets go below 40.6
    from core import key_down

    def write_with_key(joints):
        real_write(joints)
        if joints[2] >= 41.0:
            key_down.set()
        elif joints[2] < 40.6:
            key_down.clear()

    arm._write = write_with_key
    assert dispatcher.handle("key down")["ok"] and key_down.is_set()      # what the keypad listener sends
    assert dispatcher.handle("key up")["ok"] and not key_down.is_set()
    assert dispatcher.handle("run tap_calibrate")["ok"] is True
    dispatcher._worker.join(60)
    assert not dispatcher._worker.is_alive()
    arm._write = real_write
    saved = json.loads((core.arm.POSES / "tap_key.json").read_text())
    tune = json.loads((core.arm.POSES / "tap_tune.json").read_text())
    assert abs(saved["elbow_flex.pos"] - 41.15) < 0.11, saved      # just past the first registration
    assert saved["shoulder_pan.pos"] == 10 and saved["gripper.pos"] == 30   # nothing else changed
    assert abs(tune["lift"] - 3.15) < 0.25 and arm.lift == tune["lift"], tune   # hovers just above the release
    assert get_arm(mock=True).lift == tune["lift"]                 # the next start loads it
    (core.arm.POSES / "tap_tune.json").unlink()

    # an old or mistyped option is refused before anything runs
    for old_name in ('{"press_deg": -2}', '{"lift_deg": 0}', '{"lfit": 2}'):
        reply = dispatcher.handle(f"run gd_tap {old_name}")
        assert reply["ok"] is False and "no option" in reply["reason"], reply
    assert dispatcher.handle('run home {"x": 1}')["ok"] is False

    # no key ever registers: it gives up, changes nothing, and goes home
    before_file = (core.arm.POSES / "tap_key.json").read_text()
    key_down.clear()                                           # the pretend key ended up 'pressed' at home
    assert dispatcher.handle('run tap_calibrate {"max_travel": 1}')["ok"] is True
    dispatcher._worker.join(60)
    assert (core.arm.POSES / "tap_key.json").read_text() == before_file
    assert not (core.arm.POSES / "tap_tune.json").exists()
    assert close(arm.get_joints(), arm.load_pose("home"))

    # with no key it never commands the tap joint below the rough pose + max_travel
    lowest_seen = []
    rough_pose = arm.load_pose("tap_key")
    rough_elbow = rough_pose[2]
    # creep steps are the rough pose with only the elbow changed; home and the approach glide differ elsewhere
    arm._write = lambda joints: (lowest_seen.append(joints[2]) if joints[:2] + joints[3:] == rough_pose[:2] + rough_pose[3:] else None,
                                 real_write(joints))
    assert dispatcher.handle('run tap_calibrate {"max_travel": 2}')["ok"] is True
    dispatcher._worker.join(60)
    assert lowest_seen and max(lowest_seen) <= rough_elbow + 2 + 1e-6, max(lowest_seen)

    # a stop that lands as the approach ends: not one creep step is written
    import skills.tap_calibrate as cal
    creep_writes = []

    class StopAtKey(type(arm)):
        def to_key(self):
            self.halt.set()                                         # stop arrives exactly here
            return True

        def _write(self, joints):
            creep_writes.append(joints)

    halted = StopAtKey()
    assert cal.run(halted, {}, halted.halt) == cal.STOPPED and creep_writes == []

    # a measured stroke that fails the check leaves the saved calibration alone
    arm._write = write_with_key
    key_down.clear()
    good_set_tap, before_file = arm.set_tap, (core.arm.POSES / "tap_key.json").read_text()

    def reject(lift=None, press=None):
        raise ValueError("pretend stroke out of range")

    arm.set_tap = reject
    assert dispatcher.handle("run tap_calibrate")["ok"] is True
    dispatcher._worker.join(60)
    arm.set_tap, arm._write = good_set_tap, real_write
    assert (core.arm.POSES / "tap_key.json").read_text() == before_file
    assert not (core.arm.POSES / "tap_tune.json").exists()
    key_down.clear()

    # a key that sticks down after calibration's first test press: no success, nothing saved
    state = {"stuck": False}

    def sticky_key(joints):
        real_write(joints)
        if joints[1] != -20:                                       # only near the key, not on the way from home
            return
        if joints[2] >= 41.0:
            if key_down.is_set() is False and state.get("armed"):
                state["stuck"] = True                              # the second time it goes down, it stays
            key_down.set()
            state["armed"] = True
        elif joints[2] < 40.6 and not state["stuck"]:
            key_down.clear()

    arm._write = sticky_key
    before_file = (core.arm.POSES / "tap_key.json").read_text()
    lift_before = arm.lift
    assert dispatcher.handle("run tap_calibrate")["ok"] is True
    dispatcher._worker.join(60)
    arm._write = real_write
    assert dispatcher.handle("status")["last"]["ok"] is False, dispatcher.handle("status")
    assert "stayed down" in dispatcher.handle("status")["last"]["reason"]
    assert (core.arm.POSES / "tap_key.json").read_text() == before_file
    assert not (core.arm.POSES / "tap_tune.json").exists() and arm.lift == lift_before
    key_down.clear()

    # the key first registers just inside the travel limit: the saved press must not go past the limit
    rough_now = arm.load_pose("tap_key")[2]

    def edge_key(joints):
        real_write(joints)
        if joints[2] >= rough_now + 0.88:     # some 0.1 step lands in the last 0.12 before the limit,
            key_down.set()                    # so "registration + PAST" would overshoot it
        elif joints[2] < rough_now + 0.7:
            key_down.clear()

    arm._write = edge_key
    assert dispatcher.handle('run tap_calibrate {"max_travel": 1}')["ok"] is True
    dispatcher._worker.join(60)
    arm._write = real_write
    assert dispatcher.handle("status")["last"]["ok"] is True, dispatcher.handle("status")
    assert json.loads((core.arm.POSES / "tap_key.json").read_text())["elbow_flex.pos"] <= rough_now + 1.0 + 1e-6
    key_down.clear()

    skills = dispatcher.list_skills()
    assert by_keyword("please wave at me", skills) == {"skill": "wave"}
    assert by_keyword("STOP now", skills) == {"skill": "stop"}
    assert by_keyword("make me a sandwich", skills) == {"skill": None}


def test_tap_delay():
    """A pretend key that follows the tap joint 20 ms late: the measured delays come out near 20 ms."""
    import threading

    import skills.tap_delay as delay
    from core import key_down

    core.arm.POSES = Path(tempfile.mkdtemp())
    arm = get_arm(mock=True)
    wrist = core.arm.TAP_JOINT
    real_write = arm._write

    def late_key(joints):
        real_write(joints)
        pressed = joints[wrist] >= -0.01                      # the mock's tap_key pose is all zeros
        threading.Timer(0.02, key_down.set if pressed else key_down.clear).start()

    arm._write = late_key
    key_down.clear()
    result = delay.run(arm, {"times": 5}, arm.halt)
    assert result["ok"] is True, result
    assert 15 <= result["press_ms"] <= 45 and 15 <= result["release_ms"] <= 45, result
    assert delay.run(arm, {"times": 1}, arm.halt)["ok"] is False   # refused before moving
    key_down.clear()


def test_send_waits_for_its_own_result():
    """A failed run must not be reported as ok because a later run by someone else succeeded."""
    from core import send

    core.arm.POSES = Path(tempfile.mkdtemp())      # no poses: the mock uses zeros, everything is instant
    dispatcher.load(get_arm(mock=True))
    real_argv, real_ask, polls = send.sys.argv, send.ask, []

    def fake_transport(line):
        if line == "status" and not polls:         # before the first poll, another client runs a good job
            polls.append(1)
            dispatcher._worker.join(5)
            assert dispatcher.handle("home")["ok"] is True
            dispatcher._worker.join(10)
        return dispatcher.handle(line)

    try:
        send.ask = fake_transport
        send.sys.argv = ["send", "run", "gd_tap", '{"times": 0}']   # refused inside the skill: ok False
        assert send.main() == 1
        send.sys.argv = ["send", "home"]
        assert send.main() == 0
    finally:
        send.sys.argv, send.ask = real_argv, real_ask


def test_cli_cue():
    """Started the real way (python -m core.dispatcher), the cue typed or sent must reach the skill."""
    import os
    import socket
    import subprocess
    import sys

    with socket.socket() as probe:  # any free port, so two test runs at once do not collide
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]

    def ask(line):
        with socket.create_connection(("127.0.0.1", port), timeout=2) as s:
            s.sendall((line + "\n").encode())
            return json.loads(s.makefile().readline())

    proc = subprocess.Popen([sys.executable, "-u", "-m", "core.dispatcher", "--mock"], stdin=subprocess.PIPE,
                            stdout=subprocess.PIPE, text=True, env={**os.environ, "BUDDY_PORT": str(port)})
    try:
        assert "Listening" in proc.stdout.readline()
        assert ask('run geometry_dash {"pattern": "demo_taps.csv", "first_taps": 1}')["ok"] is True
        for _ in range(100):
            if ask("ready")["ok"]:
                break
            time.sleep(0.1)
        assert ask("ready")["ok"] is True
        assert ask("status")["busy"] is True
        assert ask("cue")["ok"] is True
        line = ""
        while "[geometry_dash] {" not in line:
            line = proc.stdout.readline()
            assert line, "dispatcher exited before the replay finished"
        assert "'ok': True" in line, line
        done = ask("status")
        assert done["busy"] is False and done["last"]["skill"] == "geometry_dash" and done["last"]["ok"] is True
    finally:
        proc.stdin.close()
        proc.wait(10)


if __name__ == "__main__":
    test_core()
    test_tap_delay()
    test_send_waits_for_its_own_result()
    test_cli_cue()
    print("core ok")
