"""RobTop's voice: push to talk, ElevenLabs writes it down, a phrase table picks the command, RobTop
answers out loud.

    python robtop_voice.py                              # Enter, speak, Enter. Ctrl+C to quit.
    python robtop_voice.py --text "hold this for me"    # one exchange from typed text, no microphone
    python robtop_voice.py --text "wave" --dry          # print what would be sent and said; no socket, no sound

Push to talk is the noise filter for a loud room: nothing is heard unless the person asks.
Commands go as one line to 127.0.0.1:BUDDY_PORT (8765), to whichever program listens there: the
teleoperation (steady.py) or the dispatcher (core/dispatcher.py). A command the listener does not
know gets a plain spoken explanation. After each exchange the line voice {"heard", "said"} goes to
the same port for the dashboard.

.env:  ELEVENLABS_API_KEY=...     (required for listening; without it run robtop_listen.ps1)
       ELEVENLABS_VOICE_ID=...    (optional; default below)
No key, or ElevenLabs fails: RobTop speaks with the Windows voice (System.Speech).

ElevenLabs REST API, checked 2026-11-14:
  speech to text  POST /v1/speech-to-text, multipart: file, model_id; reply JSON "text"
                  https://elevenlabs.io/docs/api-reference/speech-to-text/convert
  text to speech  POST /v1/text-to-speech/{voice_id}?output_format=pcm_24000, JSON: text, model_id
                  https://elevenlabs.io/docs/api-reference/text-to-speech/convert
  model ids       https://elevenlabs.io/docs/overview/models
Both take the key in the xi-api-key header. pcm_* is raw mono samples with no header; the docs do
not state the sample width, and 16-bit signed little-endian is assumed (as the STT input format is).
"""
import argparse
import json
import os
import re
import subprocess
import sys
import urllib.request
import uuid
from pathlib import Path

import see
from core import send

API = "https://api.elevenlabs.io"
STT_MODEL = os.environ.get("ELEVENLABS_STT_MODEL", "scribe_v2")          # batch Scribe, the docs' example
TTS_MODEL = os.environ.get("ELEVENLABS_TTS_MODEL", "eleven_flash_v2_5")  # ~100 ms, the fastest listed
VOICE = os.environ.get("ELEVENLABS_VOICE_ID", "JBFqnCBsd6RMkjVDRZzb")    # the docs' example voice
TTS_RATE = 24000  # pcm_44100 needs the Pro tier
TIMEOUT_S = 15

SORRY = "Sorry, I did not catch that."
CANT_STEADY = "I can't do that while I'm steadying your hand."
ONLY_STEADY = "I can only do that while I'm steadying your hand."
OFF = "My arm is not switched on."

STEADY_ON = ("steady on", "Steadying your hand.")
FREEZE = ("steady off", "Holding still.")  # steady.py: steady off freezes the arm. No phrase ever sends filter off.
HOLD = ("hold on", "Holding still.")
RELEASE = ("hold off", "Released.")
TEST = ("test", "Starting the ten second test. Hold still.")
TAKE = ('run hand {"do": "take"}', "I have it.")
GIVE = ('run hand {"do": "give"}', "Here you go.")
DROP = ('run hand {"do": "drop"}', "Dropping it.")
# "run wave {}", never bare "run wave": steady.py reads that exact line as the keypad's steady toggle
WAVE = ("run wave {}", "Hello!")
NOD = ('run gesture {"name": "nod"}', "Yes.")
SHAKE = ('run gesture {"name": "shake"}', "No.")
BUMP = ('run gesture {"name": "fist_bump"}', "Boom.")
FIVE = ('run gesture {"name": "high_five"}', "Up top!")
DANCE = ('run gesture {"name": "dance"}', "Watch this.")
HOME = ("home", "Going home.")
STOP = ("stop", "Stopped.")

