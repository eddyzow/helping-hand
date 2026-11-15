"""Every gesture replayed through the SO-101 MuJoCo model, with the limits the real arm needs (14-15 Nov).

    python -m tests.test_gestures_sim         # SO101_ROOT=<a checkout that has the model> if this one does not

The arm here is core.arm.MockArm with its 30 Hz waits removed, so the frames checked are the
exact joint targets skills.gesture sends, interpolated exactly as move_joints does (home -> wave_up -> each
step -> wave_up -> home, from the taught poses in poses/).

Checks, per gesture:
- every joint inside LIMITS (fact 2), widened only to take in the two taught poses: home's elbow is 127 (the
  folded rest reads past +118, steady.py) and wave_up's is -64.35 (the stop was swept to -64.9);
- wrist_roll within 0.01 degree of wave_up's from leaving wave_up to returning (the roll motor is faulty);
- no joint asked to pass 120 deg/s between frames; the gripper counts too, at 1.1 jaw degrees per unit;
- the fingertip site and every vertex of the moving parts' visual meshes (upper arm to jaw) stay 20 mm above
  the table (TABLE_Z = -2.4 mm, steady.py); the base and shoulder only turn about the vertical, so are skipped;
- starts and ends at home, and no more than 6 s from leaving wave_up to returning to it.

Joint conventions (assumptions, from core/tremor.py's Fingertip, the one mapping the repo uses for real angles):
- real degrees go to the model's radians with the same sign on every joint; nothing here checks that sign on
  the real arm. In the model at wave_up, +shoulder_lift, +elbow_flex and +wrist_flex each move the tip forward
  and down, and +shoulder_pan moves it toward -y. skills/gesture.py's own note (a bigger wrist angle bends the
  hand down) agrees for the wrist; the lift and pan signs are unchecked on the real arm.
- the elbow: the real one reads 30 degrees more than the model's (ELBOW_ZERO_DEG, measured 14 Nov); sim.py uses
  no shift. The clearance is also printed with that zero at 20 and 40 degrees, as a measure of how much it matters.
  First run (15 Nov): only the folded home pose is sensitive to it (its lowest point 9 mm at 20, 33 at 30, 54 at
  40); the lowest point while gesturing stays at the same 104.6 mm whichever zero is used.
- gripper 0..100 spread over the jaw's range (an assumption, not measured); it does not move the fingertip site.
"""
import os
import sys
from pathlib import Path

import numpy as np

from core import tremor
from core.arm import HZ, JOINTS, MockArm
from skills import gesture

LIMITS = [(-110, 110), (-100, 100), (-64, 118), (-95, 95), (-180, 180), (0, 100)]  # wrist_roll: checked apart
MAX_DEG_S, GRIP_DEG = 120.0, 1.1
TABLE_Z, CLEAR_MM = -2.4, 20.0
MAX_GESTURE_S = 6.0
OUT = tremor.ROOT / "outputs" / "gestures"


class Recorder(MockArm):
    """The mock arm, every 30 Hz frame it writes kept, and no waiting (a 1/30 s wait per frame is the only change)."""

    def __init__(self):
        super().__init__()
        self.frames, self.starts = [], []
        self.halt.wait = lambda timeout=None: False

    def _write(self, joints):
        super()._write(joints)
        self.frames.append(list(joints))

    def move_joints(self, joints_deg, duration_s):
        self.starts.append(len(self.frames))
        return super().move_joints(joints_deg, duration_s)


def replay(name):
    """(30 Hz frames, index of the first frame of the first step, index of the first frame of the move home)."""
    arm = Recorder()
    arm._write(arm.load_pose("home"))
    assert gesture.run(arm, {"name": name}, arm.halt)["ok"] is True, name
    return np.array(arm.frames), arm.starts[1], arm.starts[-1]


class Body:
    """The model posed by Fingertip, and the moving parts' mesh vertices for the lowest point."""

    def __init__(self):
        root = Path(os.environ.get("SO101_ROOT", tremor.ROOT))
        if not (root / tremor.MODEL / "so101.xml").exists():
            sys.exit(f"no SO-101 model under {root / tremor.MODEL}: set SO101_ROOT to a checkout that has it")
        tremor.ROOT = root
        self.tip = tremor.Fingertip()
        m = self.tip.model
        upper = m.body("upper_arm").id
        self.parts = [(g, m.mesh_vert[m.mesh_vertadr[k]:m.mesh_vertadr[k] + m.mesh_vertnum[k]])
                      for g in self.tip.meshes if m.geom_bodyid[g] >= upper for k in [m.geom_dataid[g]]]

    def heights(self, joints):
        """(tip mm, lowest moving-part vertex z in mm) in this pose."""
        tip = self.tip.mm(joints)
        d = self.tip.data
        low = min((d.geom_xpos[g][2] + verts @ d.geom_xmat[g].reshape(3, 3)[2]).min() for g, verts in self.parts)
        return tip, low * 1000.0


