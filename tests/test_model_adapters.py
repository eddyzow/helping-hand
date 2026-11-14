"""Fake API clients, speech and transport only: python -m tests.test_model_adapters."""
import ast
import base64
import contextlib
import io
import json
import math
import re
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from tests.test_perception_boundaries import functions


def test_adapters():
    configs, requests, audio_files = [], [], []
    detector_reply = '[{"box_2d":[100,200,300,400],"label":"brick"}]'

    def detect_reply(**kwargs):
        requests.append(kwargs)
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=detector_reply))])

    def transcript(**kwargs):
        audio_files.append(kwargs["file"])
        assert kwargs["file"].read() == b"fake audio"
        return SimpleNamespace(text="  wave  ")

    def claude_reply(**kwargs):
        requests.append(kwargs)
        return SimpleNamespace(content=[SimpleNamespace(type="thinking"),
                                        SimpleNamespace(type="text", text="ok")])

    openai_client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=detect_reply)),
                                    audio=SimpleNamespace(transcriptions=SimpleNamespace(create=transcript)))
    claude_client = SimpleNamespace(messages=SimpleNamespace(create=claude_reply))
    scope = {"os": SimpleNamespace(environ={"OPENAI_API_KEY": "fake", "ANTHROPIC_API_KEY": "fake"}),
             "sys": sys, "base64": base64, "json": json, "re": re, "math": math,
             "TIMEOUT_S": 30.0, "CHOOSER": "chooser", "DETECTOR": "detector", "LISTENER": "listener",
             "DETECT": "detect", "cv2": SimpleNamespace(
                 imencode=lambda *args: (True, SimpleNamespace(tobytes=lambda: b"jpeg")))}
    functions("see.py", {"ask_claude", "_openai", "parse_reply", "_number", "to_boxes", "detect", "transcribe"}, scope)
    with patch.dict(sys.modules, {
        "openai": SimpleNamespace(OpenAI=lambda **kwargs: (configs.append(kwargs) or openai_client)),
        "anthropic": SimpleNamespace(Anthropic=lambda **kwargs: (configs.append(kwargs) or claude_client))}):
        frame = SimpleNamespace(shape=(100, 200, 3))
        assert scope["detect"](frame) == [{"x0": 40, "y0": 10, "x1": 80, "y1": 30, "label": "brick"}]
        detector_reply = "not JSON"
        assert scope["detect"](frame) == []
        assert scope["ask_claude"]("question", b"jpeg", model="override", max_tokens=17) == "ok"
        assert requests[-1]["model"] == "override" and requests[-1]["max_tokens"] == 17
        assert requests[-1]["messages"][0]["content"][0]["source"]["data"] == "anBlZw=="
        with tempfile.TemporaryDirectory() as temporary:
            audio = Path(temporary) / "fake.wav"
            audio.write_bytes(b"fake audio")
            assert scope["transcribe"](audio) == "wave"
        assert audio_files[0].closed
        assert all(config == {"timeout": 30.0, "max_retries": 1} for config in configs)
        scope["os"].environ.clear()
        before = len(configs)
        for call in (scope["_openai"], lambda: scope["ask_claude"]("question")):
            try:
                call()
            except SystemExit:
                pass
            else:
                raise AssertionError("missing key was accepted")
        assert len(configs) == before


def test_voice_and_drawing():
    commands, spoken, recordings = [], [], []
    reply = '{"skill":"wave","params":{}}'
    transcript = "wave"
    parser = {"json": json, "re": re}
    functions("see.py", {"parse_reply"}, parser)
    see = SimpleNamespace(ask_claude=lambda *args, **kwargs: reply,
                          parse_reply=parser["parse_reply"], load_env=lambda: None,
                          record_wav=lambda: (recordings.append(1) or "fake.wav"),
                          transcribe=lambda path: transcript)
    source = Path(__file__).resolve().parents[1] / "voice" / "route.py"
    prompt = next(ast.literal_eval(node.value) for node in ast.parse(source.read_text()).body
                  if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "PROMPT" for t in node.targets))
    with tempfile.TemporaryDirectory() as temporary, patch.dict(sys.modules, {"see": see}):
        scope = {"sys": sys, "Path": Path, "json": json, "PROMPT": prompt,
                 "os": SimpleNamespace(environ={"ANTHROPIC_API_KEY": "fake"}),
                 "__file__": str(Path(temporary) / "voice" / "route.py"), "speak": spoken.append,
                 "send": lambda command: (commands.append(command) or
                     ([{"name": "wave"}] if command == "list" else {"ok": True}))}
        functions("voice/route.py", {"by_model", "main"}, scope)
        for argv, model_reply, heard, runs in (
            (["route", "wave"], reply, "wave", 1),
            (["route", "wave"], "[]", "wave", 0),
            (["route", "wave"], "not JSON", "wave", 0),
            (["route"], reply, "wave", 1),
            (["route"], reply, None, 0)):
            reply, transcript = model_reply, heard
            commands.clear()
            with patch.object(sys, "argv", argv), contextlib.redirect_stdout(io.StringIO()):
                scope["main"]()
            assert sum(command.startswith("run ") for command in commands) == runs, commands
        assert len(recordings) == 2
        scope["os"].environ.clear()
        commands.clear()
        with patch.object(sys, "argv", ["route", "wave"]), contextlib.redirect_stdout(io.StringIO()):
            scope["main"]()
        assert commands == ["list", "run wave {}"]
        reply = "```json\n[[[0,0],[1,1]]]\n```"
        draw = {"Stroke": list, "json": json, "os": scope["os"], "fit": lambda strokes: strokes, "DETAIL": "detailed"}
        functions("draw.py", {"from_model", "closed_up"}, draw)
        assert draw["from_model"]("line") == [[(0.0, 0.0), (1.0, 1.0)]]


if __name__ == "__main__":
    test_adapters()
    test_voice_and_drawing()
    print("model adapters ok")