# phrase -> command. A phrase matches when its words appear in a row anywhere in what was heard.
PHRASES = {
    "steady": STEADY_ON, "steady on": STEADY_ON, "steady my hand": STEADY_ON, "steady hand": STEADY_ON,
    "filter on": STEADY_ON, "turn on the filter": STEADY_ON,
    "steady off": FREEZE, "filter off": FREEZE, "turn off the filter": FREEZE, "turn off steady": FREEZE,
    "turn it off": FREEZE,
    "hold": HOLD, "hold it": HOLD, "hold on": HOLD, "hold still": HOLD, "freeze": HOLD,
    "release": RELEASE, "let go of the hold": RELEASE, "unfreeze": RELEASE, "hold off": RELEASE,
    "start the test": TEST, "start test": TEST, "run the test": TEST, "do the test": TEST,
    "take this": TAKE, "take it": TAKE, "hold this": TAKE, "grab this": TAKE,
    "give it back": GIVE, "hand it to me": GIVE, "give it to me": GIVE,
    "drop it": DROP, "drop this": DROP, "let go": DROP,
    "wave": WAVE, "say hi": WAVE, "say hello": WAVE,
    "nod": NOD, "nod your head": NOD,
    "shake your head": SHAKE,
    "fist bump": BUMP,
    "high five": FIVE, "hi five": FIVE,
    "dance": DANCE,
    "go home": HOME, "home": HOME,
}
# Either word anywhere means stop, whatever else was said: "stop the shaking" and "stop the steadying"
# stop too (in steady.py that freezes the arm), because steady on now releases a hold and moves.
STOP_WORDS = {"stop", "halt"}
NEGATIVES = {"dont", "not", "never", "no", "cant", "cannot", "wont", "shouldnt", "stay"}  # after normalise(): no apostrophes
NOT_SURE = "I heard a no in that, so I did nothing. Say stop if you want me to freeze."
TWO_THINGS = "I heard two different things, so I did nothing. Say just one."


def normalise(text: str) -> str:
    words = re.sub(r"[^a-z0-9 ]", " ", text.lower().replace("'", "")).split()
    return re.sub(r"^(hey |ok |okay )?rob ?top\b ?", "", " ".join(words))


def understand(text: str):
    """(command line, reply), or (None, SORRY). A stop word wins; otherwise the longest matching phrase.
    "off" anywhere turns steady on into the freeze: "steady as she goes off we went" holds still."""
    heard = normalise(text)
    words = heard.split()
    if STOP_WORDS & set(words):
        return STOP
    # "don't release", "do not go home": matching words would do the very thing the person said NOT
    # to do. A negative never becomes an action; the person can say "stop" or "hold" to freeze.
    if NEGATIVES & set(words):
        return None, NOT_SURE
    found = [p for p in PHRASES if f" {p} " in f" {heard} "]
    if not found:
        return None, SORRY
    # "go home ... stay here", "release ... hold": two different requests in one breath. Phrases that
    # sit inside a longer matched phrase ("hold" inside "hold this") are the same request, not a second.
    whole = [p for p in found if not any(p != q and f" {p} " in f" {q} " for q in found)]
    if len({PHRASES[p] for p in whole}) > 1:
        return None, TWO_THINGS
    best = PHRASES[max(found, key=lambda p: len(p.split()))]
    return FREEZE if best == STEADY_ON and "off" in words else best


def explain(line: str, said: str, reply) -> str:
    """What to say, given the listener's reply to the line."""
    if reply is None:
        return OFF
    teleop_command = line.split()[0] in ("steady", "hold", "test")
    if reply.get("ok"):
        if not teleop_command and line != "stop" and "steady" in reply:
            return CANT_STEADY  # steady.py answers ok to "home" but does nothing with it
        return said
    reason = str(reply.get("reason", ""))
    if reason == "busy":
        return "One moment, I'm still busy."
    if "steady on|off" in reason:   # steady.py's list of what it knows
        return CANT_STEADY
    if reason.startswith("commands: run"):  # the dispatcher's
        return ONLY_STEADY
    return "Sorry, that did not work."


def tell(line: str):
    """One line to the robot; its JSON reply, or None if nothing is listening."""
    try:
        return send.ask(line)
    except (OSError, ValueError):
        return None


