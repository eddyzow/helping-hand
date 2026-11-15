"""Extracted source and fake devices only; never import a demo's startup code."""
import ast
import math
import queue
import runpy
import sys
import time
from types import SimpleNamespace
from unittest.mock import patch

import numpy as np

from tests.test_drawloop_boundaries import ROOT, test_saved_depth_bounds, test_teach_stop_before_auto_save


def test_demo_saved_depth():
    test_saved_depth_bounds("demo")


def test_demo_teach_stop():
    test_teach_stop_before_auto_save("demo")


def test_game_search():
    for name in ("ttt.py", "ttt2.py"):
        path = ROOT / "demo" / name
        tree = ast.parse(path.read_text())
        nodes = [node for node in tree.body
                 if isinstance(node, ast.FunctionDef) and node.name == "best_move"
                 or isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name)
                 and node.targets[0].id in ("WINS", "winner")]
        scope = {}
        exec(compile(ast.Module(body=nodes, type_ignores=[]), str(path), "exec"), scope)
        seen, terminal = set(), set()

        def visit(board):
            state = tuple(board)
            if state in seen:
                return
            seen.add(state)
            won = scope["winner"](board)
            assert won != "X", (name, board)
            if won or all(board):
                terminal.add(state)
            elif board.count("X") == board.count("O"):
                for cell in range(9):
                    if board[cell] is None:
                        visit(board[:cell] + ["X"] + board[cell + 1:])
            else:
                cell = scope["best_move"](board)
                assert board[cell] is None, (name, board, cell)
                visit(board[:cell] + ["O"] + board[cell + 1:])

        visit([None] * 9)
        print(name, "legal board states", len(seen), "terminal states", len(terminal), "X wins 0")


def test_camera_wait_stop():
    failures = []
    for name in ("ttt.py", "ttt2.py"):
        path = ROOT / "demo" / name
        tree = ast.parse(path.read_text())
        loops = [node for node in ast.walk(tree) if isinstance(node, ast.While)
                 and any(isinstance(call, ast.Call) and isinstance(call.func, ast.Name)
                         and call.func.id in ("ready", "look") for call in ast.walk(node.test))]
        assert len(loops) == 4, (name, len(loops))
        for loop in loops:
            waits = []

            def bounded_sleep(seconds):
                waits.append(seconds)
                if len(waits) == 3:
                    raise TimeoutError("fake bounded wait")

            scope = dict(halt=SimpleNamespace(is_set=lambda: True),
                         ready=lambda: "no sheet", look=lambda: None, began=0,
                         time=SimpleNamespace(time=lambda: 0, sleep=bounded_sleep),
                         show=lambda *args: None, sys=sys)
            cancelled = False
            try:
                exec(compile(ast.Module(body=[loop], type_ignores=[]), str(path), "exec"), scope)
            except KeyboardInterrupt:
                cancelled = True
            except TimeoutError:
                pass
            if not cancelled:
                failures.append((name, loop.lineno, len(waits)))
    assert not failures, ("camera wait ignores an already-set Stop", failures)


def test_typed_moves():
    path = ROOT / "demo" / "ttt2.py"
    tree = ast.parse(path.read_text())
    loop = next(node for node in ast.walk(tree) if isinstance(node, ast.While)
                and isinstance(node.test, ast.Compare) and isinstance(node.test.left, ast.Name)
                and node.test.left.id == "steady")
    for text, expected in (("1 1", 4), ("2,0", 6), ("", None), ("a b", None),
                           ("-1 0", None), ("3 0", None), ("0 0", None)):
        typed = queue.Queue()
        typed.put(text)

        def stop_wait(_):
            raise TimeoutError("end fake camera iteration")

        scope = dict(typed=typed, queue=queue, board=["X"] + [None] * 8, view=list(range(9)),
                     steady=0, choice=None, halt=SimpleNamespace(is_set=lambda: False),
                     print=lambda *args, **kwargs: None, root=SimpleNamespace(update=lambda: None),
                     time=SimpleNamespace(sleep=stop_wait))
        try:
            exec(compile(ast.Module(body=[loop], type_ignores=[]), str(path), "exec"), scope)
        except TimeoutError:
            pass
        assert scope["choice"] == expected, (text, scope["choice"])


