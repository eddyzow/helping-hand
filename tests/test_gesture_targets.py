"""Reuse the owner's mock recorder without importing or running MuJoCo."""
import ast
from pathlib import Path

import numpy as np

from core.arm import HZ, MockArm
from skills import gesture


def test_gesture_targets():
    path = Path(__file__).with_name("test_gestures_sim.py")
    tree = ast.parse(path.read_text())
    nodes = [node for node in tree.body
             if isinstance(node, ast.ClassDef) and node.name == "Recorder"
             or isinstance(node, ast.FunctionDef) and node.name == "replay"]
    scope = dict(MockArm=MockArm, gesture=gesture, np=np)
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(path), "exec"), scope)
    peak, whole_roll = 0.0, 0.0
    for name in gesture.GESTURES:
        frames, leave, back = scope["replay"](name)
        speeds = np.abs(np.diff(frames, axis=0)) * [1, 1, 1, 1, 1, 1.1] * HZ
        peak = max(peak, float(speeds.max()))
        whole_roll = max(whole_roll, float(np.ptp(frames[:, 4])))
        assert speeds.max() <= 120 + 1e-6, (name, speeds.max())
        assert np.allclose(frames[0], frames[-1]), name
        assert np.ptp(frames[leave - 1:back, 4]) <= .01, name
        stopped = scope["Recorder"]()
        stopped.stop()
        assert gesture.run(stopped, {"name": name}, stopped.halt) == gesture.STOPPED
        assert not stopped.frames, name
    print("mock gestures", len(gesture.GESTURES), "peak commanded deg/s", round(peak, 3),
          "whole-replay roll target span", round(whole_roll, 3))


if __name__ == "__main__":
    test_gesture_targets()
    print("gesture targets ok; no MuJoCo or hardware")
