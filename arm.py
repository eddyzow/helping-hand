"""Teach, record and replay motions on the SO-101 follower. Runs on the arm laptop.

    python arm.py teach paper        # hand-pose the arm over a 3x3 grid, on the surface then above it
    python arm.py pose home          # save one pose by hand (home, handover)
    python arm.py record wave        # move the leader; the follower copies and it is saved
    python arm.py replay wave        # the follower repeats it

UNTESTED ON HARDWARE as of Fri night. Written against LeRobot main on GitHub
(lerobot.robots.so_follower). If an import fails, check the installed version.
First runs: one person on the power switch, arm clear of people.

Ports and ids come from the environment:
    FOLLOWER_PORT=/dev/ttyACM1 LEADER_PORT=/dev/ttyACM0 python arm.py ...
"""
import json
import os
import sys
import time
from pathlib import Path

FOLLOWER_PORT = os.environ.get("FOLLOWER_PORT", "/dev/ttyACM1")
LEADER_PORT = os.environ.get("LEADER_PORT", "/dev/ttyACM0")
HZ = 30
MAX_STEP = float(os.environ.get("MAX_STEP", "15"))  # most a joint may move per command
HERE = Path(__file__).parent

Pose = dict[str, float]


def follower():
    from lerobot.robots.so_follower import SO101Follower, SO101FollowerConfig

    robot = SO101Follower(SO101FollowerConfig(
        port=FOLLOWER_PORT, id="follower", max_relative_target=MAX_STEP))
    robot.connect()
    return robot


def leader():
    from lerobot.teleoperators.so_leader import SO101Leader, SO101LeaderConfig

    teleop = SO101Leader(SO101LeaderConfig(port=LEADER_PORT, id="leader"))
    teleop.connect()
    return teleop


def read_pose(robot) -> Pose:
    return {k: float(v) for k, v in robot.get_observation().items() if k.endswith(".pos")}


def move_to(robot, target: Pose, seconds: float = 1.5) -> None:
    """Glide from the current pose to target in small steps."""
    start = read_pose(robot)
    steps = max(1, int(seconds * HZ))
    for i in range(1, steps + 1):
        f = i / steps
        robot.send_action({k: start[k] + (target[k] - start[k]) * f for k in target})
        time.sleep(1 / HZ)


def teach(name: str, n: int = 3) -> None:
    robot = follower()
    robot.bus.disable_torque()  # arm goes limp so you can pose it by hand
    grid = {"n": n}
    for layer, hint in [("down", "pen or open gripper on the surface"), ("up", "lifted clear, about 5 cm")]:
        grid[layer] = []
        for row in range(n):
            for col in range(n):
                input(f"{layer}: row {row} (0 = far), col {col} (0 = left), {hint}. Enter to save. ")
                grid[layer].append(read_pose(robot))
    out = HERE / "poses" / f"{name}.json"
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps(grid, indent=1))
    print(f"saved {out}")
    robot.disconnect()


def pose(name: str) -> None:
    robot = follower()
    robot.bus.disable_torque()
    input(f"Move the arm to the {name} pose by hand, then Enter. ")
    out = HERE / "poses" / f"{name}.json"
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps(read_pose(robot), indent=1))
    print(f"saved {out}")
    robot.disconnect()


def record(name: str) -> None:
    robot, teleop = follower(), leader()
    input("Hold the leader near the follower's pose, then Enter. Ctrl+C to stop. ")
    frames, t0 = [], time.time()
    try:
        while True:
            action = teleop.get_action()
            robot.send_action(action)
            frames.append([time.time() - t0, {k: float(v) for k, v in action.items()}])
            time.sleep(1 / HZ)
    except KeyboardInterrupt:
        pass
    out = HERE / "motions" / f"{name}.json"
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps(frames))
    print(f"saved {len(frames)} frames to {out}")
    robot.disconnect()
    teleop.disconnect()


def replay(name: str, robot=None) -> None:
    frames = json.loads((HERE / "motions" / f"{name}.json").read_text())
    own = robot is None
    robot = robot or follower()
    move_to(robot, frames[0][1], 2.0)
    t0 = time.time()
    for t, action in frames:
        time.sleep(max(0.0, t - (time.time() - t0)))
        robot.send_action(action)
    if own:
        robot.disconnect()


if __name__ == "__main__":
    commands = {"teach": teach, "pose": pose, "record": record, "replay": replay}
    if len(sys.argv) < 3 or sys.argv[1] not in commands:
        sys.exit(__doc__)
    commands[sys.argv[1]](sys.argv[2])
