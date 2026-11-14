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
# Tapping. tap_key.json is the pose at which the key registers; the tip waits LIFT above it (TAP_JOINT
# raised) and a press comes back down to it, no further unless PRESS is positive.
# You only teach a rough pose with the tip about 1 cm ABOVE the key. `run tap_calibrate` then lowers
# the tip slowly until the keypad itself reports the key, and saves the exact pose and lift, so the
# press is as light as the key allows. Until it has run, a tap stops in the air at the rough pose.
# ponytail: units are TAP_JOINT's (wrist degrees, under 2 mm at the tip each), not millimetres.
# The wrist, as in Jonathan's simulation: it is light, and a bigger wrist angle bends the tip down.
TAP_JOINT = JOINTS.index(os.environ.get("TAP_JOINT", "wrist_flex"))  # the joint that lowers the tip
LIFT = float(os.environ.get("TAP_LIFT", "3.0"))
PRESS = float(os.environ.get("TAP_PRESS", "0.0"))
ELBOW = 2              # index in JOINTS. A bigger elbow angle lowers the forearm.
APPROACH_DEG = 20.0    # the arm arrives and leaves with the elbow raised this much, then comes straight down


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
        self._poses = {}  # poses read once: a file read inside press() cost up to 0.3 s on /mnt/c
        self.lift, self.press_extra = 3.0, 0.0
        self.set_tap(LIFT, PRESS)  # environment defaults pass the same check as live changes
        tune = POSES / "tap_tune.json"  # written by tap_calibrate
        if tune.exists():
            self.set_tap(**json.loads(tune.read_text()))
        self._joints = [0.0] * 6

    def _read(self) -> list[float]:
        return list(self._joints)

    def _write(self, joints: list[float]) -> None:
        self._joints = list(joints)

    def load_pose(self, name: str) -> list[float]:
        if name not in self._poses:
            path = POSES / f"{name}.json"
            if not path.exists():
                if not self.REAL:
                    return [0.0] * 6
                raise FileNotFoundError(f"No pose '{name}'. Teach it: python arm.py pose {name}")
            pose = json.loads(path.read_text())
            self._poses[name] = _checked(pose[f"{j}.pos"] for j in JOINTS)
        return list(self._poses[name])

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

    def home(self, duration_s: float = 2.0) -> bool:
        return self.move_joints(self.load_pose("home"), duration_s)

    def move_to(self, x_mm, y_mm, z_mm, duration_s):
        raise NotImplementedError("phase 2: needs inverse kinematics")

    def gripper(self, open_fraction: float) -> bool:
        joints = self._read()
        joints[5] = 100 * min(max(open_fraction, 0.0), 1.0)
        return self.move_joints(joints, 0.4)

    def set_tap(self, lift=None, press=None) -> None:
        """Change how far the tip lifts off the key and how far a press goes. Raises before changing anything."""
        lift = self.lift if lift is None else lift
        press = self.press_extra if press is None else press
        if type(lift) not in (int, float) or not 0.2 <= lift <= 40:  # NaN fails both comparisons
            raise ValueError("lift must be 0.2 to 40")
        if type(press) not in (int, float) or not -10 <= press <= 10:
            raise ValueError("press must be -10 to 10")
        self.lift, self.press_extra = float(lift), float(press)

    def key_pose(self, lower: float = 0.0) -> list[float]:
        """The tap_key pose with the tip lowered by `lower` on TAP_JOINT (negative = lifted)."""
        pose = self.load_pose("tap_key")
        pose[TAP_JOINT] += lower
        return pose

    def hover_pose(self) -> list[float]:
        return self.key_pose(-self.lift)

    def to_key(self) -> bool:
        """From anywhere: home, arrive well above the key, then come straight down to the hover."""
        above = self.hover_pose()
        above[ELBOW] -= APPROACH_DEG
        at_home = all(abs(a - b) < 3 for a, b in zip(self._read(), self.load_pose("home")))
        return ((at_home or self.home(1.2))  # no pause at home when it is already there
                and self.move_joints(above, 0.9) and self.move_joints(self.hover_pose(), 0.4))

    def from_key(self) -> bool:
        """Lift straight up off the key, then go home."""
        above = self.hover_pose()
        above[ELBOW] -= APPROACH_DEG
        return self.move_joints(above, 0.4) and self.home(1.2)

    def press(self) -> bool:
        """Come down onto the key. One command, for tight timing."""
        return self._jump(self.press_extra)

    def release(self) -> bool:
        """Lift off the key to the hover."""
        return self._jump(-self.lift)

    def _jump(self, lower: float) -> bool:
        if self.halt.is_set():
            return False
        self._write_tap(_checked(self.key_pose(lower)))
        return True

    def _write_tap(self, joints: list[float]) -> None:
        """Send a tap. The mock has nothing faster than a normal write."""
        self._write(joints)

    def tap(self, depth_mm: float = 3.0) -> bool:
        # ponytail: depth_mm is ignored until there is IK; the stroke is set_tap(lift, press).
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

    def temperatures(self) -> dict[str, float]:
        return {name: 30.0 for name in JOINTS}

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
        gain = os.environ.get("TAP_P_GAIN")
        if gain is not None and not (gain.isdigit() and 8 <= int(gain) <= 48):
            raise ValueError("TAP_P_GAIN must be a whole number from 8 to 48")  # checked before connecting
        import arm as root_arm  # the root arm.py

        self._robot = root_arm.follower()  # connects: motors switch on and hold
        if gain is not None:
            # Daniel approved this on 14 Nov for the tapping (wrist) motor only: LeRobot sets every
            # motor's position gain to 16 at connect, which makes small moves slow and uneven. A
            # higher gain snaps the tip to the key. It is written again at every connect, so it does
            # not outlast this run. Unset TAP_P_GAIN to go back to 16.
            gain, name = int(gain), JOINTS[TAP_JOINT]
            with self._robot.bus.torque_disabled(name):
                self._robot.bus.write("P_Coefficient", name, gain)
            print(f"position gain of {name} set to {gain}", flush=True)

    def temperatures(self) -> dict[str, float]:
        """Degrees Celsius of each motor. Call only while no skill is running: it uses the serial bus."""
        return {name: float(value) for name, value in self._robot.bus.sync_read("Present_Temperature").items()}

    def _read(self) -> list[float]:
        obs = self._robot.get_observation()
        return [float(obs[f"{j}.pos"]) for j in JOINTS]

    def _write(self, joints: list[float]) -> None:
        self._robot.send_action({f"{j}.pos": v for j, v in zip(JOINTS, joints)})

    def _write_tap(self, joints: list[float]) -> None:
        """One packet to the tapping motor only. The normal write first reads all six motors to
        limit the step, which added a few milliseconds that varied from tap to tap; a tap is a
        small, already-checked move of one joint, so it does not need that."""
        name, goal = JOINTS[TAP_JOINT], joints[TAP_JOINT]
        cap = self._robot.config.max_relative_target
        if cap is not None:
            # Keep the same safety the normal write has, for this one motor: read where it really is
            # and never command it further than the step limit from there. One motor, one read.
            here = float(self._robot.bus.sync_read("Present_Position", [name])[name])
            goal = max(here - cap, min(here + cap, goal))
        self._robot.bus.sync_write("Goal_Position", {name: goal})

    def close(self, release: bool = True) -> None:
        """Close the serial port. Never moves. release=True switches the motors off, so the arm
        drops unless it is resting or held; release=False leaves them on and holding.
        The flag is set on the robot itself because LeRobot also disconnects when the object is
        garbage collected, and that path must not release the motors either."""
        self._robot.config.disable_torque_on_disconnect = release
        self._robot.disconnect()


def get_arm(mock: bool = False) -> MockArm:
    return MockArm() if mock else Arm()
