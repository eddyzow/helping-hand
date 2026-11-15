"""Actual source blocks with fakes only: no devices, cameras, GUI, sockets or input."""
import ast
import ctypes
import json
import math
import os
import queue
import runpy
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


def test_core_read_retries():
    from core import arm
    calls = []

    def read(*args, **kwargs):
        calls.append((args, kwargs))
        if args[0] == "unavailable":
            raise ConnectionError("fake exhausted retries")
        return {"wrist_roll": 0}

    disabled = []
    robot = SimpleNamespace(bus=SimpleNamespace(sync_read=read,
        disable_torque=lambda *args, **kwargs: disabled.append((args, kwargs))))
    with tempfile.TemporaryDirectory() as temporary, patch.dict(os.environ):
        os.environ.pop("TAP_P_GAIN", None)
        os.environ.pop("ROLL_POWER", None)
        poses = Path(temporary)
        (poses / "home.json").write_text("{}")
        with patch.object(arm, "POSES", poses), \
                patch.dict(sys.modules, arm=SimpleNamespace(follower=lambda: robot)):
            actual = arm.Arm()
            assert disabled == [(("wrist_roll",), {"num_retry": 8})]
            assert actual._robot.bus.sync_read("Present_Position", ["wrist_roll"],
                                               normalize=False, num_retry=1) == {"wrist_roll": 0}
            assert calls[-1] == (("Present_Position", ["wrist_roll"]),
                                  {"normalize": False, "num_retry": 12})
            try:
                actual._robot.bus.sync_read("unavailable")
            except ConnectionError:
                pass
            else:
                raise AssertionError("exhausted read failure was swallowed")
            os.environ["ROLL_POWER"] = "1"
            arm.Arm()
            assert len(disabled) == 1, "explicit roll-power opt-in still disabled the fake motor"


def test_core_constructor_cleanup():
    from core import arm
    closed = []

    def unavailable(*args, **kwargs):
        raise ConnectionError("fake wrist-roll disable failure after connect")

    robot = SimpleNamespace(bus=SimpleNamespace(sync_read=lambda *args, **kwargs: {},
                                                disable_torque=unavailable),
                            disconnect=lambda *args, **kwargs: closed.append(True))
    with tempfile.TemporaryDirectory() as temporary, patch.dict(os.environ):
        os.environ.pop("TAP_P_GAIN", None)
        os.environ.pop("ROLL_POWER", None)
        poses = Path(temporary)
        (poses / "home.json").write_text("{}")
        with patch.object(arm, "POSES", poses), \
                patch.dict(sys.modules, arm=SimpleNamespace(follower=lambda: robot)):
            try:
                arm.Arm()
            except ConnectionError:
                pass
            else:
                raise AssertionError("fake disable failure should propagate")
    assert closed, "constructor leaves the connected follower unclosed when wrist-roll disable fails"


def test_cleanup_after_device_error():
    failures = []
    paths = ["drawloop/" + name for name in ("loop.py", "measure.py", "playtest.py", "playtest2.py")]
    paths += ["demo/" + name for name in ("loop.py", "measure.py", "playtest2.py", "ttt.py", "ttt2.py")]
    for name in paths:
        path = ROOT / name
        tree = ast.parse(path.read_text(encoding="utf-8"))
        blocks = [node.finalbody for node in tree.body if isinstance(node, ast.Try) and node.finalbody]
        assert len(blocks) == 1, name
        calls = []

        def unavailable(*args, **kwargs):
            raise ConnectionError("fake unavailable bus during cleanup")

        scope = dict(bus=SimpleNamespace(sync_read=unavailable, write=unavailable),
                     robot=SimpleNamespace(disconnect=lambda: calls.append("disconnect")),
                     cam=SimpleNamespace(release=lambda: calls.append("camera release")),
                     gain=32, set_gain=lambda value: calls.append(("gain", value)),
                     print=lambda *args, **kwargs: None)
        try:
            exec(compile(ast.Module(body=blocks[0], type_ignores=[]), str(path), "exec"), scope)
        except ConnectionError:
            pass
        if "disconnect" not in calls or "camera release" not in calls:
            failures.append((name, calls))
    assert not failures, ("device error bypassed resource cleanup", failures)


