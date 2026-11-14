"""Fake connection/bus only: python -m tests.test_arm_boundaries."""
import os
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import core.arm
import core.dispatcher


def test_arm_boundaries():
    def forbidden_connection():
        raise AssertionError("invalid gain reached follower connection")

    with tempfile.TemporaryDirectory() as folder:
        (Path(folder) / "home.json").write_text("{}")
        with patch.multiple(core.arm, POSES=Path(folder), LIFT=3.0, PRESS=0.0), \
                patch.dict(sys.modules, {"arm": SimpleNamespace(follower=forbidden_connection)}):
            for gain in ("bad", "7", "49", "32.5", "inf", ""):
                with patch.dict(os.environ, {"TAP_P_GAIN": gain}):
                    try:
                        core.arm.Arm()
                    except ValueError:
                        pass
                    else:
                        raise AssertionError(f"accepted invalid gain {gain!r}")

    reads = []
    arm = SimpleNamespace(temperatures=lambda: (reads.append(1) or {"wrist_flex": 30.0}))
    with patch.multiple(core.dispatcher, _arm=arm, _worker=None, _closing=True):
        assert core.dispatcher.handle("temps") == {"ok": False, "reason": "shutting down"}
        assert not reads
        core.dispatcher._closing = False
        core.dispatcher._worker = SimpleNamespace(is_alive=lambda: True)
        assert core.dispatcher.handle("temps") == {"ok": False, "reason": "busy"}
        assert not reads
        core.dispatcher._worker = None
        assert core.dispatcher.handle("temps") == {"ok": True, "temps": {"wrist_flex": 30.0}}
        assert reads == [1]


if __name__ == "__main__":
    test_arm_boundaries()
    print("arm boundaries ok")
