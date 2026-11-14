"""Fake arm and stop only: python -B -m tests.test_hand_boundaries."""
from types import SimpleNamespace

from skills import hand


def check(do, occupied=True, fail_at=None, stop_at=None):
    calls, waits = [], []
    position = [0, 0, 0, 0, 0, 20]

    def move(joints, seconds):
        calls.append((list(joints), seconds))
        position[:] = joints
        return len(calls) != fail_at

    def wait(seconds):
        waits.append(seconds)
        return len(waits) == stop_at

    def reading():
        return position[:5] + ([16 if occupied else 5] if position[5] == hand.CLOSED else position[5:])

    arm = SimpleNamespace(load_pose=lambda name: ([10] * 5 + [20]) if name == "handover" else [0] * 5 + [20],
                          get_joints=reading, move_joints=move)
    result = hand.run(arm, {"do": do, "wait": 0}, SimpleNamespace(wait=wait))
    return result, calls, waits


def test_hand():
    for do, grips in (("take", [60, 0, 0]), ("give", [0, 60, 20]), ("drop", [60])):
        result, calls, _ = check(do)
        assert result["ok"] and [joints[5] for joints, _ in calls] == grips
        assert result["holding"] == (do == "take")
        for fail_at in range(1, len(calls) + 1):
            result, stopped, _ = check(do, fail_at=fail_at)
            assert result == hand.STOPPED and len(stopped) == fail_at
    result, calls, _ = check("take", occupied=False)
    assert not result["ok"] and not result["holding"]
    assert [joints[5] for joints, _ in calls] == [60, 0, 60, 20]
    for do in ("take", "give"):
        for stop_at in (1, 2):
            result, calls, waits = check(do, stop_at=stop_at)
            assert result == hand.STOPPED and len(calls) == stop_at and len(waits) == stop_at
    forbidden = SimpleNamespace(load_pose=lambda name: (_ for _ in ()).throw(AssertionError("bad input accessed pose")))
    for params in ({}, {"do": "bad"}, {"do": []}, {"do": "take", "wait": True},
                   {"do": "take", "wait": float("nan")}, {"do": "give", "wait": float("inf")},
                   {"do": "drop", "wait": -1}, {"do": "take", "wait": 21}):
        assert not hand.run(forbidden, params, None)["ok"]


if __name__ == "__main__":
    test_hand()
    print("hand boundaries ok")
