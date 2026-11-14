"""Extracted parser and fake routing only; no simulator import or model call."""
import contextlib
import io
import json
import sys
from types import SimpleNamespace
from unittest.mock import patch

from tests.test_perception_boundaries import functions


def test_requests():
    calls, routed = [], []
    draw = SimpleNamespace(FONTS={"print": "futural", "script": "scripts"},
                           from_text=lambda text: calls.append(("text", text)) or [],
                           from_writing=lambda text, style: calls.append(("write", text, style)) or [],
                           sketch=lambda what: calls.append(("sketch", what)) or [])
    scope = {"draw": draw, "json": json, "importlib": SimpleNamespace(
        import_module=lambda name: SimpleNamespace(NAME=name.split(".")[-1], DESCRIPTION="fake", PARAMS={}))}
    functions("sim_draw.py", {"strokes_for"}, scope)
    reply = {"skill": "write", "params": {"text": "Dr. Lee", "style": "script"}}
    route = SimpleNamespace(by_model=lambda text, skills: routed.append((text, skills)) or reply)
    with patch.dict(sys.modules, {"see": SimpleNamespace(load_env=lambda: None), "voice.route": route}), \
            contextlib.redirect_stdout(io.StringIO()):
        for text, expected in (
            ("--text HI", ("text", "HI")),
            ("--write Dr. Lee", ("write", "Dr. Lee", "print")),
            ("--script Dr. Lee", ("write", "Dr. Lee", "script")),
            ('run write {"text": "Dr. Lee", "style": "script"}', ("write", "Dr. Lee", "script")),
            ('run draw {"what": "a cat"}', ("sketch", "a cat"))):
            scope["strokes_for"](text.split())
            assert calls[-1] == expected and not routed, (text, calls, routed)
        scope["strokes_for"]("write Dr. Lee in cursive".split())
        assert calls[-1] == ("write", "Dr. Lee", "script")
        assert {skill["name"] for skill in routed[-1][1]} == {"draw", "write"}
        reply = {"skill": "draw", "params": {"what": "a cat"}}
        scope["strokes_for"]("draw a cat".split())
        assert calls[-1] == ("sketch", "a cat") and len(routed) == 2


if __name__ == "__main__":
    test_requests()
    print("sim drawing requests ok (fakes only)")
