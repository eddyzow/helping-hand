"""Voice-controlled pick up: hear a request, find the object, pick it up, hand it over.

Set up once (redo --corners whenever the camera or arm base moves):
    python arm.py pose home            # arm parked out of the camera's view
    python arm.py pose handover        # where the arm holds the object out
    python arm.py teach table          # 3x3 grid: open gripper on the table, then lifted clear
    python pick.py --corners           # click the grid's 4 corners in the camera view:
                                       # far-left, far-right, near-right, near-left
Use:
    python pick.py "pick up the mouse"        # dry run: marks the target in outputs/last.jpg
    python pick.py "pick up the mouse" --go   # moves the arm
    python pick.py --go                       # voice loop: Enter, speak, Enter

The arm half is UNTESTED ON HARDWARE. First runs: someone on the power switch.
"""
import json
import os
import sys
import time
from pathlib import Path

import cv2
import numpy as np

import see

HERE = Path(__file__).parent
CORNERS = HERE / "poses" / "table_corners.json"
GRIP_OPEN = float(os.environ.get("GRIP_OPEN", "60"))      # gripper.pos when open
GRIP_CLOSED = float(os.environ.get("GRIP_CLOSED", "5"))   # gripper.pos when squeezing
HOLD_SECONDS = float(os.environ.get("HOLD_SECONDS", "3"))  # how long it holds the object out
EDGE = 0.05  # how far outside the taught grid a target may be


def to_uv(x: float, y: float, corners: list[list[float]]) -> tuple[float, float]:
    """Camera pixel -> position on the taught grid, u left to right, v far to near."""
    unit = np.float32([[0, 0], [1, 0], [1, 1], [0, 1]])
    m = cv2.getPerspectiveTransform(np.float32(corners), unit)
    u, v = cv2.perspectiveTransform(np.float32([[[x, y]]]), m)[0][0]
    return float(u), float(v)


def set_corners(args: list[str]) -> None:
    points = [[float(n) for n in a.split(",")] for a in args]  # or type them: 120,80 900,85 ...
    if not points:
        frame = see.grab_frame()
        def click(event, x, y, *_):
            if event == cv2.EVENT_LBUTTONDOWN and len(points) < 4:
                points.append([x, y])
                cv2.circle(frame, (x, y), 8, (0, 0, 255), -1)
        cv2.namedWindow("corners")
        cv2.setMouseCallback("corners", click)
        while len(points) < 4 and cv2.waitKey(30) != 27:
            cv2.imshow("corners", frame)
        cv2.destroyAllWindows()
    if len(points) != 4:
        sys.exit("Need 4 corners: far-left, far-right, near-right, near-left")
    CORNERS.parent.mkdir(exist_ok=True)
    CORNERS.write_text(json.dumps(points))
    print(f"saved {CORNERS}")


def load(name: str):
    return json.loads((HERE / "poses" / f"{name}.json").read_text())


def locate(frame, command=None, audio=None):
    """Return (u, v, label) for the requested object, or None. Marks outputs/last.jpg."""
    hit = see.find(frame, command, audio)
    corners = json.loads(CORNERS.read_text())
    cv2.polylines(frame, [np.int32(corners)], True, (0, 255, 0), 2)
    result = None
    if hit:
        x, y, label = hit
        u, v = to_uv(x, y, corners)
        cv2.drawMarker(frame, (x, y), (0, 0, 255), cv2.MARKER_CROSS, 40, 3)
        cv2.putText(frame, f"{label} u={u:.2f} v={v:.2f}", (x + 15, y - 15),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2)
        result = (u, v, label)
    Path("outputs").mkdir(exist_ok=True)
    cv2.imwrite("outputs/last.jpg", frame)
    return result


def grasp(robot, u: float, v: float) -> None:
    import arm
    from grid import interpolate

    table, handover = load("table"), load("handover")
    up = interpolate(table["up"], table["n"], u, v)
    down = interpolate(table["down"], table["n"], u, v)
    arm.move_to(robot, {**up, "gripper.pos": GRIP_OPEN}, 1.5)
    arm.move_to(robot, {**down, "gripper.pos": GRIP_OPEN}, 1.0)
    arm.move_to(robot, {**down, "gripper.pos": GRIP_CLOSED}, 0.6)
    arm.move_to(robot, {**up, "gripper.pos": GRIP_CLOSED}, 1.0)
    arm.move_to(robot, {**handover, "gripper.pos": GRIP_CLOSED}, 2.0)
    time.sleep(HOLD_SECONDS)
    arm.move_to(robot, {**handover, "gripper.pos": GRIP_OPEN}, 0.6)


def main() -> None:
    see.load_env()
    args = [a for a in sys.argv[1:] if a != "--go"]
    go = "--go" in sys.argv
    if args[:1] == ["--corners"]:
        return set_corners(args[1:])
    image = None
    if args[:1] == ["--image"]:  # dry run on a photo instead of the camera
        image, args = args[1], args[2:]
    command = " ".join(args) or None
    robot = None
    if go:
        import arm
        robot = arm.follower()
    while True:
        if robot:
            arm.move_to(robot, load("home"), 2.0)  # clear the camera's view before looking
        audio = None if command else see.record_wav()
        frame = cv2.imread(image) if image else see.grab_frame()
        target = locate(frame, command, audio)
        if not target:
            print("I can't see that.")
        elif not (-EDGE <= target[0] <= 1 + EDGE and -EDGE <= target[1] <= 1 + EDGE):
            print(f"{target[2]} is outside my reach (u={target[0]:.2f}, v={target[1]:.2f}).")
        else:
            print(f"{target[2]}: u={target[0]:.2f} v={target[1]:.2f} -> outputs/last.jpg")
            if robot:
                grasp(robot, target[0], target[1])
        if command:  # typed request: do it once
            break
    if robot:
        arm.move_to(robot, load("home"), 2.0)
        robot.disconnect()


if __name__ == "__main__":
    # a tilted camera view: corners map to the unit square's corners, in the taught order
    quad = [[100, 100], [500, 120], [560, 400], [60, 380]]
    for pixel, uv in zip(quad, [(0, 0), (1, 0), (1, 1), (0, 1)]):
        assert all(abs(a - b) < 1e-4 for a, b in zip(to_uv(*pixel, quad), uv)), pixel
    # a square-on view: the middle pixel is the middle of the grid
    assert all(abs(a - 0.5) < 1e-4 for a in to_uv(300, 250, [[100, 50], [500, 50], [500, 450], [100, 450]]))
    main()
