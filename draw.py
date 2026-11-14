"""Turn a request into pen strokes, preview them, and draw them with the arm.

    python draw.py a cat               # anything: the best of people's Quick, Draw! doodles, or Claude draws it
    python draw.py --first cat         # the first usable Quick, Draw! doodle, no model
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
# A pen pressed on paper trails behind the gripper, so strokes end short and corners are cut. Aiming this far
# ahead along the direction of travel cancels it. As a fraction of the page; 0 = off. Measure: draw a line and
# see how far short of its end the ink stops.
PEN_DRAG = float(os.environ.get("PEN_DRAG", "0"))
# "detailed": up to 30 strokes with small features. "simple": bold drawings of 3 to 10 strokes, about half the
# drawing time. Tested by bending both the way a sloppy arm would (pen lagging its direction of travel, plus
# wobble) and asking a viewer that was not told the subject, 12 subjects each: detailed was named 12 of 12 with
# the pen 2 and 4 mm off and 8 of 12 at 6 mm; simple 11, 10 and 9. So detail does not cost recognition up to
# about 4 mm, but simple drawings look less broken at the same error.
DETAIL = os.environ.get("DRAW_DETAIL", "detailed")
PEN_SQUEEZE = float(os.environ.get("PEN_SQUEEZE", "8"))  # close this much past the taught gripper value
QUICKDRAW = "https://storage.googleapis.com/quickdraw_dataset/full/simplified/{}.ndjson"
CATEGORIES = "https://raw.githubusercontent.com/googlecreativelab/quickdraw-dataset/master/categories.txt"

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


def _fetch(url: str, first_bytes: int | None = None) -> str:
    import ssl

    import certifi  # python.org builds on macOS ship without root certificates

    req = urllib.request.Request(url, headers={"Range": f"bytes=0-{first_bytes}"} if first_bytes else {})
    return urllib.request.urlopen(req, timeout=20, context=ssl.create_default_context(cafile=certifi.where())).read().decode()


def categories() -> list[str]:
    """The 345 things in the Quick, Draw! database. Kept in drawings/ so it works without Wi-Fi."""
    cache = HERE / "drawings" / "_categories.txt"
    if not cache.exists():
        cache.parent.mkdir(exist_ok=True)
        cache.write_text(_fetch(CATEGORIES))
    return [line.strip() for line in cache.read_text().splitlines() if line.strip()]


def doodles(word: str) -> list[list[Stroke]]:
    """A few hundred people's doodles of `word` from Quick, Draw!, each fitted to the page. Only ones
    the game recognised, and not scribbles or single lines."""
    try:
        lines = _fetch(QUICKDRAW.format(urllib.parse.quote(word)), 600000).splitlines()[:-1]
    except Exception as err:
        raise LookupError(f'No Quick, Draw! drawings for "{word}" ({err})') from err
    good = [d["drawing"] for d in map(json.loads, lines) if d["recognized"] and 2 <= len(d["drawing"]) <= 14]
    return [fit([list(zip(xs, ys)) for xs, ys in drawing]) for drawing in good]


def raster(strokes: list[Stroke], size: int = 32):
    """The drawing as a small soft image, for comparing drawings with each other."""
    import cv2
    import numpy as np

    page = np.zeros((size * 4, size * 4), np.uint8)
    for stroke in strokes:
        cv2.polylines(page, [np.int32([(u * size * 4, v * size * 4) for u, v in stroke])], False, 255, 6)
    small = cv2.resize(cv2.GaussianBlur(page, (0, 0), 6), (size, size)).astype(np.float32).ravel()
    return small / (np.linalg.norm(small) or 1.0)


def most_typical(drawings: list[list[Stroke]], keep: int = 12) -> list[list[Stroke]]:
    """The `keep` drawings most like the average of them all. People draw a thing a few common ways;
    the odd ones (a cat from behind, a half-finished bike) score low. This is the part learned from
    the database: nothing is hand-picked."""
    import numpy as np

    images = np.array([raster(d) for d in drawings])
    average = images.mean(axis=0)
    order = np.argsort(-(images @ (average / np.linalg.norm(average))))
    return [drawings[i] for i in order[:keep]]


def sheet(drawings: list[list[Stroke]], cell: int = 220):
    """The drawings side by side with numbers, as JPEG bytes, for a model to choose from."""
    import cv2
    import numpy as np

    across = min(len(drawings), 4)
    down = -(-len(drawings) // across)
    page = np.full((down * cell, across * cell, 3), 255, np.uint8)
    for i, strokes in enumerate(drawings):
        ox, oy = (i % across) * cell, (i // across) * cell
        for stroke in strokes:
            cv2.polylines(page, [np.int32([(ox + 20 + u * (cell - 40), oy + 20 + v * (cell - 40)) for u, v in stroke])],
                          False, (0, 0, 0), 2, cv2.LINE_AA)
        cv2.rectangle(page, (ox, oy), (ox + cell, oy + cell), (200, 200, 200), 1)
        cv2.putText(page, str(i + 1), (ox + 6, oy + 24), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
    return cv2.imencode(".jpg", page)[1].tobytes()


def best_of(drawings: list[list[Stroke]], what: str) -> list[Stroke]:
    """Claude looks at the candidates side by side and picks the one a stranger would recognise."""
    import see

    reply = see.parse_reply(see.ask_claude(
        f'These are {len(drawings)} numbered line drawings that are each meant to be "{what}". Which single one '
        "would a stranger most readily recognise as that, and looks neatest? Prefer a complete, tidy drawing "
        "over a detailed but messy one, and mark down any with stray marks or decoration that is not part of "
        'the subject. Return only JSON: {"best": number}', sheet(drawings), max_tokens=300))
    best = reply.get("best") if isinstance(reply, dict) else None
    return drawings[best - 1] if type(best) is int and 1 <= best <= len(drawings) else drawings[0]


def from_quickdraw(word: str, pick: int = 0) -> list[Stroke]:
    cache = HERE / "drawings" / f"{word}.json"
    if cache.exists() and pick == 0:
        return [[tuple(p) for p in s] for s in json.loads(cache.read_text())]
    try:
        good = doodles(word)
    except LookupError as err:
        sys.exit(f'{err}. Try --gen "{word}".')
    strokes = good[pick % len(good)]
    if pick == 0:
        cache.parent.mkdir(exist_ok=True)
        cache.write_text(json.dumps(strokes))
    return strokes


def sketch(what: str) -> list[Stroke]:
    """Strokes for anything a person asks for. Claude draws it three times and picks the best; if it
    is one of the 345 things in Quick, Draw!, it is first shown the most typical of people's doodles
    of it. A viewer that is not told the subject then names the drawing: if it gets it wrong, there
    is one more round, told what it was mistaken for. Without Claude, the doodles themselves are
    used. The answer is kept in drawings/, so the same request is instant next time."""
    import re

    import see

    see.load_env()
    slug = re.sub(r"[^a-z0-9]+", "_", what.lower()).strip("_") or "drawing"
    cache = HERE / "drawings" / (f"sketch_{slug}.json" if DETAIL == "detailed" else f"simple_{slug}.json")
    if cache.exists():
        return [[tuple(p) for p in s] for s in json.loads(cache.read_text())]
    names = categories()
    plain = re.sub(r"^(a|an|the|some|draw|sketch)\s+", "", what.lower().strip())
    match = next((n for n in names if n.lower() in (plain, what.lower().strip())), None)
    if match is None:
        reply = see.parse_reply(see.ask_claude(
            f'A person asked for a drawing of "{what}". Here is a list of things we have drawings of: {", ".join(names)}. '
            'If one of them is the same thing (a kitten is a cat, a car is a car, a rocket is not an airplane), return it '
            'exactly as written; otherwise null. Return only JSON: {"have": "<name>" or null}', max_tokens=300,
            model=os.environ.get("ROUTER_MODEL", "claude-haiku-5-5")))
        match = reply.get("have") if isinstance(reply, dict) and reply.get("have") in names else None
    from concurrent.futures import ThreadPoolExecutor

    people = most_typical(doodles(match)) if match else []  # how people draw it, when the database has it
    reference = sheet(people) if people else None
    with ThreadPoolExecutor() as pool:  # three tries at once, then the best of everything
        tries = [t for t in pool.map(lambda _: _try(from_model, what, reference), range(3)) if t]
        if not tries:  # Claude is unreachable or returned nothing usable: people's doodles are the fallback
            tries = people[:4]
        if not tries:
            raise LookupError(f'could not draw "{what}"')
        strokes = best_of(tries, what) if len(tries) > 1 else tries[0]
        seen = looks_like(strokes)  # a viewer who is not told what it is
        if not same_thing(what, seen):  # one more round, told what went wrong
            again = [t for t in pool.map(lambda _: _try(from_model, what, reference, seen), range(3)) if t]
            if again:
                strokes = best_of(again, what) if len(again) > 1 else again[0]
    cache.parent.mkdir(exist_ok=True)
    cache.write_text(json.dumps(strokes))
    return strokes


def looks_like(strokes: list[Stroke]) -> str:
    """What someone who was not told would say this drawing is."""
    import see

    return see.ask_claude("What is this line drawing of? Answer with one to three words only.",
                          sheet([strokes], cell=400), max_tokens=200).strip()


def same_thing(asked: str, seen: str) -> bool:
    import see

    reply = see.parse_reply(see.ask_claude(
        f'Someone asked for a drawing of "{asked}". A viewer who was not told said it shows "{seen}". Did the viewer '
        'recognise it? A more specific or looser name for the same thing counts ("electric guitar" for a guitar); '
        'a part of it or a different thing does not ("elephant head" for an elephant, "robot arm" for a robot). '
        'Return only JSON: {"same": true or false}', max_tokens=100))
    return isinstance(reply, dict) and reply.get("same") is True


def _try(make, *args):
    try:
        return make(*args)
    except Exception as err:  # one bad reply out of three is fine
        print(f"A drawing attempt failed: {type(err).__name__}: {str(err)[:120]}", file=sys.stderr)
        return None


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


def rounded(points: Stroke, passes: int = 2) -> Stroke:
    """Cut the corners off a stroke so it reads as a curve (Chaikin). A stroke that ends where it
    starts stays closed."""
    closed = len(points) > 3 and points[0] == points[-1]
    for _ in range(passes):
        pairs = list(zip(points, points[1:]))
        cut = [q for (x0, y0), (x1, y1) in pairs
               for q in ((0.75 * x0 + 0.25 * x1, 0.75 * y0 + 0.25 * y1), (0.25 * x0 + 0.75 * x1, 0.25 * y0 + 0.75 * y1))]
        points = cut + [cut[0]] if closed else [points[0]] + cut + [points[-1]]
    return points


def closed_up(points: Stroke) -> Stroke:
    """A loop whose ends nearly meet is closed. The model often draws a circle or an ellipse and stops just
    short of where it started, which left a gap in a cup's rim and a saucer."""
    (x0, y0), (x1, y1) = points[0], points[-1]
    size = max(max(x for x, _ in points) - min(x for x, _ in points), max(y for _, y in points) - min(y for _, y in points))
    gap = ((x1 - x0) ** 2 + (y1 - y0) ** 2) ** 0.5
    return points + [points[0]] if len(points) > 3 and 0 < gap < 0.2 * size else points


