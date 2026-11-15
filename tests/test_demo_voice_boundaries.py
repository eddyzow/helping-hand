"""python -B -m tests.test_demo_voice_boundaries; extracted code and fake I/O only."""
import argparse
import ast
import contextlib
import io
import json
import os
import re
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


def router():
    normalise = next(n for n in ast.parse((ROOT / "robtop_voice.py").read_text(encoding="utf-8")).body
                     if isinstance(n, ast.FunctionDef) and n.name == "normalise")
    scope = {"re": re}
    exec(compile(ast.Module(body=[normalise], type_ignores=[]), "robtop_voice.py", "exec"), scope)
    path = ROOT / "demo" / "voice_draw.py"
    nodes = [n for n in ast.parse(path.read_text()).body
             if isinstance(n, ast.FunctionDef) and n.name in ("choose", "main")
             or isinstance(n, ast.Assign) and isinstance(n.targets[0], ast.Name)
             and n.targets[0].id in ("DRAW", "GAME")]
    scope.update(ROOT=ROOT, sys=sys, os=os, argparse=argparse,
                 voice=SimpleNamespace(normalise=scope["normalise"]))
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(path), "exec"), scope)
    return scope


def test_positive_routes():
    choose = router()["choose"]
    for name in ("flower", "house", "heart"):
        _, (command, env) = choose("draw a " + name)
        assert Path(command[1]).name == "loop.py" and Path(command[2]).name == name + ".json"
        assert env["STATE"] == "state_" + name + ".json" and env["FAST"] == "1"
    _, (command, env) = choose("play tic tac toe")
    assert Path(command[1]).name == "ttt2.py" and env == {"ANY": "1"}


def reject(phrases):
    choose = router()["choose"]
    bad = [(text, choose(text)[1][0][1:]) for text in phrases if choose(text)[1] is not None]
    assert not bad, ("non-command request selects a drawing/game command", bad)


def test_negative_routes():
    reject(("don't draw a flower", "don’t draw a house", "do not play a game", "never draw a heart"))


def test_stop_routes():
    reject(("stop drawing the flower", "halt the game"))


def test_word_boundaries():
    reject(("practice", "heartwarming", "the household"))


def test_ambiguous_routes():
    reject(("draw a flower or a house", "draw a heart and play tic tac toe"))


def test_typed_dry_run():
    scope, calls = router(), []
    scope["voice"].hear = lambda: calls.append("hear")
    scope["voice"].speak = lambda text: calls.append("speak")
    scope.update(see=SimpleNamespace(load_env=lambda: None),
                 subprocess=SimpleNamespace(call=lambda *a, **k: calls.append("process")))
    with patch.object(sys, "argv", ["voice_draw.py", "--text", "draw a flower", "--dry"]), \
            contextlib.redirect_stdout(io.StringIO()):
        assert scope["main"]() == 0
    assert calls == [], calls


def test_arm_do_failure_status():
    source = (ROOT / "demo" / "cmds.sh").read_text()
    code = source.split("arm_do()", 1)[1].split('$PY -c "', 1)[1].split('" "$1"', 1)[0]
    bad = []
    for accepted in (False, True):
        replies = iter([{"ok": accepted, "job": 7},
                        {"ok": True, "busy": False, "last": {"job": 7, "ok": False}},
                        {"ok": True, "busy": False, "last": {"job": 7, "ok": False}}])
        commands = []

        def connect(*args, **kwargs):
            response = json.dumps(next(replies)) + "\n"
            return SimpleNamespace(sendall=commands.append, close=lambda: None,
                                   makefile=lambda: io.StringIO(response))

        status = 0
        with patch.dict(sys.modules, {"socket": SimpleNamespace(create_connection=connect)}), \
                patch.object(sys, "argv", ["-c", "run tap_calibrate"]), \
                contextlib.redirect_stdout(io.StringIO()):
            try:
                exec(compile(code, "demo/cmds.sh:arm_do", "exec"), {})
            except SystemExit as error:
                status = error.code
        if not status:
            bad.append((accepted, commands))
    assert not bad, ("failed/rejected calibration exits successfully, so gd_cal continues", bad)


def test_stop_all_scope():
    line = next(line for line in (ROOT / "demo" / "cmds.sh").read_text().splitlines()
                if line.startswith("stop_all()"))
    pattern = re.search(r"-match '([^']+)'", line)[1]
    cases = ((r"python.exe C:\other-project\steady.py", False),
             (r"python.exe C:\Users\Khang\helping-hand\keypad\listen.py", True),
             ("python.exe keypad/geometry_dash/arm_play.py my_macro_full.csv", True),
             ("python.exe -m core.dispatcher", True))
    bad = [(command, expected) for command, expected in cases
           if bool(re.search(pattern, command, re.IGNORECASE)) != expected]
    assert not bad, ("stop_all selector crosses project scope or misses an arm process", bad)


if __name__ == "__main__":
    failures = []
    for test in (test_positive_routes, test_negative_routes, test_stop_routes, test_word_boundaries,
                 test_ambiguous_routes, test_typed_dry_run, test_arm_do_failure_status, test_stop_all_scope):
        try:
            test()
            print("PASS", test.__name__)
        except AssertionError as error:
            failures.append(test.__name__)
            print("FAIL", test.__name__, error)
    assert not failures, failures
