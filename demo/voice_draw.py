"""Start a drawing by voice. Push to talk: Enter, say it, Enter.

    python demo/voice_draw.py                       # microphone
    python demo/voice_draw.py --text "draw a flower" # typed, no microphone
    python demo/voice_draw.py --text "play tic tac toe" --dry   # only print what it would run

Say: "draw a flower", "draw a house", "draw a heart", "play tic tac toe" (or "game", "noughts and crosses").
Listening and the spoken reply are ElevenLabs, through robtop_voice.py (needs ELEVENLABS_API_KEY in .env).
The drawing programs take the arm themselves, so the dispatcher must NOT be running: this is for the pen demo,
robtop_voice.py is for gestures. One drawing at a time; when it ends you are asked again.
"""
import argparse
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import robtop_voice as voice
import see

DRAW = {"flower": ("flower.json", "state_flower.json"), "house": ("house.json", "state_house.json"), "heart": ("heart.json", "state_heart.json")}
GAME = ("tic", "tac", "toe", "game", "noughts", "crosses", "x and o", "xs and os")


def choose(text: str):
    """(what to say, command to run or None) for what was heard."""
    said = voice.normalise(text)
    for name, (strokes, state) in DRAW.items():
        if name in said:
            env = {"USED": "1", "OVERDRAW": "1", "FAST": "1", "STATE": state}
            return f"Drawing a {name}.", ([sys.executable, str(ROOT / "demo" / "loop.py"), str(ROOT / "demo" / strokes)], env)
    if any(word in said for word in GAME):
        return "Let's play. You are X.", ([sys.executable, str(ROOT / "demo" / "ttt2.py")], {"ANY": "1"})
    return "I can draw a flower, a house or a heart, or play tic tac toe.", None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--text", help="one request from this text instead of the microphone")
    parser.add_argument("--dry", action="store_true", help="print what would be said and run; no sound, no arm")
    args = parser.parse_args()
    see.load_env()
    while True:
        if args.text:
            heard = args.text
        else:
            heard = voice.hear()
            if not heard:
                continue
        say, run = choose(heard)
        print(f"heard: {heard!r}\nRobTop: {say}", flush=True)
        if args.dry:
            print("would run:", None if run is None else " ".join(run[0][1:]) + "  " + str(run[1]), flush=True)
        else:
            voice.speak(say)
            if run is not None:
                subprocess.call(run[0], env={**os.environ, **run[1]}, cwd=str(ROOT))
        if args.text:
            return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        pass
