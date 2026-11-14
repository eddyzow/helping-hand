"""The tremor maths shared by steady.py and skills/steady.py: the filter, the shake meter, the
fingertip model, the hold-still test and the session summary. Nothing here touches the arms or
imports LeRobot, so anything (tests included) can import it."""
import math
import statistics
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
CUTOFF_HZ = 2.0          # movement slower than this passes; tremor above it is held back
GRIP_CUTOFF_HZ = 4.0     # the claw answers faster, so a pinch still feels direct
TREMOR_BAND = (3.0, 12.0)  # Hz: where tremor lives (essential tremor about 4 to 8, Parkinsonian about 4 to 6)
TEST_S = 10.0            # how long the hold-still test measures
SCORE_ZERO_MM = 20.0     # a mean hand shake this big scores 0; a display scale, not a clinical measure


class LowPass:
    """Two one-pole stages in a row: smooth, no overshoot, about 12 dB per octave above the cutoff."""

    def __init__(self, first):
        self.a = self.b = np.array(first, float)

    def step(self, value, cutoff_hz, dt):
        k = 1.0 - np.exp(-2.0 * math.pi * np.asarray(cutoff_hz) * dt)
        self.a = self.a + k * (np.asarray(value, float) - self.a)
        self.b = self.b + k * (self.a - self.b)
        return self.b


def band_rms_and_peak(samples, rate):
    """Size (RMS) and main frequency of the part of a signal inside the tremor band."""
    x = np.asarray(samples, float)
    if len(x) < rate:  # under a second of data says nothing about a 4 Hz shake
        return 0.0, 0.0
    x = x - x.mean(axis=0)
    spectrum = np.fft.rfft(x * np.hanning(len(x))[:, None], axis=0)
    freqs = np.fft.rfftfreq(len(x), 1.0 / rate)
    band = (freqs >= TREMOR_BAND[0]) & (freqs <= TREMOR_BAND[1])
    power = (np.abs(spectrum) ** 2).sum(axis=1)
    if not band.any() or power[band].sum() <= 0:
        return 0.0, 0.0
    # Parseval, corrected for the window: RMS of the band-limited signal, summed over x, y, z
    rms = math.sqrt(2.0 * power[band].sum() / (len(x) * (np.hanning(len(x)) ** 2).sum()))
    return rms, float(freqs[band][np.argmax(power[band])])


class Fingertip:
    """Where the fingertip is for a set of joint angles, from the SO-101 model. Used only to turn
    joint shake into millimetres at the hand; a few degrees of zero error do not matter for that."""

    def __init__(self):
        import mujoco
        self.mj = mujoco
        self.model = mujoco.MjModel.from_xml_path(str(ROOT / "keypad" / "geometry_dash" / "robotstudio_so101" / "so101.xml"))
        self.data = mujoco.MjData(self.model)
        self.site = self.model.site("gripperframe").id

    def mm(self, degrees):
        self.data.qpos[:5] = [math.radians(v) for v in degrees[:5]]
        self.mj.mj_forward(self.model, self.data)
        return self.data.site_xpos[self.site] * 1000.0

    def chain(self, degrees):
        """The arm as a line of points (mm), base to fingertip, for the dashboard's drawing."""
        tip = self.mm(degrees)
        points = [self.data.xpos[i] * 1000.0 for i in range(1, 7)] + [tip]  # base, shoulder, upper arm, forearm, wrist, gripper
        return [[round(float(v)) for v in point] for point in points]


def score(tremor_mm):
    """100 for no shake, falling in a straight line to 0 at SCORE_ZERO_MM."""
    return int(round(max(0.0, min(100.0, 100.0 * (1.0 - tremor_mm / SCORE_ZERO_MM)))))


class HoldStillTest:
    """The ten-second hold-still test. start() opens the window, feed() takes the hand shake ten
    times a second and returns the result on the sample that closes the window."""

    def __init__(self):
        self.end, self.samples, self.result = None, [], {"score": None, "tremor_mm": None}

    def start(self, now):
        self.end, self.samples = now + TEST_S, []

    def feed(self, now, tremor_mm):
        if self.end is None:
            return None
        self.samples.append(tremor_mm)
        if now < self.end:
            return None
        mean = sum(self.samples) / len(self.samples)
        self.end, self.result = None, {"score": score(mean), "tremor_mm": round(mean, 2)}
        return dict(self.result)

    def view(self, now):
        if self.end is None:
            return {"running": False, "seconds_left": 0, **self.result}
        return {"running": True, "seconds_left": round(max(0.0, self.end - now), 1), "score": None, "tremor_mm": None}


class Session:
    """One session's summary for sessions.json, built from the ten-a-second measurements."""

    def __init__(self, start_iso):
        self.start, self.t, self.n, self.steady_n = start_iso, 0.0, 0, 0
        self.tremor, self.arm, self.peak, self.hz, self.tests = 0.0, 0.0, 0.0, [], []

    def add(self, t, tremor_mm, tremor_hz, out_mm, steady):
        self.t, self.n, self.steady_n = t, self.n + 1, self.steady_n + bool(steady)
        self.tremor, self.arm, self.peak = self.tremor + tremor_mm, self.arm + out_mm, max(self.peak, tremor_mm)
        if tremor_mm >= 0.3:  # below this the frequency is noise
            self.hz.append(tremor_hz)

    def summary(self):
        tremor, arm = self.tremor / max(1, self.n), self.arm / max(1, self.n)
        removed = 0.0 if tremor < 0.15 else max(0.0, min(100.0, 100.0 * (1.0 - arm / tremor)))
        return {"start": self.start, "duration_s": round(self.t, 1), "mean_tremor_mm": round(tremor, 2),
                "peak_tremor_mm": round(self.peak, 2), "tremor_hz": round(statistics.median(self.hz), 1) if self.hz else 0.0,
                "mean_arm_mm": round(arm, 2), "removed_pct": round(removed, 1),
                "steady_share_pct": round(100.0 * self.steady_n / max(1, self.n), 1), "tests": list(self.tests)}
