"""Hear or read a request and find the matching objects in the camera frame.

    python see.py "pick up the red brick"        # typed command
    python see.py                                # speak: Enter to start, Enter to stop
    python see.py --image photo.jpg "the mouse"  # test on a still photo

Two steps, because no single model did both well on our Duplo photos (notes/eddy.md):
  1. OpenAI draws a box around every object on the table. It is accurate at where.
  2. Claude sees the boxes numbered and says which numbers match the request. It is
     accurate at which, including "there are two of those".
Speech is written down by OpenAI. Saves the annotated frame to outputs/last.jpg.
Needs OPENAI_API_KEY and ANTHROPIC_API_KEY in .env. Gemini was dropped on Nov 14: its free
tier timed out or refused most requests.
"""
import base64
import json
import math
import os
import re
import sys
import tempfile
import wave
from pathlib import Path

import cv2

DETECTOR = os.environ.get("DETECTOR", "gpt-6.1-terra")  # boxes the frame: 8 of 9 Duplo pieces, about 5 seconds
CHOOSER = os.environ.get("CHOOSER_MODEL", "claude-sonnet-5-5")
LISTENER = os.environ.get("LISTENER", "gpt-4o-mini-transcribe")  # writes down what was said
CAMERA = int(os.environ.get("CAMERA", "0"))  # index of the overhead camera
TIMEOUT_S = 30.0
SAMPLE_RATE = 16000
AXIS_CONTRAST = float(os.environ.get("AXIS_CONTRAST", "22"))  # how different from the table counts as the object
CHOOSER_LONG_EDGE = 1024  # the numbered image is shrunk to this before it goes to the chooser

DETECT = """Detect every separate physical object lying on the table. Two objects that touch are
still two objects. Do not skip any object, whatever its colour, and do not report shadows or
marks on the table.
Return only JSON: [{"box_2d": [ymin, xmin, ymax, xmax], "label": "<colour and shape>"}]
Coordinates are normalized to 0-1000."""

# ponytail: the hint names our Duplo set. Edit it when the objects on the table change.
CHOOSE = """A robot arm picks objects off a table. Each object in the image has a green box and a
numbered badge. The objects (the detector's guess at what each is may be wrong; trust the image):
{labels}
Positions are on the robot's table grid. u runs from the robot's left (0) to its right (1). v runs from
the far edge (0) to the edge nearest the robot (1); the robot sits beyond v = 1. So "behind" an object
means smaller v, "in front of" it means larger v, "left" smaller u, "right" larger u. One unit of u is
{aspect} times as long on the table as one unit of v. Anything outside 0 to 1 is beyond the robot's reach,
and boxes at v above 1 are usually parts of the robot itself: never pick those or put things there.
The pieces may be LEGO Duplo. A piece may lie on its side or upside down, showing its hollow
underside. People call the 2x4 brick with a sloped top the "triangle" brick; from below it shows
three round holes in a row. One box may hold two touching pieces.
The person said: "{command}"

"matches": the numbered objects they asked to pick up. Use the positions to settle words such as left,
right, closest, farthest, middle. A different kind of object does not fit. If several fit equally and
the words do not settle it, list them all; but if they ask for "a" or "any" such object, choose one.

If they also said where to put it, "put_down" is true and "place" is where the CENTRE of the picked
object should end up:
- On another object ("on", "onto", "on top of"): "on_top" is true, and u, v lie inside that object's
  span. A named part of it, such as "the far right end of the green brick", means against that end,
  moved in by half the picked object's own size so it does not hang over the edge.
- Beside another object ("next to", "left of", "behind", ...): "on_top" is false; go to the side they
  named, or with no side named the side the picked object is on now. Leave a gap of about half the
  picked object's size between the two, and do not overlap any other object's span.
- A spot on the table ("the front left corner", "the middle"): those coordinates, "on_top" false.
Unless "on_top" is true, the picked object's span at the new place must not overlap any other
object's span: if the spot they named is taken, use the nearest free spot to it.
Keep u and v between 0.05 and 0.95. If the place they named is not there, or you cannot tell which
object they mean, "place" is null.

Return only JSON: {{"matches": [numbers], "put_down": true or false,
"place": {{"u": number, "v": number, "on_top": true or false}} or null}}. Use [] when nothing fits."""


def load_env():
    env = Path(__file__).with_name(".env")
    if env.exists():
        for line in env.read_text().splitlines():
            key, sep, value = line.partition("=")
            if sep and not key.strip().startswith("#"):
                os.environ[key.strip()] = value.strip()  # .env wins: a stale key exported in a shell broke a run


