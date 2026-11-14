"""Hear or read a request, find the object in the camera frame, return its pixel.

    python see.py "pick up the red lego brick"   # typed command
    python see.py                                # speak: Enter to start, Enter to stop
    python see.py --image photo.jpg "the mouse"  # test on a still photo

Saves the annotated frame to outputs/last.jpg. Needs GEMINI_API_KEY (put it in .env).
"""
import json
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
CAMERA = int(os.environ.get("CAMERA", "0"))  # index of the overhead camera
TIMEOUT_MS = 8000  # a normal answer takes 1 to 2 seconds; give up early and retry
RETRY_SECONDS = 3
SAMPLE_RATE = 16000

PROMPT = """You guide a robot arm that picks objects off a table.
{request}
First list every object you can see on the table. Then decide whether one of them
is what the person asked for. A different kind of object is not a match.
If there is a match, point to the spot where a two-finger gripper should close on it
(the middle of its narrowest graspable part).
Return only JSON: {{"seen": ["..."], "match": true or false, "point": [y, x], "label": "<short name>"}}
Points are [y, x] normalized to 0-1000. Use "point": null when match is false."""


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
        input("Listening. Enter to stop. ")
    path = tempfile.mkstemp(suffix=".wav")[1]
    with wave.open(path, "wb") as f:
        f.setnchannels(1)
        f.setsampwidth(2)
        f.setframerate(SAMPLE_RATE)
        f.writeframes(b"".join(c.tobytes() for c in chunks))
    return path


def parse_reply(text):
    """Pull the JSON object out of the reply, which may be wrapped in a code fence."""
    match = re.search(r"\{.*\}", text, re.S)
    return json.loads(match.group(0)) if match else {}


def find(frame, command=None, audio_path=None):
    """Return (x_px, y_px, label) for the requested object, or None if not seen."""
    from google import genai
    from google.genai import types

    client = genai.Client(http_options=types.HttpOptions(timeout=TIMEOUT_MS))
    jpg = cv2.imencode(".jpg", frame)[1].tobytes()
    parts = [types.Part.from_bytes(data=jpg, mime_type="image/jpeg")]
    if audio_path:
        parts.append(types.Part.from_bytes(data=Path(audio_path).read_bytes(), mime_type="audio/wav"))
    request = (f'The person said: "{command}"' if command
               else "The person's spoken request is in the audio.")
    parts.append(PROMPT.format(request=request))
    for attempt in (1, 2):  # the free tier sometimes refuses a burst of requests; one retry covers it
        try:
            reply = client.models.generate_content(model=MODEL, contents=parts)
            break
        except Exception as err:
            print(f"Gemini error (attempt {attempt}): {str(err)[:200]}", file=sys.stderr)
            if attempt == 2:
                raise
            time.sleep(RETRY_SECONDS)
    hit = parse_reply(reply.text or "")
    if not hit.get("match") or not hit.get("point"):
        return None
    y, x = hit["point"]
    h, w = frame.shape[:2]
    return int(x / 1000 * w), int(y / 1000 * h), hit.get("label", "")


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
    hit = find(frame, command, audio)
    if not hit:
        print("Not found")
        return
    x, y, label = hit
    cv2.drawMarker(frame, (x, y), (0, 0, 255), cv2.MARKER_CROSS, 40, 3)
    cv2.putText(frame, label, (x + 15, y - 15), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)
    Path("outputs").mkdir(exist_ok=True)
    cv2.imwrite("outputs/last.jpg", frame)
    print(f"{label}: pixel ({x}, {y}) -> outputs/last.jpg")


if __name__ == "__main__":
    assert parse_reply('```json\n{"match": true, "point": [376, 508]}\n```')["point"] == [376, 508]
    assert parse_reply("nothing here") == {}
    main()
