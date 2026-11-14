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
import math
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
GRID_ASPECT = float(os.environ.get("GRID_ASPECT", "1.0"))  # the taught grid's width divided by its depth
SQUARE_BELOW = 1.25  # an object less stretched than this counts as square
LAYER_GAP_MM = float(os.environ.get("LAYER_GAP_MM", "40"))  # how far the taught lifted layer is above the taught
# table layer, in mm. Measure it on the real grid: stacking heights are worked out from it.


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
    """Every object matching the request, as (u, v, label, turn) on the taught grid; turn is how
    many degrees to rotate the jaws so they close across the object's narrow side.
    Marks outputs/last.jpg. Returns (targets, said, place, problem, lift): place is (u, v, lift) if
    the person asked to put it somewhere, else None; problem is a sentence to say when the request
    cannot be done (check it first: a placement asked for must never become a handover); lift is how
    high the picked object sits now. A lift is a share of the way from the table layer to the lifted
    layer, 0 to 1: 0 on the table, more when it is on top of other pieces."""
    corners = json.loads(CORNERS.read_text())

    def describe(box):  # where this box is on the table, for the model to reason with
        us, vs = zip(*(to_uv(x, y, corners) for x in (box["x0"], box["x1"]) for y in (box["y0"], box["y1"])))
        return (f"centre u={sum(us) / 4:.2f} v={sum(vs) / 4:.2f}; "
                f"spans u {min(us):.2f} to {max(us):.2f}, v {min(vs):.2f} to {max(vs):.2f}")

    hits, said, boxes, placing, place, pick_height = see.find_all(frame, command, audio, describe, GRID_ASPECT)
    out = see.numbered(frame, boxes)
    cv2.polylines(out, [np.int32(corners)], True, (255, 0, 0), 3)
    targets = []
    for x, y, label, box in hits:
        u, v = to_uv(x, y, corners)
        cv2.drawMarker(out, (x, y), (0, 0, 255), cv2.MARKER_CROSS, 60, 6)
        targets.append((u, v, label, jaw_turn(frame, box, corners)))
    Path("outputs").mkdir(exist_ok=True)
    cv2.imwrite("outputs/last.jpg", out)
    problem = None
    if placing and place is None:
        problem = "I can't work out where to put it."
    elif placing and not (-EDGE <= place["u"] <= 1 + EDGE and -EDGE <= place["v"] <= 1 + EDGE):
        problem = "That spot is out of my reach."
    elif max(pick_height, place["height_mm"] if placing else 0) > LAYER_GAP_MM:
        problem = "That is stacked too high for me."
    spot = (place["u"], place["v"], place["height_mm"] / LAYER_GAP_MM) if placing and not problem else None
    return targets, said, spot, problem, pick_height / LAYER_GAP_MM


def jaw_turn(frame, box, corners) -> float:
    """Degrees to turn the jaws from their taught direction (closing left-right across the grid)
    so they close across the object's narrow side. 0 if the object's direction cannot be read.
    Positive turns from the grid's left-right line towards its near edge."""
    axis = see.long_axis(frame, box)
    if not axis:
        return 0.0
    angle, stretch = axis
    cx, cy = (box["x0"] + box["x1"]) / 2, (box["y0"] + box["y1"]) / 2
    reach = 0.25 * max(box["x1"] - box["x0"], box["y1"] - box["y0"])
    u0, v0 = to_uv(cx, cy, corners)
    u1, v1 = to_uv(cx + reach * math.cos(math.radians(angle)), cy + reach * math.sin(math.radians(angle)), corners)
    lies = math.degrees(math.atan2(v1 - v0, (u1 - u0) * GRID_ASPECT))  # the long side, on the table
    if stretch < SQUARE_BELOW:
        return (lies + 45.0) % 90.0 - 45.0   # square: either pair of faces will do, take the smaller turn
    return (lies + 90.0 + 90.0) % 180.0 - 90.0  # long: close across it, at right angles to the long side


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
        targets, said, spot, problem, lift = locate(frame, command, audio)
        target = targets[0] if len(targets) == 1 else None
        if spot or problem or lift:  # pick.py only hands over; putting down is in skills/fetch.py via voice/route.py
            print("This script only hands things over from the table. Use voice/route.py for stacks and putting down.")
        elif not targets:
            print(f"I can't see that. (heard: {said})")
        elif len(targets) > 1:  # never pick one silently: ask
            print(f"I see {len(targets)} of those: " + "; ".join(
                f"{label} at u={u:.2f} v={v:.2f}" for u, v, label, _ in targets) + ". Which one?")
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
