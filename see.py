"""Hear or read a request and find the matching objects in the camera frame.

    python see.py "pick up the red brick"        # typed command
    python see.py                                # speak: Enter to start, Enter to stop
    python see.py --image photo.jpg "the mouse"  # test on a still photo

Two steps, because no single model did both well on our Duplo photos (notes/eddy.md):
  1. Gemini draws a box around every object on the table. It is accurate at where.
  2. Claude sees the boxes numbered and says which numbers match the request. It is
     accurate at which, including "there are two of those".
Saves the annotated frame to outputs/last.jpg.
Needs GEMINI_API_KEY and ANTHROPIC_API_KEY in .env. Without the Anthropic key, Gemini
does step 2 as well, and gets look-alike pieces wrong more often.
"""
import base64
import json
import math
import os
import re
import sys
import tempfile
import time
import wave
from pathlib import Path

import cv2

# gemini-3.8-flash timed out on Nov 13; the robotics-ER models are not on our key
MODEL = os.environ.get("GEMINI_MODEL", "gemini-3.5-flash-lite")
CHOOSER = os.environ.get("CHOOSER_MODEL", "claude-sonnet-5-5")
CAMERA = int(os.environ.get("CAMERA", "0"))  # index of the overhead camera
TIMEOUT_MS = 10000  # Gemini rejects anything under 10 seconds; a normal answer takes 1 to 2
RETRY_SECONDS = 3
SAMPLE_RATE = 16000
CHOOSER_LONG_EDGE = 1024  # the numbered image is shrunk to this before it goes to the chooser

# Keep this prompt as a bare list. Wrapping it in an object, or asking for the transcript in the
# same call, made gemini-3.5-flash-lite return malformed JSON on Nov 14.
DETECT = """Detect every separate physical object lying on the table. Two objects that touch are
still two objects. Do not skip any object, whatever its colour, and do not report shadows or
marks on the table.
Return only JSON: [{"box_2d": [ymin, xmin, ymax, xmax], "label": "<colour and shape>"}]
Coordinates are normalized to 0-1000."""

TRANSCRIBE = 'Write down exactly what the person says in the audio. Return only JSON: {"said": "..."}'

# ponytail: the hint names our Duplo set. Edit it when the objects on the table change.
CHOOSE = """A robot arm picks objects off a table. Each object in the image has a green box and a
numbered badge. The detector's own guesses (may be wrong; trust the image): {labels}
The pieces may be LEGO Duplo. A piece may lie on its side or upside down, showing its hollow
underside. People call the 2x4 brick with a sloped top the "triangle" brick; from below it shows
three round holes in a row. One box may hold two touching pieces.
The person said: "{command}"
Which numbered objects are what the person asked for? Include every one that fits; a different
kind of object does not fit. Return only JSON: {{"matches": [numbers]}}. Use [] if none fit."""


def load_env():
    env = Path(__file__).with_name(".env")
    if env.exists():
        for line in env.read_text().splitlines():
            key, sep, value = line.partition("=")
            if sep and not key.strip().startswith("#"):
                os.environ.setdefault(key.strip(), value.strip())


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


def _gemini(parts):
    from google import genai
    from google.genai import types

    client = genai.Client(http_options=types.HttpOptions(timeout=TIMEOUT_MS))
    parts = [types.Part.from_bytes(data=p[0], mime_type=p[1]) if isinstance(p, tuple) else p for p in parts]
    for attempt in (1, 2, 3):  # the free tier refuses bursts (429), stalls, and has busy spells (503)
        try:
            return parse_reply(client.models.generate_content(model=MODEL, contents=parts).text or "")
        except Exception as err:
            print(f"Gemini error (attempt {attempt}): {str(err)[:200]}", file=sys.stderr)
            if attempt == 3:
                raise
            time.sleep(RETRY_SECONDS)


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


def to_matches(answer, count):
    """The chooser's reply -> indexes into the boxes. Only whole numbers from 1 to count."""
    matches = answer.get("matches") if isinstance(answer, dict) else None
    return [n - 1 for n in matches if type(n) is int and 1 <= n <= count] if isinstance(matches, list) else []


def detect(frame):
    """Box every object. Returns dicts with pixel x0, y0, x1, y1 and a label."""
    reply = _gemini([(cv2.imencode(".jpg", frame)[1].tobytes(), "image/jpeg"), DETECT])
    return to_boxes(reply, frame.shape[1], frame.shape[0])


def transcribe(audio_path):
    reply = _gemini([(Path(audio_path).read_bytes(), "audio/wav"), TRANSCRIBE])
    return reply.get("said") if isinstance(reply, dict) else None


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


def choose(frame, boxes, command):
    """Which boxes match the request? Returns a list of indexes into boxes."""
    image = numbered(frame, boxes)
    shrink = CHOOSER_LONG_EDGE / max(image.shape[:2])
    if shrink < 1:
        image = cv2.resize(image, None, fx=shrink, fy=shrink)
    jpg = cv2.imencode(".jpg", image)[1].tobytes()
    prompt = CHOOSE.format(labels=", ".join(f"{i}: {b['label']}" for i, b in enumerate(boxes, 1)),
                           command=command)
    if os.environ.get("ANTHROPIC_API_KEY"):
        import anthropic

        reply = anthropic.Anthropic(timeout=TIMEOUT_MS / 1000 * 2, max_retries=1).messages.create(
            model=CHOOSER, max_tokens=2000, output_config={"effort": "low"},
            messages=[{"role": "user", "content": [
                {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg",
                                             "data": base64.standard_b64encode(jpg).decode()}},
                {"type": "text", "text": prompt}]}])
        answer = parse_reply("".join(b.text for b in reply.content if b.type == "text"))
    else:
        print("No ANTHROPIC_API_KEY: Gemini is choosing, which is less reliable.", file=sys.stderr)
        answer = _gemini([(jpg, "image/jpeg"), prompt])
    return to_matches(answer, len(boxes))


def find_all(frame, command=None, audio_path=None):
    """Every object that matches the request. Returns (hits, said, boxes): hits are
    (x_px, y_px, label) at the centre of each matching box; said is what was asked."""
    from concurrent.futures import ThreadPoolExecutor

    with ThreadPoolExecutor() as pool:  # hearing and looking run side by side
        heard = pool.submit(transcribe, audio_path) if audio_path and not command else None
        boxes = pool.submit(detect, frame).result()
        command = command or (heard.result() if heard else None)
    if not boxes or not command:
        return [], command, boxes
    answer = choose(frame, boxes, command)
    hits = [((boxes[i]["x0"] + boxes[i]["x1"]) // 2, (boxes[i]["y0"] + boxes[i]["y1"]) // 2, boxes[i]["label"])
            for i in answer]
    return hits, command, boxes


def find(frame, command=None, audio_path=None):
    """The first matching object as (x_px, y_px, label), or None. Prefer find_all: when two
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
    hits, said, boxes = find_all(frame, command, audio)
    out = numbered(frame, boxes)
    for x, y, _ in hits:
        cv2.drawMarker(out, (x, y), (0, 0, 255), cv2.MARKER_CROSS, 60, 6)
    Path("outputs").mkdir(exist_ok=True)
    cv2.imwrite("outputs/last.jpg", out)
    print(f'heard "{said}", saw {len(boxes)} objects, {len(hits)} match -> outputs/last.jpg')
    for x, y, label in hits:
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
    main()