def _post(path: str, body: bytes, kind: str) -> bytes:
    request = urllib.request.Request(API + path, data=body, method="POST",
                                     headers={"xi-api-key": os.environ["ELEVENLABS_API_KEY"], "Content-Type": kind})
    with urllib.request.urlopen(request, timeout=TIMEOUT_S) as response:
        return response.read()


def transcribe(wav: bytes) -> str:
    boundary = uuid.uuid4().hex
    parts = [f'--{boundary}\r\nContent-Disposition: form-data; name="{k}"\r\n\r\n{v}\r\n'.encode()
             for k, v in (("model_id", STT_MODEL), ("language_code", "en"), ("tag_audio_events", "false"))]
    parts.append(f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="speech.wav"\r\n'
                 f"Content-Type: audio/wav\r\n\r\n".encode() + wav + f"\r\n--{boundary}--\r\n".encode())
    reply = _post("/v1/speech-to-text", b"".join(parts), f"multipart/form-data; boundary={boundary}")
    return json.loads(reply)["text"]


def synthesise(text: str) -> bytes:
    body = json.dumps({"text": text, "model_id": TTS_MODEL}).encode()
    return _post(f"/v1/text-to-speech/{VOICE}?output_format=pcm_{TTS_RATE}", body, "application/json")


def play(pcm: bytes) -> None:
    import numpy as np
    import sounddevice as sd

    sd.play(np.frombuffer(pcm[: len(pcm) // 2 * 2], "<i2"), TTS_RATE)
    sd.wait()  # blocks, so RobTop never listens while it speaks


def windows_say(text: str) -> None:
    clean = re.sub(r"[^A-Za-z0-9 ,.?!']", "", text).replace("'", "''")
    try:
        subprocess.run(["powershell", "-NoProfile", "-Command", "Add-Type -AssemblyName System.Speech; "
                        f"(New-Object System.Speech.Synthesis.SpeechSynthesizer).Speak('{clean}')"],
                       creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0), check=False)
    except OSError:
        pass  # no PowerShell: the printed line is enough


def speak(text: str) -> None:
    print(f"RobTop: {text}", flush=True)
    if os.environ.get("ELEVENLABS_API_KEY"):
        try:
            play(synthesise(text))
            return
        except (OSError, ValueError) as err:  # HTTPError, timeouts and no audio device are all OSError
            print(f"ElevenLabs voice failed ({err}); using the Windows voice.", flush=True)
    windows_say(text)


def hear():
    """Push to talk, then ElevenLabs writes it down. None if that failed."""
    # ponytail: the temp wav is left behind, as see.py's callers do; its open mkstemp handle blocks a delete
    try:
        return transcribe(Path(see.record_wav()).read_bytes())
    except (OSError, ValueError, KeyError) as err:
        print(f"Could not write that down ({err}). Try again.", flush=True)
        return None


def exchange(text: str, dry: bool = False):
    line, said = understand(text)
    if line and not dry:
        said = explain(line, said, tell(line))
    status = "voice " + json.dumps({"heard": text, "said": said})
    if dry:
        print(f"would send: {line or 'nothing'}\nwould send: {status}\nRobTop: {said}", flush=True)
    else:
        print(f"heard '{text}' -> {line or 'nothing'}", flush=True)
        tell(status)  # for the dashboard; both listeners reject it, which is fine
        speak(said)
    return line, said


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="RobTop's push-to-talk voice")
    parser.add_argument("--text", help="one exchange from this text instead of the microphone")
    parser.add_argument("--dry", action="store_true", help="print the command and reply; send and say nothing")
    args = parser.parse_args(argv)
    see.load_env()
    if args.text is not None:
        exchange(args.text, args.dry)
        return 0
    if not os.environ.get("ELEVENLABS_API_KEY"):
        print("No ELEVENLABS_API_KEY in .env. To talk to RobTop without one, run: "
              "powershell -ExecutionPolicy Bypass -File robtop_listen.ps1", flush=True)
        return 1
    print("RobTop is listening when you press Enter. Ctrl+C to quit.", flush=True)
    try:
        while True:
            text = hear()
            if text is not None:
                exchange(text, args.dry)
    except (KeyboardInterrupt, EOFError):
        return 0


if __name__ == "__main__":
    sys.exit(main())