def grab_frame():
    cap = cv2.VideoCapture(CAMERA)
    for _ in range(5):  # first frames are dark while exposure settles
        ok, frame = cap.read()
    cap.release()
    if not ok:
        sys.exit(f"No frame from camera {CAMERA}. Try CAMERA=1 python see.py ...")
    return frame


def record_wav():
    import sounddevice as sd

    input("Press Enter, speak, then press Enter again... ")
    chunks = []
    with sd.InputStream(samplerate=SAMPLE_RATE, channels=1, dtype="int16",
                        callback=lambda data, *_: chunks.append(data.copy())):
        input("Listening. Speak now, then press Enter to stop. ")
    samples = b"".join(c.tobytes() for c in chunks)
    seconds = len(samples) / 2 / SAMPLE_RATE
    loudest = max((abs(int(c.min())) for c in chunks), default=0)
    print(f"Got {seconds:.1f} seconds of audio. Working on it, about 5 seconds...", flush=True)
    if seconds < 0.3 or loudest < 300:  # 300 of 32768: quieter than any speech
        print("That was silence. Check the terminal has microphone permission "
              "(System Settings > Privacy & Security > Microphone) and the right input is selected.",
              file=sys.stderr)
    path = tempfile.mkstemp(suffix=".wav")[1]
    with wave.open(path, "wb") as f:
        f.setnchannels(1)
        f.setsampwidth(2)
        f.setframerate(SAMPLE_RATE)
        f.writeframes(samples)
    return path


def parse_reply(text):
    """Pull the JSON object or list out of the reply, which may be wrapped in a code fence."""
    match = re.search(r"\[.*\]|\{.*\}", text, re.S)
    try:
        return json.loads(match.group(0)) if match else {}
    except ValueError:
        return {}  # a malformed reply counts as "nothing found", never as a guess


def ask_claude(prompt, jpg=None, model=None, max_tokens=2000):
    """One question to Claude, with an optional JPEG. Returns the reply's text."""
    import anthropic

    if not os.environ.get("ANTHROPIC_API_KEY"):
        sys.exit("ANTHROPIC_API_KEY is missing from .env.")
    content = [{"type": "text", "text": prompt}]
    if jpg:
        content.insert(0, {"type": "image", "source": {
            "type": "base64", "media_type": "image/jpeg", "data": base64.standard_b64encode(jpg).decode()}})
    reply = anthropic.Anthropic(timeout=TIMEOUT_S, max_retries=1).messages.create(
        model=model or CHOOSER, max_tokens=max_tokens, output_config={"effort": "low"},
        messages=[{"role": "user", "content": content}])
    return "".join(block.text for block in reply.content if block.type == "text")


def _openai():
    import openai

    if not os.environ.get("OPENAI_API_KEY"):
        sys.exit("OPENAI_API_KEY is missing from .env.")
    return openai.OpenAI(timeout=TIMEOUT_S, max_retries=1)


def _number(value):
    return type(value) in (int, float) and math.isfinite(value)  # bool is not a number here


def to_boxes(reply, width, height):
    """The model's reply -> pixel boxes. A malformed entry is dropped, never guessed: it needs
    four finite numbers in 0 to 1000 with ymin < ymax and xmin < xmax."""
    boxes = []
    for obj in reply if isinstance(reply, list) else []:
        box = obj.get("box_2d") if isinstance(obj, dict) else None
        if not (isinstance(box, list) and len(box) == 4 and all(_number(n) and 0 <= n <= 1000 for n in box)):
            continue
        y0, x0, y1, x1 = box
        if y0 >= y1 or x0 >= x1:
            continue
        boxes.append({"x0": int(x0 / 1000 * width), "y0": int(y0 / 1000 * height),
                      "x1": int(x1 / 1000 * width), "y1": int(y1 / 1000 * height),
                      "label": str(obj.get("label", ""))})
    return boxes


def to_matches(answer, count, key="matches"):
    """The chooser's reply -> indexes into the boxes. Only whole numbers from 1 to count."""
    matches = answer.get(key) if isinstance(answer, dict) else None
    return [n - 1 for n in matches if type(n) is int and 1 <= n <= count] if isinstance(matches, list) else []


def detect(frame):
    """Box every object. Returns dicts with pixel x0, y0, x1, y1 and a label."""
    jpg = cv2.imencode(".jpg", frame)[1].tobytes()
    answer = _openai().chat.completions.create(
        model=DETECTOR, reasoning_effort="low",
        messages=[{"role": "user", "content": [
            {"type": "image_url", "image_url": {
                "url": "data:image/jpeg;base64," + base64.standard_b64encode(jpg).decode()}},
            {"type": "text", "text": DETECT}]}])
    return to_boxes(parse_reply(answer.choices[0].message.content or ""), frame.shape[1], frame.shape[0])