def test_saved_depth_bounds(folder="drawloop"):
    from grid import interpolate
    path = ROOT / folder / "loop.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    selected = []
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name in ("polar", "pose"):
            selected.append(node)
        elif isinstance(node, ast.Assign):
            target = node.targets[0]
            first = target if isinstance(target, ast.Name) else target.elts[0] if isinstance(target, ast.Tuple) else None
            if isinstance(first, ast.Name) and first.id in ("PAN", "RF", "RN", "R0", "CX", "PRESS"):
                selected.append(node)
    scope = dict(math=math, interpolate=interpolate,
                 grid=json.loads((ROOT / ("poses" if folder == "drawloop" else folder) / "paper_2x2.json").read_text()),
                 PLANE=json.loads((ROOT / folder / "height.json").read_text()))
    exec(compile(ast.Module(body=selected, type_ignores=[]), str(path), "exec"), scope)
    normal = scope["pose"](0, 0)
    assert all(math.isfinite(value) and abs(value) < 400 for value in normal.values())
    try:
        excessive = scope["pose"](0, 0, lower=100.0)
    except (ValueError, AssertionError):
        return
    assert all(abs(value) < 400 for value in excessive.values()), ("unbounded saved depth produced extreme joints", excessive)


def test_teach_stop_before_auto_save(folder="drawloop"):
    path = ROOT / folder / "teach_paper.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    loops = [node for node in ast.walk(tree) if isinstance(node, ast.While)
             and any(isinstance(call, ast.Attribute) and call.attr == "get_nowait"
                     for call in ast.walk(node))]
    assert len(loops) == 1
    keys = queue.Queue()
    keys.put("stop")
    joints = ["shoulder_pan", "shoulder_lift", "elbow_flex", "wrist_flex", "wrist_roll"]
    pose = {joint + ".pos": 0.0 for joint in joints}

    def unexpected_wait(_):
        raise AssertionError("bounded fake should cancel without another wait")

    scope = dict(time=SimpleNamespace(time=lambda: 4.0, sleep=unexpected_wait),
                 arm=SimpleNamespace(read_pose=lambda _: pose), robot=None, ARM_JOINTS=joints,
                 began=0.0, moved=True, prev=[0.0] * 4, ref=[0.0] * 4, t0=0.0,
                 last=0.0, keys=keys, queue=queue, root=SimpleNamespace(update=lambda: None))
    cancelled = False
    try:
        exec(compile(ast.Module(body=loops, type_ignores=[]), str(path), "exec"), scope)
    except KeyboardInterrupt:
        cancelled = True
    assert cancelled, ("auto-save bypassed queued Stop", keys.qsize())


def test_play_clean_help_and_missing_args():
    path = ROOT / "keypad" / "geometry_dash" / "play_clean.py"
    failures = []
    for arguments in (["--help"], []):
        keys, children = [], []
        user32 = SimpleNamespace(FindWindowW=lambda *args: 1, GetForegroundWindow=lambda: 1,
                                 keybd_event=lambda *args: keys.append(args))
        with patch.object(ctypes, "WinDLL", lambda _: user32, create=True), \
                patch.object(time, "sleep", lambda _: None), \
                patch.object(subprocess, "call", lambda args: children.append(args) or 0), \
                patch.object(sys, "argv", [str(path), *arguments]):
            try:
                runpy.run_path(str(path), run_name="__main__")
            except SystemExit:
                pass
        if keys:
            failures.append((arguments, keys))
    assert not failures, ("help or missing args injected restart keys before validation", failures)


if __name__ == "__main__":
    failures = []
    for test in (test_core_read_retries, test_core_constructor_cleanup,
                 test_cleanup_after_device_error, test_saved_depth_bounds,
                 test_teach_stop_before_auto_save,
                 test_play_clean_help_and_missing_args):
        try:
            test()
            print("PASS", test.__name__)
        except AssertionError as error:
            failures.append(test.__name__)
            print("FAIL", test.__name__, error)
    assert not failures, failures
