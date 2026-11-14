"""Dispatcher and skills against the mock arm. Run: python -m tests.test_core  (or pytest)"""
import time

from core import dispatcher
from core.arm import get_arm
from voice.route import by_keyword


def test_core():
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
    assert not dispatcher._worker.is_alive() and arm.get_joints() == arm.load_pose("home")

    # a tap goes down and comes back
    arm._write([0, 0, 0, 10, 0, 0])
    assert arm.tap(3.0) and arm.get_joints()[3] == 10

    skills = dispatcher.list_skills()
    assert by_keyword("please wave at me", skills) == {"skill": "wave"}
    assert by_keyword("STOP now", skills) == {"skill": "stop"}
    assert by_keyword("make me a sandwich", skills) == {"skill": None}


if __name__ == "__main__":
    test_core()
    print("core ok")