def transcribe(audio_path):
    with open(audio_path, "rb") as audio:
        return _openai().audio.transcriptions.create(model=LISTENER, file=audio).text.strip() or None


def numbered(frame, boxes):
    """A copy of the frame with a green box and a number badge on each object."""
    out = frame.copy()
    scale = max(frame.shape[:2]) / 2000  # badge sized for a 2000 px photo, scaled to this frame
    for i, b in enumerate(boxes, 1):
        cv2.rectangle(out, (b["x0"], b["y0"]), (b["x1"], b["y1"]), (0, 255, 0), max(2, int(5 * scale)))
        corner = (b["x0"] + int(70 * scale), b["y0"] + int(64 * scale))
        cv2.rectangle(out, (b["x0"], b["y0"]), corner, (255, 255, 255), -1)
        cv2.rectangle(out, (b["x0"], b["y0"]), corner, (0, 0, 0), max(1, int(3 * scale)))
        cv2.putText(out, str(i), (b["x0"] + int(12 * scale), b["y0"] + int(50 * scale)),
                    cv2.FONT_HERSHEY_SIMPLEX, 1.6 * scale, (0, 0, 255), max(2, int(5 * scale)))
    return out


def choose(frame, boxes, command, describe=None, aspect=1.0):
    """Which boxes match the request, and where should the object be put?
    describe(box) gives the box's position on the table as text, so the model can work with it.
    Returns (indexes to pick up, placing, place): placing says whether the person asked to put it
    somewhere; place is {"u", "v", "on_top"} or None when that could not be worked out."""
    image = numbered(frame, boxes)
    shrink = CHOOSER_LONG_EDGE / max(image.shape[:2])
    if shrink < 1:
        image = cv2.resize(image, None, fx=shrink, fy=shrink)
    jpg = cv2.imencode(".jpg", image)[1].tobytes()
    labels = "\n".join(f"{i}: {b['label']}" + (f" - {describe(b)}" if describe else "") for i, b in enumerate(boxes, 1))
    prompt = CHOOSE.format(labels=labels, command=command, aspect=round(aspect, 2))
    return to_choice(parse_reply(ask_claude(prompt, jpg)), len(boxes))


def to_choice(answer, count):
    """The chooser's reply -> (picked indexes, placing, place). A reply without a true/false
    "put_down" is malformed: nothing is picked, so nothing moves. A place that is not two finite
    numbers and a true/false comes back as None, which the caller must refuse, never hand over."""
    if not (isinstance(answer, dict) and isinstance(answer.get("put_down"), bool)):
        return [], False, None
    place = answer.get("place")
    if not (isinstance(place, dict) and _number(place.get("u")) and _number(place.get("v"))
            and isinstance(place.get("on_top"), bool)):
        place = None
    return to_matches(answer, count), answer["put_down"] or place is not None, place


def long_axis(frame, box):
    """Which way the object in this box lies: (angle of its long side in the image in degrees,
    0 = along the image's x axis, turning towards y; how many times longer than wide it is).
    None if the object cannot be told apart from the table. Plain image processing: the table
    colour is taken from the rim of the box, and what differs from it is the object."""
    import numpy as np

    h, w = frame.shape[:2]
    pad = int(0.12 * max(box["x1"] - box["x0"], box["y1"] - box["y0"])) + 2
    x0, y0, x1, y1 = max(box["x0"] - pad, 0), max(box["y0"] - pad, 0), min(box["x1"] + pad, w), min(box["y1"] + pad, h)
    crop = cv2.cvtColor(cv2.GaussianBlur(frame[y0:y1, x0:x1], (5, 5), 0), cv2.COLOR_BGR2LAB).astype(np.float32)
    if crop.shape[0] < 12 or crop.shape[1] < 12:
        return None
    rim = np.concatenate([crop[:3].reshape(-1, 3), crop[-3:].reshape(-1, 3),
                          crop[:, :3].reshape(-1, 3), crop[:, -3:].reshape(-1, 3)])
    mask = (np.linalg.norm(crop - np.median(rim, axis=0), axis=2) > AXIS_CONTRAST).astype(np.uint8)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((7, 7), np.uint8))
    contours = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)[0]
    if not contours:
        return None
    outline = max(contours, key=cv2.contourArea)
    if cv2.contourArea(outline) < 0.15 * mask.size:
        return None
    (_, _), (rw, rh), angle = cv2.minAreaRect(outline)
    if min(rw, rh) < 1:
        return None
    return (angle if rw >= rh else angle + 90.0) % 180.0, max(rw, rh) / min(rw, rh)


