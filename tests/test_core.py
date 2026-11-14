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
                         "tap_up": [10, -20, 40, 70, 0, 0]}.items():
        (core.arm.POSES / f"{name}.json").write_text(json.dumps({f"{j}.pos": v for j, v in zip(JOINTS, joints)}))
    arm = get_arm(mock=True)
    dispatcher.load(arm)
    names = {s["name"] for s in dispatcher.list_skills()}
    assert {"wave", "gd_tap"} <= names

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
    arm._write([0, 0, 0, 10, 0, 0])
    assert arm.tap(3.0) and abs(arm.get_joints()[3] - 10) < 1e-6

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


if __name__ == "__main__":
    test_core()
    print("core ok")
