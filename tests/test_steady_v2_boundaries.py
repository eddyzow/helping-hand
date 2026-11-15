"""Offline v2 profile and filter boundaries; no devices, model or network."""
import json
import tempfile
from pathlib import Path
from unittest.mock import patch

import numpy as np
import steady
from core.tremor import LowPass
from tests.test_steady import get, run_loop


def test_mesh_routes():
    with tempfile.TemporaryDirectory() as folder, patch.object(steady.tremor, "ROOT", Path(folder)):
        root = Path(folder) / steady.tremor.MODEL / "assets"
        root.mkdir(parents=True)
        (root / "part.stl").write_bytes(b"test mesh")
        (root.parent / "outside.stl").write_bytes(b"outside sentinel")
        (root / "secret.txt").write_bytes(b"unsupported sentinel")
        assert get("/meshes/index.json") == (200, "application/json", b'["part.stl"]')
        assert get("/meshes/part.stl?v=1") == (200, "model/stl", b"test mesh")
        for name in ("../outside.stl", "..%2foutside.stl", "secret.txt", "missing.stl"):
            assert get("/meshes/" + name)[0] == 404, name


def test_trigger_order():
    with tempfile.TemporaryDirectory() as folder:
        path = Path(folder) / "users.json"
        good = steady.default_profile()
        path.write_text(json.dumps({"good": good,
            "reversed squeeze": {**good, "trigger": {"rest": 43, "squeezed": 80, "open": 100}},
            "reversed open": {**good, "trigger": {"rest": 43, "squeezed": 0, "open": 20}}}))
        loaded = steady.load_users(path)
        assert set(loaded) == {"default", "good"}, ("invalid trigger ordering accepted", sorted(loaded))


def test_slow_loop_suppression():
    dt = 1 / 25
    times = np.arange(0, 20, dt)
    shake = 3 * np.sin(2 * np.pi * 6 * times)
    signal = 20 * np.sin(2 * np.pi * .5 * times) + shake

    low = LowPass([0.0])
    old_out = np.array([low.step([v], 2.0, dt)[0] for v in signal])
    half = len(times) // 2
    old = 2 * abs(np.mean(old_out[half:] * np.exp(-2j * np.pi * 6 * times[half:]))) / 3
    hand = lambda t: np.array([20 * np.sin(2 * np.pi * .5 * t) + 3 * np.sin(2 * np.pi * 6 * t), 0, 0, 0, 0, 43.0])
    with patch.object(steady, "HZ", 25):
        ticks, _, _ = run_loop(hand, 20.0)
    late = [tick for tick in ticks if 10 <= tick[0] < 20]
    current = 2 * abs(np.mean([tick[1][0] * np.exp(-2j * np.pi * 6 * tick[0]) for tick in late])) / 3
    print(f"25 Hz sampling, 6 Hz shake: old leaves {old:.1%}; v2 leaves {current:.1%}")
    assert old <= .15
    assert current <= .15, ("default v2 loses the 85% suppression bound at 25 Hz", current)


if __name__ == "__main__":
    failures = []
    for check in (test_mesh_routes, test_trigger_order, test_slow_loop_suppression):
        try:
            check()
            print("PASS", check.__name__)
        except AssertionError as error:
            failures.append(check.__name__)
            print("FAIL", check.__name__, error)
    assert not failures, failures