def contact_sheet(body, frames, name):
    """Six frames of the gesture side by side, 320x240 each. Returns the path, or None if rendering failed."""
    import cv2
    import mujoco
    try:
        renderer = mujoco.Renderer(body.tip.model, 240, 320)
    except Exception as e:  # no OpenGL context on this machine
        print(f"  no pictures: offscreen rendering failed ({e})")
        return None
    body.tip.model.vis.headlight.ambient[:] = 0.5   # the model brings no light of its own
    cam = mujoco.MjvCamera()
    cam.lookat[:], cam.distance, cam.azimuth, cam.elevation = (0.15, 0.0, 0.25), 0.7, 125.0, -10.0
    tiles = []
    for i in np.linspace(0, len(frames) - 1, 6).astype(int):
        body.tip._pose(list(frames[i]))
        renderer.update_scene(body.tip.data, cam)
        tiles.append(renderer.render())
    renderer.close()
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / f"{name}.png"
    cv2.imwrite(str(path), cv2.cvtColor(np.hstack(tiles), cv2.COLOR_RGB2BGR))
    return path


def main():
    body = Body()
    home = MockArm().load_pose("home")
    up = MockArm().load_pose("wave_up")
    low_lim = np.array([min(lo, h, u) for (lo, _), h, u in zip(LIMITS, home, up)])
    high_lim = np.array([max(hi, h, u) for (_, hi), h, u in zip(LIMITS, home, up)])
    scale = np.array([1, 1, 1, 1, 1, GRIP_DEG])
    pictures, legs, shifted = [], [], {20.0: [], 40.0: []}
    for name in gesture.GESTURES:
        frames, leave, back = replay(name)
        g = slice(leave - 1, back)   # the gesture: from the last frame on wave_up to the first one back on it
        assert np.allclose(frames[0], home) and np.allclose(frames[-1], home), f"{name}: must start and end at home"
        outside = (frames < low_lim - 1e-9) | (frames > high_lim + 1e-9)
        assert not outside.any(), f"{name}: {JOINTS[np.argwhere(outside)[0][1]]} outside its limits"
        roll = np.abs(frames[g, 4] - up[4]).max()
        assert roll <= 0.01, f"{name}: wrist_roll moves {roll:.3f} degrees from wave_up"
        speed = np.abs(np.diff(frames, axis=0)) * scale * HZ   # speed[i]: from frame i to i + 1
        assert speed.max() <= MAX_DEG_S + 1e-6, \
            f"{name}: {JOINTS[np.argmax(speed.max(axis=0))]} asked for {speed.max():.1f} deg/s"
        seconds = (back - leave) / HZ
        assert seconds <= MAX_GESTURE_S, f"{name}: {seconds:.2f} s between leaving wave_up and returning"
        tips, lows = zip(*(body.heights(f) for f in frames))
        tips, lows = np.array(tips), np.array(lows)
        assert tips[:, 2].min() >= TABLE_Z + CLEAR_MM, f"{name}: tip {tips[:, 2].min():.1f} mm, under table + {CLEAR_MM}"
        assert lows.min() >= TABLE_Z + CLEAR_MM, f"{name}: arm reaches {lows.min():.1f} mm, under table + {CLEAR_MM}"
        travel = np.linalg.norm(tips[g] - tips[leave - 1], axis=1).max()
        legs.append((speed.max(), tips[:, 2].min(), lows.min()))   # the whole replay, home legs included
        for zero in shifted:   # how much the elbow's zero shift matters for the clearance
            tremor.ELBOW_ZERO_DEG = zero
            shifted[zero] += [min(h[1] for h in map(body.heights, frames)), min(body.tip.mm(f)[2] for f in frames)]
        tremor.ELBOW_ZERO_DEG = 30.0
        print(f"{name:12s} {seconds:4.2f} s  peak {speed[g.start:g.stop - 1].max():5.1f} deg/s  "
              f"lowest tip {tips[g, 2].min():6.1f} mm  lowest arm {lows[g].min():6.1f} mm  tip travel {travel:5.1f} mm",
              flush=True)
        if os.environ.get("NO_PICTURES") is None and pictures is not None:
            path = contact_sheet(body, frames[g], name)
            pictures = None if path is None else pictures + [path]
    peak, tip, low = max(l[0] for l in legs), min(l[1] for l in legs), min(l[2] for l in legs)
    print(f"whole replays, home legs included: peak {peak:.1f} deg/s, lowest tip {tip:.1f} mm, lowest arm {low:.1f} mm")
    print("lowest point (arm or tip) with the elbow zero at 20 / 40 degrees instead of 30: "
          f"{min(shifted[20.0]):.1f} / {min(shifted[40.0]):.1f} mm")
    if pictures:
        print(f"contact sheets in {OUT}")
    print("gestures sim ok")


if __name__ == "__main__":
    main()
