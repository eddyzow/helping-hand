"""Offline v2 profile and filter boundaries; no devices, model or network."""
import json
import tempfile
from pathlib import Path
from unittest.mock import patch

import numpy as np
import steady
from core.tremor import LowPass, Notch
from tests.test_steady import get


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

    def remaining(cutoff, use_notch):
        low, notch = LowPass([0.0]), Notch()
        if use_notch:
            notch.track(3.0, 6.0)
        out = np.array([low.step(notch.step([v], dt), cutoff, dt)[0] for v in signal])
        half = len(times) // 2
        return 2 * abs(np.mean(out[half:] * np.exp(-2j * np.pi * 6 * times[half:]))) / 3

    old, current = remaining(2.0, False), remaining(steady.CUTOFF_HZ, True)
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
