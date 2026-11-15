"""RobTop's voice with no microphone, speakers or internet. Run: python -B -m tests.test_robtop_voice"""
import json
import os
import socketserver
import subprocess
import sys
import tempfile
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import robtop_voice as rv
from core import send

ROOT = Path(__file__).parent.parent

CASES = {
    # plain, wordy and noisy ones
    "Hold this for me": 'run hand {"do": "take"}',
    "can you please hold this for me": 'run hand {"do": "take"}',
    "RobTop, take this.": 'run hand {"do": "take"}',
    "hey rob top give it back": 'run hand {"do": "give"}',
    "umm could you hand it to me please": 'run hand {"do": "give"}',
    "drop it!": 'run hand {"do": "drop"}',
    "let go": 'run hand {"do": "drop"}',
    "let go of the hold": "hold off",
    "release": "hold off",
    "hold it right there": "hold on",
    "freeze": "hold on",
    "steady on": "steady on",
    "please steady my hand": "steady on",
    "filter on": "steady on",
    "steady off": "steady off",
    "filter off": "steady off",
    "okay turn it off": "steady off",
    "turn the filter off": "steady off",
    "start the test": "test",
    "wave": "run wave {}",
    "Say hi to everyone!": "run wave {}",
    "nod": 'run gesture {"name": "nod"}',
    "shake your head": 'run gesture {"name": "shake"}',
    "fist-bump": 'run gesture {"name": "fist_bump"}',
    "High five!": 'run gesture {"name": "high_five"}',
    "hi five": 'run gesture {"name": "high_five"}',
    "do a little dance": 'run gesture {"name": "dance"}',
    "RobTop go home": "home",
    # stop wins, wherever it is and whatever else was said
    "stop": "stop",
    "STOP STOP STOP": "stop",
    "wave and then stop": "stop",
    "drop it, no, stop": "stop",
    "stop the shaking": "stop",
    "stop the steadying": "stop",
    "I held the stop sign": "stop",  # documented: any "stop" word stops, even in a sentence like this
    "halt": "stop",
    # traps, decided: an "off" never starts movement, so this freezes instead of steadying
    "steady as she goes off we went": "steady off",
    "steady as she goes": "steady on",
    # near misses that must not match
    "what time is it": None,
    "the dancer nodded": None,
    "drop the ball": None,
    "shake hands": None,
    "he held the door": None,
    "rob top": None,
    "": None,
}


def test_phrases():
    for heard, line in CASES.items():
        assert rv.understand(heard)[0] == line, (heard, rv.understand(heard), line)
    assert rv.understand("what time is it") == (None, rv.SORRY)
    # a spoken phrase can never send filter off: that switch is only for the keypad, dashboard or typing
    lines = {line for line, _ in rv.PHRASES.values()} | {rv.STOP[0]}
    assert "filter off" not in lines and "filter on" not in lines
    for heard in list(CASES) + [p + " off" for p in rv.PHRASES] + ["filter off " + p for p in rv.PHRASES]:
        assert rv.understand(heard)[0] != "filter off", heard


class FakeElevenLabs(BaseHTTPRequestHandler):
    mode, seen = "ok", []

    def do_POST(self):
        body = self.rfile.read(int(self.headers["Content-Length"]))
        FakeElevenLabs.seen.append((self.path, self.headers.get("xi-api-key"), self.headers.get("Content-Type"), body))
        if self.mode == "slow":  # longer than the client's timeout; it has hung up by then
            time.sleep(1)
            return
        if self.mode == "401":
            self.send_error(401)
            return
        out = json.dumps({"text": "hold this for me", "words": []}).encode() if "speech-to-text" in self.path \
            else b"\x01\x00\x02\x00"
        self.send_response(200)
        self.send_header("Content-Length", str(len(out)))
        self.end_headers()
        self.wfile.write(out)

    def log_message(self, *_):
        pass


