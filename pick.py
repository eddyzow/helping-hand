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
Run `python arm.py check table` before the first real grasp.

Mount the camera straight above the middle of the grid, as high as it will go. The pixel
is mapped as if everything were flat on the table, so the top of a tall object lands
too far from the point under the camera: off by (object height / camera height) times
its distance from that point. A 3 cm object 20 cm out under a 60 cm camera is 1 cm off.
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
GRIP_OPEN = float(os.environ.get("GRIP_OPEN", "100"))      # fully open: at 60 the simulated jaw came down on top of a 32 mm brick
GRIP_CLOSED = float(os.environ.get("GRIP_CLOSED", "5"))   # gripper.pos when squeezing
HOLD_SECONDS = float(os.environ.get("HOLD_SECONDS", "3"))  # how long it holds the object out
EDGE = 0.05  # how far outside the taught grid a target may be
DROP_GAP = float(os.environ.get("DROP_GAP", "0.3"))  # how far beside an object to put something, as a share of the grid


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
    """Every object matching the request, as (u, v, label) on the taught grid.
    Marks outputs/last.jpg. Returns (targets, said, near): near lists any object the person
    asked to have it put next to, in the same form."""
    hits, said, boxes, beside = see.find_all(frame, command, audio)
    corners = json.loads(CORNERS.read_text())
    out = see.numbered(frame, boxes)
    cv2.polylines(out, [np.int32(corners)], True, (255, 0, 0), 3)
    targets = []
    for x, y, label in hits:
        u, v = to_uv(x, y, corners)
        cv2.drawMarker(out, (x, y), (0, 0, 255), cv2.MARKER_CROSS, 60, 6)
        targets.append((u, v, label))
    targets = narrow(targets, said)
    near = []
    for x, y, label in beside:
        cv2.drawMarker(out, (x, y), (255, 0, 255), cv2.MARKER_TILTED_CROSS, 60, 6)
        near.append((*to_uv(x, y, corners), label))
    Path("outputs").mkdir(exist_ok=True)
    cv2.imwrite("outputs/last.jpg", out)
    return targets, said, near


# Words that settle "which one?" by position. The model does not know where the arm is, so code does it.
# Each maps a target (u, v, label) to a score; the lowest wins. Left and right are the arm's own.
TIEBREAKS = {
    ("closest", "nearest", "closer", "nearer"): lambda t: (-t[1], abs(t[0] - 0.5)),
    ("farthest", "furthest", "farther", "further"): lambda t: (t[1], abs(t[0] - 0.5)),
    ("leftmost", "left"): lambda t: (t[0],),
    ("rightmost", "right"): lambda t: (-t[0],),
    ("any", "either", "one of"): lambda t: (-t[1], abs(t[0] - 0.5)),
}


def narrow(targets: list, command: str | None) -> list:
    """Several matches and a position word in the request ("the closest red brick"): keep one.
    A dead heat goes to the first in the list. No such word: all are returned, and the caller asks."""
    words = f" {(command or '').lower()} "
    for names, score in TIEBREAKS.items():
        if len(targets) > 1 and any(f" {name} " in words for name in names):
            return [min(targets, key=score)]
    return targets


def drop_spot(picked: tuple, near: tuple) -> tuple[float, float]:
    """A place on the taught grid beside `near`, on the side the picked object came from.
    If `near` is outside the grid, this is the closest point the arm can reach."""
    du, dv = picked[0] - near[0], picked[1] - near[1]
    length = (du * du + dv * dv) ** 0.5 or 1.0
    u, v = near[0] + DROP_GAP * du / length, near[1] + DROP_GAP * dv / length
    return min(max(u, 0.05), 0.95), min(max(v, 0.05), 0.95)


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
        targets, said, _ = locate(frame, command, audio)  # pick.py only hands over; putting down is in skills/fetch.py
        target = targets[0] if len(targets) == 1 else None
        if not targets:
            print(f"I can't see that. (heard: {said})")
        elif len(targets) > 1:  # never pick one silently: ask
            print(f"I see {len(targets)} of those: " + "; ".join(
                f"{label} at u={u:.2f} v={v:.2f}" for u, v, label in targets) + ". Which one?")
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
    two = [(0.12, 0.79, "left red"), (0.88, 0.60, "right red")]
    assert narrow(two, "pick up the closest red brick") == [two[0]] and narrow(two, "the right one") == [two[1]]
    assert narrow(two, "the farthest red brick") == [two[1]] and narrow(two, "pick up the red brick") == two
    assert narrow(two[:1], "the closest") == two[:1] and narrow([], "the closest") == []
    # put it beside the other object, on the side it came from; an object off the grid clamps to the edge
    assert all(abs(a - b) < 1e-9 for a, b in zip(drop_spot((0.2, 0.5), (0.8, 0.5)), (0.8 - DROP_GAP, 0.5)))
    assert drop_spot((0.5, 0.5), (0.5, -0.9)) == (0.5, 0.05)
    main()
