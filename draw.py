"""Turn a request into pen strokes, preview them, and draw them with the arm.

    python draw.py cat                 # from the Quick, Draw! database (345 everyday things)
    python draw.py --text "Eddy"       # write a word
    python draw.py --gen "a rocket"    # ask Claude to invent the strokes
    python draw.py cat --go            # also draw it (needs poses/paper.json from arm.py teach)

Every run saves outputs/draw.png so you can see the drawing before the arm moves.
Drawings are cached in drawings/, so the demo does not need Wi-Fi for ones already fetched.
Strokes are lists of (u, v) points in the unit square: u right, v down the page.
"""
import json
import os
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

HERE = Path(__file__).parent
MARGIN = 0.08          # keep this much of the page clear on every side
STEP = 0.02            # pen travel between arm commands, as a fraction of the page
PEN_SPEED = float(os.environ.get("PEN_SPEED", "0.15"))  # fractions of the page per second
PEN_SQUEEZE = float(os.environ.get("PEN_SQUEEZE", "8"))  # close this much past the taught gripper value
QUICKDRAW = "https://storage.googleapis.com/quickdraw_dataset/full/simplified/{}.ndjson"

Stroke = list[tuple[float, float]]


def fit(strokes: list[Stroke]) -> list[Stroke]:
    """Scale and centre strokes inside the unit square, keeping their shape."""
    xs = [x for s in strokes for x, _ in s]
    ys = [y for s in strokes for _, y in s]
    span = max(max(xs) - min(xs), max(ys) - min(ys)) or 1.0
    scale = (1 - 2 * MARGIN) / span
    ox = 0.5 - (max(xs) + min(xs)) / 2 * scale
    oy = 0.5 - (max(ys) + min(ys)) / 2 * scale
    return [[(x * scale + ox, y * scale + oy) for x, y in s] for s in strokes]


def from_quickdraw(word: str, pick: int = 0) -> list[Stroke]:
    cache = HERE / "drawings" / f"{word}.json"
    if cache.exists() and pick == 0:
        return [[tuple(p) for p in s] for s in json.loads(cache.read_text())]
    req = urllib.request.Request(QUICKDRAW.format(urllib.parse.quote(word)),
                                 headers={"Range": "bytes=0-400000"})
    import ssl

    import certifi  # python.org builds on macOS ship without root certificates

    try:
        tls = ssl.create_default_context(cafile=certifi.where())
        lines = urllib.request.urlopen(req, timeout=20, context=tls).read().decode().splitlines()[:-1]
    except Exception as err:
        sys.exit(f'No Quick, Draw! drawing for "{word}" ({err}). Try --gen "{word}".')
    # people's doodles vary; keep recognised ones that are not scribbles
    good = [d for d in map(json.loads, lines) if d["recognized"] and 2 <= len(d["drawing"]) <= 12]
    strokes = fit([list(zip(xs, ys)) for xs, ys in good[pick % len(good)]["drawing"]])
    if pick == 0:
        cache.parent.mkdir(exist_ok=True)
        cache.write_text(json.dumps(strokes))
    return strokes


def from_text(text: str) -> list[Stroke]:
    from HersheyFonts import HersheyFonts

    font = HersheyFonts()
    font.load_default_font()
    strokes: list[Stroke] = []
    for a, b in font.lines_for_text(text):
        if strokes and strokes[-1][-1] == a:
            strokes[-1].append(b)  # join segments so the pen stays down
        else:
            strokes.append([a, b])
    return fit(strokes)


def from_model(what: str) -> list[Stroke]:
    import see

    see.load_env()
    prompt = (f"Draw {what} as a simple line drawing for a pen plotter. Use 4 to 15 strokes. "
              "Each stroke is a list of [x, y] points, x right and y down, both 0 to 100. "
              "Curves need enough points to look smooth. Return only JSON: [[[x, y], ...], ...]")
    text = see.ask_claude(prompt, model=os.environ.get("DRAW_MODEL", "claude-sonnet-5-5"), max_tokens=8000)
    strokes = json.loads(text[text.index("["):text.rindex("]") + 1])
    return fit([[(float(x), float(y)) for x, y in s] for s in strokes if len(s) > 1])


def preview(strokes: list[Stroke], path: str = "outputs/draw.png") -> None:
    import cv2
    import numpy as np

    size = 600
    page = np.full((size, size, 3), 255, np.uint8)
    for s in strokes:
        pts = np.array([[u * size, v * size] for u, v in s], np.int32)
        cv2.polylines(page, [pts], False, (0, 0, 0), 3, cv2.LINE_AA)
    Path(path).parent.mkdir(exist_ok=True)
    cv2.imwrite(path, page)


def resample(stroke: Stroke) -> Stroke:
    """Add points so no two are more than STEP apart."""
    out = [stroke[0]]
    for (x0, y0), (x1, y1) in zip(stroke, stroke[1:]):
        n = max(1, int(((x1 - x0) ** 2 + (y1 - y0) ** 2) ** 0.5 / STEP))
        out += [(x0 + (x1 - x0) * i / n, y0 + (y1 - y0) * i / n) for i in range(1, n + 1)]
    return out


def draw(strokes: list[Stroke], grid_name: str = "paper") -> None:
    import arm
    from grid import interpolate

    grid = json.loads((HERE / "poses" / f"{grid_name}.json").read_text())
    n = grid["n"]
    # the gripper was taught limp around the pen, which holds it at exactly pen width: squeeze a bit more
    for layer in ("up", "down"):
        for taught in grid[layer]:
            if not all(type(x) in (int, float) and x == x and abs(x) != float("inf") for x in taught.values()):
                raise SystemExit(f"Bad taught pose in poses/{grid_name}.json; teach it again.")  # max() would hide a NaN
            taught["gripper.pos"] = max(0.0, taught["gripper.pos"] - PEN_SQUEEZE)
    robot = arm.follower()
    for stroke in strokes:
        pts = resample(stroke)
        arm.move_to(robot, interpolate(grid["up"], n, *pts[0]), 1.0)
        arm.move_to(robot, interpolate(grid["down"], n, *pts[0]), 0.4)
        for u, v in pts[1:]:
            robot.send_action(interpolate(grid["down"], n, u, v))
            time.sleep(STEP / PEN_SPEED)
        arm.move_to(robot, interpolate(grid["up"], n, *pts[-1]), 0.4)
    robot.disconnect()


def main() -> None:
    args = [a for a in sys.argv[1:] if a != "--go"]
    if not args:
        sys.exit(__doc__)
    if args[0] == "--text":
        strokes = from_text(" ".join(args[1:]))
    elif args[0] == "--gen":
        strokes = from_model(" ".join(args[1:]))
    else:
        strokes = from_quickdraw(" ".join(args).lower())
    preview(strokes)
    print(f"{len(strokes)} strokes -> outputs/draw.png")
    if "--go" in sys.argv:
        draw(strokes)


if __name__ == "__main__":
    square = fit([[(0, 0), (10, 0), (10, 5)]])  # wide shape: fills the width, centred in height
    assert abs(square[0][0][0] - MARGIN) < 1e-9 and abs(square[0][1][0] - (1 - MARGIN)) < 1e-9
    assert abs((square[0][0][1] + square[0][2][1]) / 2 - 0.5) < 1e-9
    assert len(resample([(0, 0), (1, 0)])) == 51
    main()