def test_first_line_orientation():
    path = ROOT / "demo" / "ttt2.py"
    tree = ast.parse(path.read_text())
    body = next(node.body for node in tree.body if isinstance(node, ast.Try) and node.finalbody)
    first = next(i for i, node in enumerate(body) if isinstance(node, ast.Assign)
                 and isinstance(node.targets[0], ast.Name) and node.targets[0].id == "side")
    for angle in (0, math.pi / 2, math.pi, -math.pi / 2):
        turn = np.array([[math.cos(angle), -math.sin(angle)], [math.sin(angle), math.cos(angle)]])
        prior = np.diag([1.0, -1.0])
        expected = turn @ prior
        line = np.array([[-11, y] for y in np.linspace(-5, 33, 40)]) @ expected.T
        scope = dict(np=np, math=math, resume=False, first_line=line,
                     ink=np.array([[-10.0, 0.0], [10.0, 0.0]]), R=prior,
                     print=lambda *args, **kwargs: None)
        exec(compile(ast.Module(body=body[first:first + 3], type_ignores=[]), str(path), "exec"), scope)
        assert np.allclose(scope["R"], expected), (angle, scope["R"])


def test_tracked_sheet_shift():
    path = ROOT / "demo" / "ttt2.py"
    tree = ast.parse(path.read_text())
    follow = next(node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef) and node.name == "follow")
    ref = np.array([(x, y) for x in (-11, 11) for y in np.linspace(-33, 33, 101)]
                   + [(x, y) for y in (-11, 11) for x in np.linspace(-33, 33, 101)])
    scope = dict(np=np, s=1.0, R=np.eye(2), ref=ref, t_grid=np.zeros(2),
                 t_now=[np.array([20.0, 0.0])], cells=[],
                 centre=lambda cell: ((cell % 3 - 1) * 22, (1 - cell // 3) * 22),
                 vision=SimpleNamespace(points=lambda _: ref + [20, 0]))
    exec(compile(ast.Module(body=[follow], type_ignores=[]), str(path), "exec"), scope)
    assert scope["follow"](None), "synthetic translated grid should be tracked"
    game = next(node for node in ast.walk(tree) if isinstance(node, ast.While)
                and any(isinstance(stmt, ast.Assign) and isinstance(stmt.targets[0], ast.Name)
                        and stmt.targets[0].id == "shift" for stmt in node.body))
    first = next(i for i, stmt in enumerate(game.body) if isinstance(stmt, ast.Assign)
                 and isinstance(stmt.targets[0], ast.Name) and stmt.targets[0].id == "shift")
    commands = []
    scope.update(mine=4, circle=lambda _: [(0.0, 0.0), (1.0, 0.0)], stroke=lambda pts: commands.append(pts))
    try:
        exec(compile(ast.Module(body=game.body[first:first + 3], type_ignores=[]), str(path), "exec"), scope)
    except (ValueError, AssertionError, KeyboardInterrupt, SystemExit):
        return
    assert not commands or np.allclose(commands[0], [[20, 0], [21, 0]]), (
        "accepted 20 mm grid shift silently reset to old drawing location", commands)


def test_grip_validation_and_cleanup():
    failures = []
    for folder in ("drawloop", "demo"):
        path = ROOT / folder / "grip.py"
        for argument in ("0", "--help", "50"):
            calls = []

            def read(*args, **kwargs):
                raise ConnectionError("fake diagnostic read failure")

            bus = SimpleNamespace(connect=lambda: calls.append("connect"),
                                  write=lambda *args, **kwargs: calls.append("write"), read=read,
                                  disconnect=lambda **kwargs: calls.append(("disconnect", kwargs)))
            modules = {"lerobot": SimpleNamespace(),
                       "lerobot.motors": SimpleNamespace(Motor=lambda *args: None,
                           MotorNormMode=SimpleNamespace(RANGE_0_100=0)),
                       "lerobot.motors.feetech": SimpleNamespace(FeetechMotorsBus=lambda **kwargs: bus)}
            with patch.dict(sys.modules, modules), patch.object(sys, "argv", [str(path), argument]), \
                    patch.object(time, "sleep", lambda _: None):
                try:
                    runpy.run_path(str(path), run_name="__main__")
                except (ValueError, SystemExit, ConnectionError):
                    pass
            if argument != "50" and "connect" in calls or argument == "50" and not any(
                    isinstance(call, tuple) and call == ("disconnect", {"disable_torque": False}) for call in calls):
                failures.append((folder, argument, calls))
    assert not failures, ("invalid arguments connect or diagnostic failure skips disconnect", failures)


if __name__ == "__main__":
    failures = []
    for test in (test_game_search, test_typed_moves, test_first_line_orientation,
                 test_demo_saved_depth, test_demo_teach_stop,
                 test_camera_wait_stop, test_tracked_sheet_shift, test_grip_validation_and_cleanup):
        try:
            test()
            print("PASS", test.__name__)
        except AssertionError as error:
            failures.append(test.__name__)
            print("FAIL", test.__name__, error)
    assert not failures, failures
