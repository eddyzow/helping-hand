"""Arm API from newcontext.md section 5: the real SO-101 follower, or a mock that only logs.

    from core.arm import get_arm
    arm = get_arm(mock=True)

Joints are 6 numbers in JOINTS order: degrees, except the gripper, which is 0 (closed) to 100 (open).
The real arm wraps the helpers in the root arm.py, so pick.py and draw.py keep working.
Creating the real arm switches its motors on. Poses are taught by hand with `python arm.py pose <name>`.
"""
import json
import os
import threading
from pathlib import Path

JOINTS = ["shoulder_pan", "shoulder_lift", "elbow_flex", "wrist_flex", "wrist_roll", "gripper"]
HZ = 30
POSES = Path(__file__).parent.parent / "poses"
# ponytail: a tap is a wrist_flex nudge, not a real depth. Tune on the real key (negative flips the
# direction); inverse kinematics replaces it in phase 2.
TAP_DEG_PER_MM = float(os.environ.get("TAP_DEG_PER_MM", "1.0"))
TAP_SECONDS = float(os.environ.get("TAP_SECONDS", "0.08"))


class MockArm:
    """Same methods as the real arm. Keeps the joints in memory and moves nothing."""

    def __init__(self):
        self.halt = threading.Event()  # set by stop(); every move checks it
        self._joints = [0.0] * 6

    def _read(self) -> list[float]:
        return list(self._joints)

    def _write(self, joints: list[float]) -> None:
        self._joints = list(joints)

    def load_pose(self, name: str) -> list[float]:
        path = POSES / f"{name}.json"
        if not path.exists():
            if type(self) is MockArm:
                return [0.0] * 6
            raise FileNotFoundError(f"No pose '{name}'. Teach it: python arm.py pose {name}")
        pose = json.loads(path.read_text())
        return [float(pose[f"{j}.pos"]) for j in JOINTS]

    def get_joints(self) -> list[float]:
        return self._read()

    def move_joints(self, joints_deg: list[float], duration_s: float) -> bool:
        """Glide to joints_deg. Returns False if stop() cut it short."""
        start = self._read()
        steps = max(1, int(duration_s * HZ))
        for i in range(1, steps + 1):
            if self.halt.is_set():
                return False
            self._write([a + (b - a) * i / steps for a, b in zip(start, joints_deg)])
            self.halt.wait(1 / HZ)
        return not self.halt.is_set()

    def home(self) -> bool:
        return self.move_joints(self.load_pose("home"), 2.0)

    def move_to(self, x_mm, y_mm, z_mm, duration_s):
        raise NotImplementedError("phase 2: needs inverse kinematics")

    def gripper(self, open_fraction: float) -> bool:
        joints = self._read()
        joints[5] = 100 * min(max(open_fraction, 0.0), 1.0)
        return self.move_joints(joints, 0.4)

    def tap(self, depth_mm: float = 3.0) -> bool:
        up = self._read()
        down = list(up)
        down[3] += depth_mm * TAP_DEG_PER_MM
        return self.move_joints(down, TAP_SECONDS) and self.move_joints(up, TAP_SECONDS)

    def play(self, trajectory) -> bool:
        """trajectory: list of (time_s, joints_deg). Returns False if stopped."""
        if not trajectory or not self.move_joints(trajectory[0][1], 2.0):
            return False
        last = 0.0
        for t, joints in trajectory:
            if self.halt.wait(max(0.0, t - last)):
                return False
            last = t
            self._write(joints)
        return True

    def stop(self) -> None:
        """Hold position now: moves stop sending, the motors keep holding the last target."""
        self.halt.set()

    def close(self) -> None:
        pass


class Arm(MockArm):
    def __init__(self):
        if not (POSES / "home.json").exists():
            # without a resting home pose, switching the motors off drops the arm from mid-air
            raise FileNotFoundError("Teach a resting home pose first: python arm.py pose home")
        super().__init__()
        import arm as root_arm  # the root arm.py

        self._robot = root_arm.follower()  # connects: motors switch on and hold

    def _read(self) -> list[float]:
        obs = self._robot.get_observation()
        return [float(obs[f"{j}.pos"]) for j in JOINTS]

    def _write(self, joints: list[float]) -> None:
        self._robot.send_action({f"{j}.pos": v for j, v in zip(JOINTS, joints)})

    def close(self) -> None:
        """Go home, then switch the motors off."""
        self.halt.clear()
        try:
            self.home()
        finally:
            self._robot.disconnect()


def get_arm(mock: bool = False) -> MockArm:
    return MockArm() if mock else Arm()
