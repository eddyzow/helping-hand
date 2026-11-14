"""Known failing checks, fake bus/socket only: python -m tests.test_pending_boundaries."""
import ast
import threading
from pathlib import Path
from types import SimpleNamespace

from core.arm import Arm, JOINTS, TAP_JOINT


def test_notify_eof():
    path = Path(__file__).resolve().parents[1] / "keypad" / "listen.py"
    node = next(n for n in ast.parse(path.read_text()).body
                if isinstance(n, ast.FunctionDef) and n.name == "notify")
    closed, connections = [], []

    class Socket:
        def __init__(self, eof): self.eof = eof
        def sendall(self, data): pass
        def recv(self, count): return b"" if self.eof else b'{"ok":true}\n'
        def close(self): closed.append(self)
        def setsockopt(self, *args): pass
        def setblocking(self, *args): pass

    def connect(*args, **kwargs):
        connections.append(1)
        assert len(connections) <= 1, "unbounded reconnection"
        return Socket(False)

    stale = Socket(True)
    scope = {"_open": [stale], "PORT": 0, "socket": SimpleNamespace(
        create_connection=connect, IPPROTO_TCP=6, TCP_NODELAY=1)}
    exec(compile(ast.Module(body=[node], type_ignores=[]), str(path), "exec"), scope)
    scope["notify"]("key up")
    assert stale not in scope["_open"] and closed == [stale], "EOF socket retained instead of closed"


def test_measured_tap_step():
    for measured in (0.0, 10.0):
        writes = []
        positions = {name: measured if i == TAP_JOINT else 0.0 for i, name in enumerate(JOINTS)}

        def write(register, values):
            assert register == "Goal_Position", register
            writes.append(dict(values))

        def bounded_send(actions):
            # The existing follower API bounds goals against measured positions.
            goals = {name: positions[name] + max(-15, min(15, actions[name + ".pos"] - positions[name]))
                     for name in positions if name + ".pos" in actions}
            write("Goal_Position", goals)
            return {name + ".pos": value for name, value in goals.items()}

        arm = object.__new__(Arm)
        arm.halt = threading.Event()
        arm._poses = {"tap_key": [0.0] * len(JOINTS)}
        arm.lift, arm.press_extra = 3.0, 0.0
        arm._robot = SimpleNamespace(
            config=SimpleNamespace(max_relative_target=15), send_action=bounded_send,
            get_observation=lambda: {name + ".pos": value for name, value in positions.items()},
            bus=SimpleNamespace(sync_read=lambda *args, **kwargs: dict(positions), sync_write=write))
        try:
            arm.set_tap(lift=40, press=0)
            accepted = arm.release()
        except (ValueError, RuntimeError):
            accepted = False
        assert not accepted or writes, "tap silently accepted without a write"
        assert all(abs(value - positions[name]) <= 15 for values in writes for name, value in values.items()), \
            f"tap exceeded measured-position step cap: measured={measured}, writes={writes}"


if __name__ == "__main__":
    failed = 0
    for check in (test_notify_eof, test_measured_tap_step):
        try:
            check()
            print(check.__name__, "ok")
        except AssertionError as error:
            failed += 1
            print(check.__name__, "FAILED:", error)
    raise SystemExit(bool(failed))