def find_all(frame, command=None, audio_path=None, describe=None, aspect=1.0):
    """Every object that matches the request. Returns (hits, said, boxes, placing, place): hits are
    (x_px, y_px, label, box) at the centre of each matching box; said is what was asked; placing and
    place are as in choose()."""
    from concurrent.futures import ThreadPoolExecutor

    with ThreadPoolExecutor() as pool:  # hearing and looking run side by side
        heard = pool.submit(transcribe, audio_path) if audio_path and not command else None
        boxes = pool.submit(detect, frame).result()
        command = command or (heard.result() if heard else None)
    if not boxes or not command:
        return [], command, boxes, False, None
    centre = lambda i: ((boxes[i]["x0"] + boxes[i]["x1"]) // 2, (boxes[i]["y0"] + boxes[i]["y1"]) // 2,
                        boxes[i]["label"], boxes[i])
    picked, placing, place = choose(frame, boxes, command, describe, aspect)
    return [centre(i) for i in picked], command, boxes, placing, place


def find(frame, command=None, audio_path=None):
    """The first matching object as (x_px, y_px, label, box), or None. Prefer find_all: when two
    objects match, this picks one without saying so."""
    hits = find_all(frame, command, audio_path)[0]
    return hits[0] if hits else None


def main():
    load_env()
    args = sys.argv[1:]
    image = None
    if args[:1] == ["--image"]:
        image, args = args[1], args[2:]
    command = " ".join(args) or None
    audio = None if command else record_wav()
    frame = cv2.imread(image) if image else grab_frame()
    if frame is None:
        sys.exit(f"Could not read {image}")
    hits, said, boxes, *_ = find_all(frame, command, audio)
    out = numbered(frame, boxes)
    for x, y, *_ in hits:
        cv2.drawMarker(out, (x, y), (0, 0, 255), cv2.MARKER_CROSS, 60, 6)
    Path("outputs").mkdir(exist_ok=True)
    cv2.imwrite("outputs/last.jpg", out)
    print(f'heard "{said}", saw {len(boxes)} objects, {len(hits)} match -> outputs/last.jpg')
    for x, y, label, _ in hits:
        print(f"  {label}: pixel ({x}, {y})")


if __name__ == "__main__":
    assert parse_reply('```json\n{"matches": [2, 5]}\n```')["matches"] == [2, 5]
    assert parse_reply("nothing here") == {}
    # malformed model replies produce no target
    good = {"box_2d": [100, 200, 300, 400], "label": "brick"}
    assert to_boxes([good], 1000, 1000) == [{"x0": 200, "y0": 100, "x1": 400, "y1": 300, "label": "brick"}]
    for bad in [[900, 900, 100, 100], [100, 200, "300", 400], [100, 200, 300], [True, 200, 300, 400],
                [100, 200, float("nan"), 400], [100, 200, 300, 1400]]:
        assert to_boxes([{"box_2d": bad}], 1000, 1000) == [], bad
    assert to_boxes({"objects": [good]}, 1000, 1000) == [] and to_boxes(["x", None], 10, 10) == []
    assert to_matches({"matches": [2, 3]}, 3) == [1, 2]
    for bad in [{"matches": [True]}, {"matches": [0, 4, 1.0, "2"]}, {"matches": 2}, [1], None]:
        assert to_matches(bad, 3) == [], bad
    spot = {"u": 0.4, "v": 0.6, "on_top": True}
    assert to_choice({"matches": [1], "put_down": False, "place": None}, 3) == ([0], False, None)
    assert to_choice({"matches": [1], "put_down": True, "place": spot}, 3) == ([0], True, spot)
    assert to_choice({"matches": [1], "put_down": True, "place": None}, 3) == ([0], True, None)
    for bad in [{"u": "0.4", "v": 0.6, "on_top": True}, {"u": 0.4, "v": float("nan"), "on_top": True},
                {"u": 0.4, "v": 0.6, "on_top": 1}, [0.4, 0.6]]:
        assert to_choice({"matches": [1], "put_down": True, "place": bad}, 3) == ([0], True, None), bad
    for bad in [{"matches": [1]}, {"matches": [1], "put_down": "true"}, [1], None]:
        assert to_choice(bad, 3) == ([], False, None), bad  # a missing or non-boolean flag never becomes a handover
    main()
