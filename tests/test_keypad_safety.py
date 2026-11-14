"""Run with python -m tests.test_keypad_safety; fake APIs only, no input hooks."""
import ast
import contextlib
import ctypes
import io
from pathlib import Path
from types import SimpleNamespace


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
        ("Editor", "Geometry Dash", [("key", 0), ("key", 2)]),
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


if __name__ == "__main__":
    test_keypad_safety()
    print("keypad safety ok")