def test_http():
    server = ThreadingHTTPServer(("127.0.0.1", 0), FakeElevenLabs)
    server.daemon_threads = True
    threading.Thread(target=server.serve_forever, daemon=True).start()
    saved = (rv.API, rv.TIMEOUT_S, rv.play, rv.windows_say, rv.see.record_wav,
             os.environ.get("ELEVENLABS_API_KEY"))
    rv.API, rv.TIMEOUT_S = f"http://127.0.0.1:{server.server_port}", 0.3
    os.environ["ELEVENLABS_API_KEY"] = "test-key"
    played, windows = [], []
    rv.play, rv.windows_say = played.append, windows.append
    wav = b"RIFF fake wav bytes"

    def record():
        path = tempfile.mkstemp(suffix=".wav")[1]
        Path(path).write_bytes(wav)
        return path

    rv.see.record_wav = record
    try:
        # speech to text: key, model, the audio itself, and the transcript comes back
        assert rv.hear() == "hold this for me"
        path, key, kind, body = FakeElevenLabs.seen[-1]
        assert path == "/v1/speech-to-text" and key == "test-key" and kind.startswith("multipart/form-data")
        assert wav in body and b'name="model_id"\r\n\r\n' + rv.STT_MODEL.encode() in body and b'name="file"' in body
        # text to speech: the PCM bytes reach the player, the Windows voice stays silent
        rv.speak("Here you go.")
        path, key, kind, body = FakeElevenLabs.seen[-1]
        assert path == f"/v1/text-to-speech/{rv.VOICE}?output_format=pcm_{rv.TTS_RATE}" and key == "test-key"
        assert json.loads(body) == {"text": "Here you go.", "model_id": rv.TTS_MODEL}
        assert played == [b"\x01\x00\x02\x00"] and windows == []
        # a 401 and a timeout fall back without raising
        for mode in ("401", "slow"):
            FakeElevenLabs.mode = mode
            assert rv.hear() is None
            rv.speak("Hello!")
            assert windows[-1] == "Hello!" and len(played) == 1, mode
        # no key: the Windows voice, and nothing sent
        del os.environ["ELEVENLABS_API_KEY"]
        count = len(FakeElevenLabs.seen)
        rv.speak("Yes.")
        assert windows[-1] == "Yes." and len(FakeElevenLabs.seen) == count
    finally:
        FakeElevenLabs.mode = "ok"
        rv.API, rv.TIMEOUT_S, rv.play, rv.windows_say, rv.see.record_wav, key = saved
        if key is None:
            os.environ.pop("ELEVENLABS_API_KEY", None)
        else:
            os.environ["ELEVENLABS_API_KEY"] = key
        server.shutdown()


def test_tcp():
    lines, replies = [], {}

    class Fake(socketserver.StreamRequestHandler):
        def handle(self):
            for raw in self.rfile:
                line = raw.decode().strip()
                lines.append(line)
                self.wfile.write((json.dumps(replies.get(line, {"ok": False, "reason": "unknown"})) + "\n").encode())

    server = socketserver.ThreadingTCPServer(("127.0.0.1", 0), Fake)
    server.daemon_threads = True
    threading.Thread(target=server.serve_forever, daemon=True).start()
    saved, said = (send.PORT, rv.speak), []
    send.PORT, rv.speak = server.server_address[1], said.append
    try:
        # dispatcher takes the hand skill; the dashboard line follows
        replies['run hand {"do": "take"}'] = {"ok": True, "reason": "started", "job": 1}
        assert rv.exchange("hold this for me") == ('run hand {"do": "take"}', "I have it.")
        assert lines[-2:] == ['run hand {"do": "take"}', 'voice {"heard": "hold this for me", "said": "I have it."}']
        # the teleoperation does not know gestures
        replies['run gesture {"name": "nod"}'] = {"ok": False, "reason": "commands: steady on|off, hold on|off, "
                                                  "cutoff <Hz>, test, status, quit"}
        assert rv.exchange("nod")[1] == rv.CANT_STEADY and said[-1] == rv.CANT_STEADY
        # the teleoperation says ok to home but does nothing
        replies["home"] = {"ok": True, "steady": True, "hold": False, "cutoff": 3.0}
        assert rv.exchange("go home")[1] == rv.CANT_STEADY
        # the dispatcher does not know teleoperation commands
        replies["hold on"] = {"ok": False, "reason": "commands: run <skill> [json params] | stop | home | list"}
        assert rv.exchange("freeze")[1] == rv.ONLY_STEADY
        replies["stop"] = {"ok": True, "steady": True, "hold": True, "cutoff": 3.0}
        assert rv.exchange("stop")[1] == "Stopped."
        replies["run wave {}"] = {"ok": False, "reason": "busy"}
        assert "busy" in rv.exchange("wave")[1]
        # unknown speech sends no command, only the dashboard line
        count = len(lines)
        assert rv.exchange("what time is it") == (None, rv.SORRY)
        assert lines[count:] == ['voice {"heard": "what time is it", "said": "Sorry, I did not catch that."}']
    finally:
        server.shutdown()
        server.server_close()
    # nothing listening: a plain answer, no crash
    assert rv.exchange("wave")[1] == rv.OFF
    send.PORT, rv.speak = saved


def test_cli_dry():
    out = subprocess.run([sys.executable, "-B", "robtop_voice.py", "--text", "hold this for me", "--dry"],
                         cwd=ROOT, capture_output=True, text=True, timeout=60)
    assert out.returncode == 0, out.stderr
    assert 'would send: run hand {"do": "take"}' in out.stdout and "RobTop: I have it." in out.stdout, out.stdout
    assert 'would send: voice {"heard": "hold this for me", "said": "I have it."}' in out.stdout


if __name__ == "__main__":
    test_phrases()
    test_http()
    test_tcp()
    test_cli_dry()
    print("robtop voice ok")
