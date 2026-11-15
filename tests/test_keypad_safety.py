"""Run with python -m tests.test_keypad_safety; fake APIs only, no input hooks."""
import argparse
import ast
import contextlib
import ctypes
import io
import math
import sys
import time
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch


def test_keypad_safety():
    path = Path(__file__).resolve().parents[1] / "keypad" / "listen.py"
    main = next(n for n in ast.parse(path.read_text()).body
                if isinstance(n, ast.FunctionDef) and n.name == "main")
    callback = next(n for n in main.body
                    if isinstance(n, ast.FunctionDef) and n.name == "on_key")
    code = compile(ast.Module(body=[callback], type_ignores=[]), str(path), "exec")
    state, events = {"title": "Geometry Dash"}, []

    def title(window, buffer, size):
        buffer.value = state["title"]

    scope = {
        "keys": {"jump": 67, "wave": 88, "stop": 90},
        "ROLES": ["wave", "jump", "stop"], "jump_as": {}, "recording": {},
        "ctypes": ctypes, "GAME_TITLE": "Geometry Dash", "VK_UP": 38, "KEYUP": 2,
        "time": SimpleNamespace(perf_counter=lambda: 1.0),
        "send": lambda command, *args: events.append(("send", command)),
        "notify": lambda command, *args: events.append(("send", command)),
        "user32": SimpleNamespace(
            GetForegroundWindow=lambda: 1, GetWindowTextW=title,
            mouse_event=lambda flag, *args: events.append(("mouse", flag)),
            keybd_event=lambda vk, scan, flag, extra: events.append(("key", flag))),
        "__file__": str(path),
    }
    exec(code, scope)
    on_key = scope["on_key"]
    for before, after, expected in (
        ("Geometry Dash", "Editor", [("mouse", 2), ("mouse", 4)]),
        ("Editor", "Geometry Dash", []),
    ):
        events.clear()
        state["title"] = before
        on_key(67, True)
        state["title"] = after
        on_key(67, False)
        assert [e for e in events if e[0] != "send"] == expected, events

    saved = []
    state["fail_save"] = True

    class Output:
        def with_name(self, name):
            return self

        def __truediv__(self, name):
            return self

        def write_text(self, text):
            events.append(("write", None))
            if state["fail_save"]:
                raise OSError("fake disk full")
            saved.append(text)

    scope["Path"] = lambda *args: Output()
    original = [(0.1, True), (0.2, False), (0.3, True)]
    scope["recording"].update(name="demo", events=list(original))
    events.clear()
    output = io.StringIO()
    with contextlib.redirect_stdout(output):
        on_key(90, True)
        assert events == [("send", "stop"), ("write", None)], events
        assert scope["recording"]["events"] == original
        assert "fake disk full" in output.getvalue()
        state["fail_save"] = False
        on_key(90, True)
    assert events == [("send", "stop"), ("write", None)] * 2, events
    assert saved == ["time_ms,state\n100.000,down\n200.000,up\n"]
    assert scope["recording"] == {}
    tree = ast.parse(path.read_text())
    settings = [node for node in tree.body if isinstance(node, ast.Assign)
                and isinstance(node.targets[0], ast.Name)
                and node.targets[0].id in ("SHOW", "SHOW_WAVE", "SHOW_JUMP", "SHOW_THIRD")]
    scope.update(os=SimpleNamespace(environ={}), sys=SimpleNamespace(argv=[str(path), "--show"]))
    exec(compile(ast.Module(body=settings, type_ignores=[]), str(path), "exec"), scope)
    assert scope["SHOW"] is True
    events.clear()
    on_key(67, True)
    on_key(67, False)
    on_key(88, True)
    on_key(90, True)
    assert events == [("send", 'run gesture {"name": "high_five"}'),
                      ("send", 'run gesture {"name": "dance"}'),
                      ("send", 'run gesture {"name": "victory"}')], events
    scope["os"].environ.update(KEYPAD_MODE="show", KEYPAD_JUMP="next")
    scope["sys"].argv = [str(path)]
    exec(compile(ast.Module(body=settings, type_ignores=[]), str(path), "exec"), scope)
    assert scope["SHOW"] is True
    events.clear()
    on_key(67, True)
    assert events == [("send", "run gesture")]
    scope["SHOW"] = False
    events.clear()
    on_key(90, True)
    assert events == [("send", "stop")], events


