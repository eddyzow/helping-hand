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
    core.arm.POSES = Path(tempfile.mkdtemp())
    for name, joints in {"home": [0, -100, 90, 60, 0, 0], "wave_up": [0, -30, 20, 0, 0, 80],
                         "tap_key": [10, -20, 40, 70, 0, 0]}.items():
        (core.arm.POSES / f"{name}.json").write_text(json.dumps({f"{j}.pos": v for j, v in zip(JOINTS, joints)}))
    arm = get_arm(mock=True)
    dispatcher.load(arm)
    names = {s["name"] for s in dispatcher.list_skills()}
    assert {"wave", "gd_tap", "geometry_dash"} <= names

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
    dispatcher._worker.join(10)
    assert not dispatcher._worker.is_alive() and close(arm.get_joints(), arm.load_pose("home"))

    # a tap goes down and comes back
    hover = [10, -20, 37, 70, 0, 0]                            # tap_key with the elbow raised 3 degrees
    assert arm.tap(3.0) and close(arm.get_joints(), hover)
    pressed = arm.load_pose("tap_key")                         # a press comes down to the taught pose, no lower
    assert arm.press() and close(arm.get_joints(), pressed)
    assert dispatcher.handle('run wave {"roll": 999}')["ok"] is True  # refused inside the skill, before motion
    dispatcher._worker.join(2)
    assert close(arm.get_joints(), pressed)
    assert dispatcher.handle('run gd_tap {"press_deg": 50}')["ok"] is True  # too deep: refused, no motion
    dispatcher._worker.join(2)
    assert close(arm.get_joints(), pressed) and arm.press_deg == 0.0
    assert dispatcher.handle('run gd_tap {"lift_deg": 0}')["ok"] is True     # no hover height: refused
    dispatcher._worker.join(2)
    assert close(arm.get_joints(), pressed) and arm.lift_deg == 3.0

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

    skills = dispatcher.list_skills()
    assert by_keyword("please wave at me", skills) == {"skill": "wave"}
    assert by_keyword("STOP now", skills) == {"skill": "stop"}
    assert by_keyword("make me a sandwich", skills) == {"skill": None}


def test_cli_cue():
    """Started the real way (python -m core.dispatcher), the cue typed or sent must reach the skill."""
    import os
    import socket
    import subprocess
    import sys

    def ask(line):
        with socket.create_connection(("127.0.0.1", 8799), timeout=2) as s:
            s.sendall((line + "\n").encode())
            return json.loads(s.makefile().readline())

    proc = subprocess.Popen([sys.executable, "-u", "-m", "core.dispatcher", "--mock"], stdin=subprocess.PIPE,
                            stdout=subprocess.PIPE, text=True, env={**os.environ, "BUDDY_PORT": "8799"})
    try:
        assert "Listening" in proc.stdout.readline()
        assert ask('run geometry_dash {"pattern": "demo_taps.csv", "first_taps": 1}')["ok"] is True
        for _ in range(100):
            if ask("ready")["ok"]:
                break
            time.sleep(0.1)
        assert ask("ready")["ok"] is True
        assert ask("cue")["ok"] is True
        line = ""
        while "[geometry_dash] {" not in line:
            line = proc.stdout.readline()
            assert line, "dispatcher exited before the replay finished"
        assert "'ok': True" in line, line
    finally:
        proc.stdin.close()
        proc.wait(10)


if __name__ == "__main__":
    test_core()
    test_cli_cue()
    print("core ok")
