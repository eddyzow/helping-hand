"""Personality moves: nod, shake, celebrate, droop, dance. Small wiggles around the taught wave_up pose.

    run personality {"move": "nod"}        # typed at the dispatcher
    python -m skills.personality           # self-check on a fake arm, no hardware

UNTESTED ON HARDWARE. Every number below is a guess made on the mock arm: the sign of each joint
(does +wrist_flex tip the gripper down or up?) and the clearance around wave_up have to be checked
on the real arm with Daniel, one move at a time, with someone on the stop key. Tune the tables here.
"""
NAME = "personality"
DESCRIPTION = "Show a reaction: nod (yes), shake (no), celebrate (success), droop (sad), dance"
PARAMS = {"move": "nod | shake | celebrate | droop | dance"}

PAN, LIFT, ELBOW, WRIST_FLEX, WRIST_ROLL, GRIPPER = range(6)
MAX_OFFSET_DEG = 35  # no step may ask a joint to leave wave_up by more than this
STOPPED = {"ok": False, "reason": "stopped"}

# Each move is a list of steps: ({joint: offset from wave_up}, seconds). Gripper offsets are on its 0-100 scale.
# A step with the same offsets as the one before it is a hold.
MOVES = {
    "nod": [({WRIST_FLEX: 18}, 0.3), ({WRIST_FLEX: -8}, 0.3)] * 3,
    "shake": [({PAN: 12}, 0.3), ({PAN: -12}, 0.3)] * 3,
    "celebrate": [({WRIST_FLEX: -20, GRIPPER: 30}, 0.3), ({WRIST_FLEX: 0, GRIPPER: -30}, 0.3)] * 4,
    "droop": [({WRIST_FLEX: 35, GRIPPER: -30}, 1.5), ({WRIST_FLEX: 35, GRIPPER: -30}, 1.0)],
    # no wrist_roll in any move: that motor was reported overheating on Sat Nov 14 (notes/daniel.md)
    "dance": [({PAN: 10, WRIST_FLEX: 12}, 0.4), ({PAN: -10, WRIST_FLEX: -12}, 0.4)] * 4,
}


def targets(base: list[float], move: str) -> list[tuple[list[float], float]]:
    """The joint targets for a move, gripper kept inside 0-100."""
    out = []
    for offsets, seconds in MOVES[move]:
        target = list(base)
        for joint, delta in offsets.items():
            target[joint] += delta
        target[GRIPPER] = min(max(target[GRIPPER], 0.0), 100.0)
        out.append((target, seconds))
    return out


def run(arm, params, stop):
    move = params.get("move", "nod")
    if move not in MOVES:  # checked before the first motion
        return {"ok": False, "reason": f"unknown move '{move}': use one of {', '.join(MOVES)}"}
    base = arm.load_pose("wave_up")
    if not (arm.home() and arm.move_joints(base, 1.5)):
        return STOPPED
    for target, seconds in targets(base, move):
        if not arm.move_joints(target, seconds):
            return STOPPED
    if not (arm.move_joints(base, 0.4) and arm.home()):
        return STOPPED
    return {"ok": True, "reason": ""}


if __name__ == "__main__":
    from core.arm import MockArm

    class FakeArm(MockArm):  # records each commanded target and jumps there, so the check is instant
        def __init__(self, stop_after=None):
            super().__init__()
            self.sent, self.stop_after = [], stop_after

        def move_joints(self, joints_deg, duration_s):
            if self.halt.is_set():
                return False
            self.sent.append(list(joints_deg))
            self._joints = list(joints_deg)
            if self.stop_after is not None and len(self.sent) >= self.stop_after:
                self.halt.set()
            return not self.halt.is_set()

    for name in MOVES:
        arm = FakeArm()
        base, home = arm.load_pose("wave_up"), arm.load_pose("home")
        assert run(arm, {"move": name}, arm.halt) == {"ok": True, "reason": ""}, name
        assert arm.sent[0] == home and arm.sent[-1] == home, f"{name} must start and end at home"
        for target in arm.sent[1:-1]:
            assert all(abs(t - b) <= MAX_OFFSET_DEG for t, b in zip(target, base)), (name, target)
            assert 0 <= target[GRIPPER] <= 100, (name, target)

    arm = FakeArm()
    assert not run(arm, {"move": "moonwalk"}, arm.halt)["ok"] and arm.sent == [], "bad move must not move the arm"
    assert run(FakeArm(), {}, FakeArm().halt)["ok"], "no params means nod"

    arm = FakeArm(stop_after=4)  # stop lands mid-move: nothing more is sent, and no homing afterwards
    assert run(arm, {"move": "dance"}, arm.halt) == STOPPED and len(arm.sent) == 4
    print("personality ok")
