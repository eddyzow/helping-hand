"""Teach, record and replay motions on the SO-101 follower. Runs on the arm laptop.

    python arm.py teach paper        # hand-pose the arm over a 3x3 grid, on the surface then above it
    python arm.py pose home          # save one pose by hand (home, handover)
    python arm.py check table        # visit the points between taught poses, slowly, to spot dips
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
    """Connect to the follower. Every script that moves the arm comes through here.
    LeRobot switches the motors off and on again while it connects, so an arm that is not
    resting can drop: the warning comes first. ARM_NO_PROMPT=1 skips it for unattended runs."""
    from lerobot.robots.so_follower import SO101Follower, SO101FollowerConfig

    if not os.environ.get("ARM_NO_PROMPT"):
        input("Connecting switches the motors off and on. Support the arm or check it is resting, then Enter. ")
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


def go_limp(robot) -> None:
    input("The arm will go LIMP and drop. Hold it up now, then press Enter. ")
    robot.bus.disable_torque()


def teach(name: str, n: int = 3) -> None:
    robot = follower()
    go_limp(robot)
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
    go_limp(robot)
    input(f"Move the arm to the {name} pose by hand, then Enter. ")
    out = HERE / "poses" / f"{name}.json"
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps(read_pose(robot), indent=1))
    print(f"saved {out}")
    robot.disconnect()


def check(name: str) -> None:
    """Blending joint angles does not guarantee height between taught points. Watch for dips."""
    from grid import interpolate

    grid = json.loads((HERE / "poses" / f"{name}.json").read_text())
    n = grid["n"]
    mids = [(c + 0.5) / (n - 1) for c in range(n - 1)]
    robot = follower()
    for layer in ("up", "down"):  # up first: if the lifted layer dips, stop before trying down
        for v in mids:
            for u in mids:
                input(f"{layer} layer, u={u:.2f} v={v:.2f}. Hand on the power switch. Enter to move. ")
                move_to(robot, interpolate(grid[layer], n, u, v), 3.0)
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
    commands = {"teach": teach, "pose": pose, "check": check, "record": record, "replay": replay}
    if len(sys.argv) < 3 or sys.argv[1] not in commands:
        sys.exit(__doc__)
    commands[sys.argv[1]](sys.argv[2])
