"""Arm API from newcontext.md section 5: the real SO-101 follower, or a mock that only logs.

    from core.arm import get_arm
    arm = get_arm(mock=True)

Joints are 6 numbers in JOINTS order: degrees, except the gripper, which is 0 (closed) to 100 (open).
The real arm wraps the helpers in the root arm.py, so pick.py and draw.py keep working.
Creating the real arm switches its motors on. Poses are taught by hand with `python arm.py pose <name>`.
"""
import json
import math
import os
import threading
from pathlib import Path

JOINTS = ["shoulder_pan", "shoulder_lift", "elbow_flex", "wrist_flex", "wrist_roll", "gripper"]
HZ = 30
POSES = Path(__file__).parent.parent / "poses"
TAP_SECONDS = float(os.environ.get("TAP_SECONDS", "0.08"))  # how long a tap holds the key down
# Tapping works from ONE taught pose, tap_key: the fingertip resting on the key. The arm hovers
# LIFT_DEG above it (elbow raised) and a press comes back down to it. It never goes below the taught
# pose unless PRESS_DEG is positive; make PRESS_DEG negative if the powered arm sags and presses too hard.
# ponytail: degrees of elbow, not millimetres (1 degree is roughly 3 mm at the tip). IK replaces it.
LIFT_DEG = float(os.environ.get("LIFT_DEG", "3.0"))
PRESS_DEG = float(os.environ.get("PRESS_DEG", "0.0"))
ELBOW = 2  # index of elbow_flex in JOINTS; a bigger angle lowers the forearm


def _checked(joints) -> list[float]:
    """Six finite numbers, or ValueError. Every command to the motors passes through here."""
    joints = list(joints)
    if len(joints) != 6 or not all(type(v) in (int, float) and math.isfinite(v) for v in joints):
        raise ValueError(f"need 6 finite joint values, got {joints}")
    return [float(v) for v in joints]


class MockArm:
    """Same methods as the real arm. Keeps the joints in memory and moves nothing."""

    REAL = False

    def __init__(self):
        self.halt = threading.Event()  # set by stop(); every move checks it
        self.lift_deg, self.press_deg = LIFT_DEG, PRESS_DEG
        self._joints = [0.0] * 6

    def _read(self) -> list[float]:
        return list(self._joints)

    def _write(self, joints: list[float]) -> None:
        self._joints = list(joints)

    def load_pose(self, name: str) -> list[float]:
        path = POSES / f"{name}.json"
        if not path.exists():
            if not self.REAL:
                return [0.0] * 6
            raise FileNotFoundError(f"No pose '{name}'. Teach it: python arm.py pose {name}")
        pose = json.loads(path.read_text())
        return _checked(pose[f"{j}.pos"] for j in JOINTS)

    def get_joints(self) -> list[float]:
        return self._read()

    def move_joints(self, joints_deg: list[float], duration_s: float) -> bool:
        """Glide to joints_deg. Returns False if stop() cut it short. Bad input raises before any motion."""
        target = _checked(joints_deg)
        if type(duration_s) not in (int, float) or not 0 <= duration_s <= 30:
            raise ValueError(f"duration must be 0 to 30 seconds, got {duration_s}")
        start = self._read()
        steps = max(1, int(duration_s * HZ))
        for i in range(1, steps + 1):
            if self.halt.is_set():
                return False
            self._write(_checked(a + (b - a) * i / steps for a, b in zip(start, target)))
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

    def set_tap(self, lift_deg=None, press_deg=None) -> None:
        """Change how high the tip hovers and how far a press goes. Raises before changing anything."""
        lift = self.lift_deg if lift_deg is None else lift_deg
        press = self.press_deg if press_deg is None else press_deg
        if type(lift) not in (int, float) or not 0.5 <= lift <= 20:
            raise ValueError("lift_deg must be 0.5 to 20 degrees")
        if type(press) not in (int, float) or not -5 <= press <= 5:
            raise ValueError("press_deg must be -5 to 5 degrees")
        self.lift_deg, self.press_deg = float(lift), float(press)

    def key_pose(self, lower_deg: float) -> list[float]:
        """The taught tap_key pose with the elbow lower_deg lower (negative = raised)."""
        pose = self.load_pose("tap_key")
        pose[ELBOW] += lower_deg
        return pose

    def hover_pose(self) -> list[float]:
        return self.key_pose(-self.lift_deg)

    def press(self) -> bool:
        """Come down onto the key. One command, for tight timing."""
        return self._jump(self.press_deg)

    def release(self) -> bool:
        """Lift back to the hover height."""
        return self._jump(-self.lift_deg)

    def _jump(self, lower_deg: float) -> bool:
        if self.halt.is_set():
            return False
        self._write(self.key_pose(lower_deg))
        return True

    def tap(self, depth_mm: float = 3.0) -> bool:
        # ponytail: depth_mm is ignored until there is IK; the stroke is lift_deg and press_deg.
        return self.press() and not self.halt.wait(TAP_SECONDS) and self.release()

    def play(self, trajectory) -> bool:
        """trajectory: list of (time_s, joints_deg), times rising. Returns False if stopped.
        The whole trajectory is checked before the first move."""
        points = [(float(t), _checked(joints)) for t, joints in trajectory]
        times = [t for t, _ in points]
        if not points or not all(math.isfinite(t) and t >= 0 for t in times) or times != sorted(times):
            raise ValueError("trajectory needs at least one point and rising, finite times")
        if not self.move_joints(points[0][1], 2.0):
            return False
        last = times[0]
        for t, joints in points:
            if self.halt.wait(t - last):
                return False
            last = t
            self._write(joints)
        return True

    def stop(self) -> None:
        """Hold position now: moves stop sending, the motors keep holding the last target."""
        self.halt.set()

    def close(self, release: bool = True) -> None:
        pass


class Arm(MockArm):
    REAL = True

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

    def close(self, release: bool = True) -> None:
        """Close the serial port. Never moves. release=True switches the motors off, so the arm
        drops unless it is resting or held; release=False leaves them on and holding.
        The flag is set on the robot itself because LeRobot also disconnects when the object is
        garbage collected, and that path must not release the motors either."""
        self._robot.config.disable_torque_on_disconnect = release
        self._robot.disconnect()


def get_arm(mock: bool = False) -> MockArm:
    return MockArm() if mock else Arm()