def test_connection_cooldown():
    path = Path(__file__).resolve().parents[1] / "keypad" / "listen.py"
    nodes = [n for n in ast.parse(path.read_text()).body
             if isinstance(n, ast.FunctionDef) and n.name in ("send", "notify")]
    attempts, now = [], [10.0]

    def unavailable(*args, **kwargs):
        attempts.append(kwargs["timeout"])
        raise ConnectionRefusedError("fake unavailable dispatcher")

    scope = dict(PORT=0, _open=[], socket=SimpleNamespace(create_connection=unavailable))
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(path), "exec"), scope)
    with patch.object(time, "perf_counter", lambda: now[0]):
        scope["send"]("ready", .2)
        scope["send"]("ready", .2)
        assert attempts == [.05]
        scope["send"]("stop")
        assert attempts == [.05, 1], "Stop must bypass the connection cooldown"
        now[0] += 1.51
        scope["send"]("ready", .2)
        assert attempts == [.05, 1, .05]
        attempts.clear()
        scope["notify"]("key down")
        scope["notify"]("key up")
        assert attempts == [.05]
        now[0] += 1.51
        scope["notify"]("key down")
        assert attempts == [.05, .05]


def test_notify_retry():
    path = Path(__file__).resolve().parents[1] / "keypad" / "listen.py"
    node = next(n for n in ast.parse(path.read_text()).body
                if isinstance(n, ast.FunctionDef) and n.name == "notify")
    code = compile(ast.Module(body=[node], type_ignores=[]), str(path), "exec")
    # Since 14 Nov notify looks at the kept connection BEFORE sending. A connection found closed has
    # had nothing sent on it, so the command goes out exactly once on a fresh connection, cue or not.
    # (Before, the send went into the closed connection first and was lost without an error: the
    # first key event after every dispatcher restart vanished, and a calibration ran to its limit.)
    for command, retry, expected in (("cue", False, 1), ("key down", True, 1)):
        accepted, closed, connections = [], [], []

        class Socket:
            def __init__(self, fail): self.fail = fail
            def sendall(self, data): accepted.append(data.decode().strip())
            def recv(self, count):
                if self.fail: raise ConnectionResetError("accepted, then disconnected")
                return b'{"ok":true}\n'
            def close(self): closed.append(self)
            def setsockopt(self, *args): pass
            def setblocking(self, *args): pass

        def connect(*args, **kwargs):
            sock = Socket(False)
            connections.append(sock)
            return sock

        stale = Socket(True)
        scope = {"_open": [stale], "PORT": 0, "socket": SimpleNamespace(
            create_connection=connect, IPPROTO_TCP=6, TCP_NODELAY=1)}
        exec(code, scope)
        scope["notify"](command, retry=retry)
        assert accepted == [command] * expected and closed == [stale]
        assert len(connections) == 1 and scope["_open"] == connections  # one fresh connection, kept
        scope["notify"](command, retry=retry)                           # the next one reuses it
        assert accepted == [command] * 2 and len(connections) == 1


def test_software_replay():
    path = Path(__file__).resolve().parents[1] / "keypad" / "geometry_dash" / "soft_replay.py"
    node = next(n for n in ast.parse(path.read_text()).body
                if isinstance(n, ast.FunctionDef) and n.name == "main")
    code = compile(ast.Module(body=[node], type_ignores=[]), str(path), "exec")
    for offset, lose_focus, expected in (
        (0, 1.0, []), (-1000, math.inf, []), (math.nan, math.inf, []),
        (math.inf, math.inf, []),
        (0, 1.57, [("key", 0, 1), ("key", 2, 1), ("mouse", 2, 1), ("mouse", 4, 2)]),
        (0, math.inf, [("key", 0, 1), ("key", 2, 1), ("mouse", 2, 1), ("mouse", 4, 1)]),
    ):
        now, calls = [0.0], []

        def foreground(): return 1 if now[0] < lose_focus else 2
        def sleep(seconds): now[0] += max(seconds, 0.000001)

        scope = {
            "argparse": argparse, "math": math, "Path": Path,
            "__doc__": "fake input test", "__file__": str(path),
            "read_pattern": lambda path: [SimpleNamespace(at=.05, down=True),
                                           SimpleNamespace(at=.10, down=False)],
            "time": SimpleNamespace(perf_counter=lambda: now[0], sleep=sleep),
            "KEY_UP": 2, "LEFT_DOWN": 2, "LEFT_UP": 4,
            "user32": SimpleNamespace(
                FindWindowW=lambda *args: 1, GetForegroundWindow=foreground,
                keybd_event=lambda key, scan, flag, extra: calls.append(("key", flag, foreground())),
                mouse_event=lambda flag, *args: calls.append(("mouse", flag, foreground()))),
        }
        exec(code, scope)
        with patch.object(sys, "argv", [str(path), "fake.csv", "--offset-ms", str(offset)]), \
                contextlib.redirect_stdout(io.StringIO()):
            result = scope["main"]()
        assert calls == expected, (offset, lose_focus, calls)
        assert result == (0 if offset == 0 and lose_focus == math.inf else 1)


if __name__ == "__main__":
    test_keypad_safety()
    test_notify_retry()
    test_connection_cooldown()
    test_software_replay()
    print("keypad safety ok")