def from_model(what: str, reference: bytes | None = None, mistaken_for: str | None = None) -> list[Stroke]:
    """Claude draws it. `reference` is a sheet of people's doodles of the same thing (JPEG), to show
    how people usually picture it. `mistaken_for` is what a viewer thought an earlier try was."""
    import see

    see.load_env()
    prompt = (f"Draw {what} as a clean, charming line drawing for a pen plotter. "
              "It should be instantly recognisable and look good, like a well-made illustration in a children's "
              "book: the whole subject (all of an animal, not only its head), well proportioned, in its most "
              "familiar view. Draw only the thing named, in its plainest familiar form, with no accessories: a cup "
              "is a cup with a handle (no saucer, no steam), a tree has no bird in it. Match the detail to the subject. Something simple (a smiley face, a heart, a star) "
              "stays simple: a few clean strokes and nothing else. Something complex (a castle, a train, an animal) "
              "gets the parts that make it what it is: eyes and expression, windows, wheels, a mane, a shell "
              "pattern. Every stroke must be a part of the subject itself. Do not add decoration: no sparkles, "
              "motion lines, blush marks, raindrops, clouds, stray ticks or background, and no ground line unless "
              "the subject would look like it is floating without one. No shading or filling "
              "in, and do not let strokes crowd or cross each other. Finish every shape: an outline meets itself, "
              "a line that joins another reaches it. "
              + ("Use 4 to 30 strokes. " if os.environ.get("DRAW_DETAIL", "detailed") == "detailed" else
                 "The arm that draws this is imprecise: its pen can land 3 or 4 units away from where it aims, and "
                 "differently for each stroke. So draw it bold and simple, like a road sign: 3 to 10 strokes, big "
                 "shapes that fill the page, nothing smaller than 12 units across, at least 8 units between lines "
                 "that are not meant to touch, and nothing that depends on two strokes meeting exactly (draw a "
                 "shape in one stroke where you can). Leave out anything that would be lost or smudged at that "
                 "accuracy: small eyes become plain dots or are left out, patterns and textures go. ")
              + (f'An earlier attempt was mistaken for "{mistaken_for}": make what sets {what} apart unmistakable. '
                 if mistaken_for else "")
              + "Each stroke is a list of [x, y] points, x right and y down, both 0 to 100. Mark a stroke "
              '"smooth": true if it is a curve (it will be rounded for you, so 6 to 12 points are enough, and repeat '
              'the first point at the end to close a loop) or false if its corners should stay sharp. '
              + ("The picture shows how people usually doodle this: use it for what to include, not for neatness. "
                 if reference else "")
              + 'Return only JSON: [{"smooth": true or false, "points": [[x, y], ...]}, ...]')
    text = see.ask_claude(prompt, reference, model=os.environ.get("DRAW_MODEL", "claude-sonnet-5-5"), max_tokens=8000)
    reply = see.parse_reply(text)
    strokes = []
    for item in reply if isinstance(reply, list) else []:
        points = item.get("points") if isinstance(item, dict) else item  # a bare list of points is a sharp stroke
        if not (isinstance(points, list) and len(points) > 1 and all(
                isinstance(q, list) and len(q) == 2 and all(type(n) in (int, float) and n == n and abs(n) < 1e6 for n in q)
                for q in points)):
            continue  # a malformed stroke is dropped, never guessed
        stroke = closed_up([(float(x), float(y)) for x, y in points])
        strokes.append(rounded(stroke) if isinstance(item, dict) and item.get("smooth") is True else stroke)
    if not strokes:
        raise ValueError("the model returned no usable strokes")
    return fit(strokes)


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
    elif args[0] == "--first":
        strokes = from_quickdraw(" ".join(args[1:]).lower())
    else:
        strokes = sketch(" ".join(args))
    preview(strokes)
    print(f"{len(strokes)} strokes -> outputs/draw.png")
    if "--go" in sys.argv:
        draw(strokes)


if __name__ == "__main__":
    square = fit([[(0, 0), (10, 0), (10, 5)]])  # wide shape: fills the width, centred in height
    assert abs(square[0][0][0] - MARGIN) < 1e-9 and abs(square[0][1][0] - (1 - MARGIN)) < 1e-9
    assert abs((square[0][0][1] + square[0][2][1]) / 2 - 0.5) < 1e-9
    assert len(resample([(0, 0), (1, 0)])) == 51
    ring = [(0, 0), (10, 0), (10, 10), (0, 10), (0, 1)]  # stops just short of its start
    assert closed_up(ring)[-1] == ring[0] and closed_up(ring[:4]) == ring[:4] and closed_up([(0, 0), (10, 0)]) == [(0, 0), (10, 0)]
    main()
