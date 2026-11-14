"""Replay's actual feedback helper with fake time, key state and arm only."""
import ast
from pathlib import Path
from types import SimpleNamespace


def check_repair(down, initial):
    path = Path(__file__).resolve().parents[1] / "skills" / "geometry_dash.py"
    node = next(node for node in ast.walk(ast.parse(path.read_text()))
                if isinstance(node, ast.FunctionDef) and node.name == "watch")
    now, calls = [0.], []
    arm = SimpleNamespace(press_extra=initial if down else 0., lift=3. if down else initial,
                          press=lambda: calls.append("press") or True,
                          release=lambda: calls.append("release") or True)

    def set_tap(**values):
        for name, value in values.items():
            setattr(arm, "press_extra" if name == "press" else name, value)

    arm.set_tap = set_tap
    scope = {"key_down": SimpleNamespace(is_set=lambda: not down), "last": [not down],
             "seen": [], "start": 0., "real_now": lambda: now[0], "feels_key": True,
             "asked": {"down": down, "at": 0., "tries": 0}, "arm": arm, "repairs": []}
    exec(compile(ast.Module(body=[node], type_ignores=[]), str(path), "exec"), scope)
    scope["watch"]()
    assert calls == []
    for moment in (.16, .32, .48):
        now[0] = moment
        scope["watch"]()
    assert len(calls) <= 2, calls
    final = arm.press_extra if down else arm.lift
    assert final >= initial, ("press" if down else "lift", initial, final)
    limit = 3. if down else 9.
    assert final == initial if initial >= limit else final <= limit, (initial, final, limit)
    return final


if __name__ == "__main__":
    failures = []
    for down, initial in ((True, 0.), (False, 3.), (True, 3.), (False, 9.), (True, 5.), (False, 12.)):
        try:
            print("repair", down, initial, "->", check_repair(down, initial))
        except AssertionError as error:
            failures.append(str(error))
            print("repair FAILED", error)
    assert not failures, failures
    print("replay repair boundaries ok")
