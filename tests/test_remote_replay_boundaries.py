"""Fake clock/screen/socket only: python -B -m tests.test_remote_replay_boundaries."""
import ast
import collections
import queue
import threading
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import core
from skills import gd_remote


def test_remote_skill():
    for idle in (False, 0, 301, float("nan"), float("inf")):
        arm = SimpleNamespace(to_key=lambda: (_ for _ in ()).throw(AssertionError("invalid input moved")))
        assert not gd_remote.run(arm, {"idle_s": idle}, threading.Event())["ok"]
    for stopped in (False, True):
        remote, ready, stop, calls = queue.Queue(), threading.Event(), threading.Event(), []
        remote.put("press")  # stale input must be discarded before approaching

        def approach():
            calls.append("approach")
            for word in ("press", "release", "end"):
                remote.put(word)
            return True

        def press():
            calls.append("press")
            if stopped:
                stop.set()
            return not stopped

        arm = SimpleNamespace(to_key=approach, press=press,
                              release=lambda: calls.append("release") or True,
                              from_key=lambda: calls.append("home") or True)
        with patch.object(core, "remote", remote), patch.object(core, "remote_ready", ready):
            result = gd_remote.run(arm, {}, stop)
        expected = ["approach", "press"] if stopped else ["approach", "press", "release", "release", "home"]
        assert calls == expected and result["ok"] is not stopped and not ready.is_set(), (calls, result)


def attempt(*, focus_loss=float("inf"), caption_at=float("inf")):
    path = Path(__file__).resolve().parents[1] / "keypad/geometry_dash/arm_play.py"
    nodes = [n for n in ast.parse(path.read_text()).body
             if isinstance(n, ast.FunctionDef) and n.name in ("attempt", "match")]
    assert len(nodes) == 2
    clock, sent = [0.0], []

    def now():
        clock[0] += .001
        assert clock[0] < 10, "replay did not terminate"
        return clock[0]

    def elapsed():
        return clock[0] - .301

    scope = {"collections": collections,
             "time": SimpleNamespace(perf_counter=now, sleep=lambda _: None),
             "threading": SimpleNamespace(Thread=lambda **_: SimpleNamespace(start=lambda: None)),
             "user32": SimpleNamespace(GetForegroundWindow=lambda: 0 if elapsed() >= focus_loss else 1,
                                       keybd_event=lambda *args: None)}
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(path), "exec"), scope)
    screen = SimpleNamespace(white=lambda: 4000 if elapsed() >= caption_at else 0,
                             frame=lambda: b"fake")
    socket = SimpleNamespace(sendall=lambda data: sent.append((round(elapsed(), 3), data)),
                             recv=lambda _: b'{"ok":true}\n')
    event = collections.namedtuple("Event", "at down")
    events = [event(1.0, True), event(1.1, False)]
    result = scope["attempt"](1, screen, socket, events, {True: 0, False: 0}, 0, 3000, [0, 0])
    return result, sent


def test_normal_attempt():
    result, sent = attempt()
    assert result["ended"] == "finished", result
    assert [data for _, data in sent] == [b"tap press\n", b"tap release\n", b"tap release\n"], sent


def test_focus_before_tap():
    result, sent = attempt(focus_loss=.98)
    assert not any(data == b"tap press\n" and at >= .98 for at, data in sent), \
        f"press sent after focus loss: {sent}; outcome={result['ended']}"


def test_late_caption_is_not_completion():
    result, _ = attempt(caption_at=2.2)
    assert result["ended"] != "completed", \
        f"a late restart caption alone became completion: {result['ended']} at {result['survived_s']}s"


if __name__ == "__main__":
    failed = 0
    for check in (test_remote_skill, test_normal_attempt, test_focus_before_tap, test_late_caption_is_not_completion):
        try:
            check()
            print(check.__name__, "ok")
        except AssertionError as error:
            failed += 1
            print(check.__name__, "FAILED:", error)
    raise SystemExit(bool(failed))
