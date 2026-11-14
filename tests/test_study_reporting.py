"""Fake browser/clock and temporary output only: python -m tests.test_study_reporting."""
import argparse
import ast
import contextlib
import io
import json
import random
import re
import sys
import tempfile
import time
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch


def test_study_reporting():
    folder = Path(__file__).resolve().parents[1] / "keypad" / "geometry_dash"
    clock, screenshots, keys = [0.0], [], []

    def load(filename, names, scope):
        path = folder / filename
        nodes = [n for n in ast.parse(path.read_text()).body
                 if isinstance(n, ast.FunctionDef) and n.name in names]
        assert len(nodes) == len(names)
        exec(compile(ast.Module(body=nodes, type_ignores=[]), str(path), "exec"), scope)

    def evaluate(script, cursor):
        clock[0] += 1000
        return ([{"type": "start", "at": 0}] if cursor == 0 else []), clock[0]

    def fail(*args, **kwargs):
        raise RuntimeError("fake browser failure")

    page = SimpleNamespace(
        evaluate=evaluate,
        keyboard=SimpleNamespace(down=lambda key: keys.append("down"), up=lambda key: keys.append("up")),
        screenshot=lambda **kwargs: screenshots.append(kwargs["path"]),
        add_init_script=lambda *args: None, goto=lambda *args, **kwargs: None,
        wait_for_selector=lambda *args, **kwargs: None, wait_for_timeout=lambda *args: None,
        mouse=SimpleNamespace(click=lambda *args: None))
    browser = SimpleNamespace(new_page=lambda **kwargs: page, close=lambda: None)
    chromium = SimpleNamespace(launch=lambda **kwargs: browser)
    events = [SimpleNamespace(at=.1, down=True), SimpleNamespace(at=.2, down=False)]
    scope = {"perf_counter": lambda: clock[0] / 1000, "sleep": lambda seconds: None}
    load("geo_browser_replay.py", {"replay"}, scope)
    with tempfile.TemporaryDirectory() as temporary:
        output = Path(temporary)
        scope.update(
            argparse=argparse, contextlib=contextlib, io=io, json=json, random=random,
            re=re, time=time, Path=Path, mkdtemp=tempfile.mkdtemp, __doc__="fake study",
            OUTPUTS=output, DEFAULT_PATTERN=output / "fake.csv", AUDIO_OBSERVER="fake",
            GAME_URL="fake://no-network", VIEWPORT={},
            sync_playwright=lambda: contextlib.nullcontext(SimpleNamespace(chromium=chromium)),
            read_pattern=lambda path: events, command_times=lambda *args: events,
            simulate=lambda *args: (events, None, None), O3CSettings=lambda: None,
            disturb=lambda *args: events)
        load("jitter_study.py", {"one_run", "main"}, scope)
        for failure in (False, True):
            if failure:
                chromium.launch = fail
            destination = output / f"{failure}.jsonl"
            with patch.object(sys, "argv", ["study", "--runs", "1", "--offsets", "0",
                                            "--out", str(destination)]), \
                    contextlib.redirect_stdout(io.StringIO()):
                assert scope["main"]() == 0
            row = json.loads(destination.read_text())
            assert "cleared" not in row and row["percent"] is None, row
            assert row["no_crash"] is (not failure), row
            if failure:
                assert row["end_screen"] is None and "fake browser failure" in row["error"], row
            else:
                assert keys == ["down", "up"] and len(screenshots) == 1
                assert row["end_screen"] == str(screenshots[0]) and not row["error"], row
                assert row["events_sent"] == 2, row


if __name__ == "__main__":
    test_study_reporting()
    print("study reporting ok")
