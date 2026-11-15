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


MODEL = Path("keypad") / "geometry_dash" / "robotstudio_so101"   # under ROOT; gitignored, so not in every checkout
ELBOW_ZERO_DEG = 30.0    # the real elbow reads 30 degrees more than the model's for the same pose (measured 14 Nov)


class Fingertip:
    """The SO-101 model posed with the real arm's joint angles: the fingertip in mm (to turn joint
    shake into millimetres at the hand) and every part's place, for the dashboard's 3D view."""

    def __init__(self):
        import mujoco
        self.mj = mujoco
        self.model = m = mujoco.MjModel.from_xml_path(str(ROOT / MODEL / "so101.xml"))
        self.data = mujoco.MjData(m)
        self.site = m.site("gripperframe").id
        self.claw = m.jnt_range[m.joint("gripper").id]   # the jaw joint's range, radians: shut .. open
        # the drawn parts are the visual meshes (group 2); group 4 are red collision copies of the jaws
        self.meshes = [g for g in range(m.ngeom) if m.geom_type[g] == mujoco.mjtGeom.mjGEOM_MESH and m.geom_group[g] == 2]
        self.files = [m.paths[m.mesh_pathadr[k]:].split(b"\0")[0].decode() for k in range(m.nmesh)]

    def _pose(self, degrees):
        """The one place real joint angles become the model's: the elbow's zero shift, and the claw's
        0 (shut) .. 100 (open) spread over the jaw joint's range (an assumption: not measured)."""
        q = [math.radians(v) for v in degrees[:5]]
        q[2] -= math.radians(ELBOW_ZERO_DEG)
        self.data.qpos[:5] = q
        if len(degrees) > 5:
            low, high = self.claw
            self.data.qpos[5] = low + (high - low) * min(100.0, max(0.0, float(degrees[5]))) / 100.0
        self.mj.mj_forward(self.model, self.data)

    def mm(self, degrees):
        self._pose(degrees)
        return self.data.site_xpos[self.site] * 1000.0

    def geoms(self, degrees):
        """Every drawn part in this pose: {"mesh": STL file, "pos": mm, "quat": [w, x, y, z], "rgba"}, in
        the model's frame. Placed so the STL file AS IT IS ON DISK (in metres) lands right: MuJoCo moves
        each mesh to its own centre and axes when it loads it (mesh_pos, mesh_quat), so that is undone here."""
        self._pose(degrees)
        m, d, out = self.model, self.data, []
        turn, quat = np.zeros(9), np.zeros(4)
        for g in self.meshes:
            k = m.geom_dataid[g]
            self.mj.mju_quat2Mat(turn, m.mesh_quat[k])
            rot = d.geom_xmat[g].reshape(3, 3) @ turn.reshape(3, 3).T
            pos = d.geom_xpos[g] - rot @ m.mesh_pos[k]
            self.mj.mju_mat2Quat(quat, rot.flatten())
            rgba = m.mat_rgba[m.geom_matid[g]] if m.geom_matid[g] >= 0 else m.geom_rgba[g]   # a material's colour wins
            out.append({"mesh": self.files[k], "pos": [round(float(v) * 1000.0, 2) for v in pos],
                        "quat": [round(float(v), 5) for v in quat], "rgba": [round(float(v), 3) for v in rgba]})
        return out

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


SHAKING_MM = 0.5   # a hand shake under this is treated as "no tremor to speak of"
HOLDING_PCT = 15.0  # grip effort above this means the claw is squeezing something


def insights(trend, test=None):
    """Plain observations from a session so far, for a person (in the story, a physiotherapist) to
    look at. Descriptions of what was measured, never advice and never a diagnosis.

    trend: rows of [seconds, hand shake mm, arm shake mm, grip effort %, tremor Hz], about one a second.
    Every duration below comes from the rows' own timestamps, never from counting rows: the loop that
    writes them can run slow, and "5 rows" is then not "5 seconds".
    Returns a list of {"id", "title", "value", "text"}; empty until there is something to say."""
    rows = [r for r in trend if len(r) >= 4]
    out = []
    if len(rows) < 5:
        return out
    gaps = [b[0] - a[0] for a, b in zip(rows, rows[1:])]
    spans = [0.0] + gaps              # the time each row stands for: since the row before. The first row
    total = sum(spans)                # stands for none, so nothing before the first measurement is counted
    shaking = [r for r in rows if r[1] >= SHAKING_MM]
    shaking_s = sum(span for r, span in zip(rows, spans) if r[1] >= SHAKING_MM)
    if total <= 0:
        return out
    if not shaking:
        return [{"id": "calm", "title": "Shake", "value": "none found",
                 "text": f"No hand shake above {SHAKING_MM} mm in the last {total:.0f} seconds."}]

    hand = statistics.fmean(r[1] for r in shaking)
    arm = statistics.fmean(r[2] for r in shaking)
    removed = max(0.0, 100.0 * (1.0 - arm / hand))
    out.append({"id": "size", "title": "Shake size", "value": f"{hand:.1f} mm",
                "text": f"While shaking, the hand moved {hand:.1f} mm (RMS) at the fingertip and the arm {arm:.1f} mm: "
                        f"{removed:.0f}% less. Shaking was present in {100 * shaking_s / total:.0f}% of the {total:.0f} seconds measured."})

    rates = [r[4] for r in shaking if len(r) > 4 and r[4] > 0]
    if rates:
        rate = statistics.median(rates)
        spread = (max(rates) - min(rates)) if len(rates) > 1 else 0.0
        steady_rate = "It stayed close to that rate" if spread <= 1.5 else f"It wandered over {spread:.1f} Hz"
        out.append({"id": "rate", "title": "Shake rate", "value": f"{rate:.1f} Hz",
                    "text": f"The shake repeated about {rate:.1f} times a second. {steady_rate}. "
                            f"This tool counts {TREMOR_BAND[0]:.0f} to {TREMOR_BAND[1]:.0f} Hz as tremor and slower movement as intended."})

    if shaking_s >= 30 and len(shaking) >= 6:   # needs half a minute of shaking to say anything about change
        third = len(shaking) // 3
        early = statistics.fmean(r[1] for r in shaking[:third])
        late = statistics.fmean(r[1] for r in shaking[-third:])
        change = 100.0 * (late - early) / early if early > 0 else 0.0
        if abs(change) < 15:
            value, text = "about the same", f"The shake was about the same size at the end ({late:.1f} mm) as at the start ({early:.1f} mm)."
        else:
            word = "larger" if change > 0 else "smaller"
            value = f"{abs(change):.0f}% {word}"
            text = (f"The shake was {abs(change):.0f}% {word} in the last third of the session ({late:.1f} mm) than in the "
                    f"first ({early:.1f} mm). One session cannot say why.")
        out.append({"id": "change", "title": "Change during the session", "value": value, "text": text})

    holding = [r[3] for r in rows if r[3] >= HOLDING_PCT]
    holding_s = sum(span for r, span in zip(rows, spans) if r[3] >= HOLDING_PCT)
    if holding_s >= 5 and len(holding) >= 2:
        mean, spread = statistics.fmean(holding), statistics.pstdev(holding)
        evenness = "evenly" if spread < 8 else "unevenly"
        out.append({"id": "grip", "title": "Grip effort", "value": f"{mean:.0f}%",
                    "text": f"The claw held with about {mean:.0f}% of its motor's maximum for {holding_s:.0f} seconds, {evenness} "
                            f"(it varied by {spread:.0f} points). This is the motor's own load reading, an estimate, not a measured force."})

    if test and test.get("score") is not None:
        out.append({"id": "test", "title": "Hold-still test", "value": f"{test['score']} out of 100",
                    "text": f"Hand shake during the last 10-second test: {test['tremor_mm']:.1f} mm. A display scale, not a clinical measure."})
    return out


class GripLatch:
    """One squeeze of the leader's trigger closes the claw and KEEPS it closed; the next squeeze opens it.

    Why: copying the trigger means holding a squeeze for as long as you hold the object, which is what
    a weak or trembling hand does worst (Eddy's suggestion, 14 Nov).

    A squeeze is measured against where the trigger RESTS, not against fixed numbers: the real
    leader's trigger was seen resting at about 43 of 100, so a fixed "released above 45" would never
    have been reached and the claw could never have opened again. The resting level follows the
    trigger up at once and down slowly, and stands still while the trigger is squeezed.
    A squeeze counts once the trigger has stayed `depth` below rest for `dwell_s` (a 5 Hz tremor
    crosses a line for well under 0.1 s), and the next one only after it has come back to within
    half of `depth` (so a hand hovering at the threshold cannot make it chatter)."""

    def __init__(self, closed_to, open_to=60.0, depth=15.0, dwell_s=0.2, settle=3.0, start=None):
        """start: where the claw is now. Until the first deliberate squeeze the latch asks for exactly
        that, so switching it on (or starting up) never opens a claw that is holding something."""
        self.closed_to, self.open_to = closed_to, open_to
        self.depth, self.dwell_s, self.settle = depth, dwell_s, settle   # settle: units a second the rest level may fall
        self.keep = start        # the grip to leave alone until the first squeeze; None once one has happened
        self.closed = start is not None and start < (closed_to + open_to) / 2   # is the claw (nearer to) shut
        self.rest = None         # where the trigger sits when nobody squeezes it
        self._armed = True       # has the trigger been released since the last squeeze
        self._since = None       # when this squeeze began
        self._last = None

    def step(self, t, trigger):
        """Feed the trigger's position (0 shut .. 100 open) at time t; returns the claw target."""
        if self.rest is None:
            self.rest, self._last = trigger, t
        dt, self._last = max(0.0, t - self._last), t
        if trigger < self.rest - self.depth:
            if self._since is None:
                self._since = t
            if self._armed and t - self._since >= self.dwell_s:
                self.closed, self._armed, self.keep = not self.closed, False, None
        else:
            self._since = None
            self.rest = max(trigger, self.rest - self.settle * dt)
            if trigger > self.rest - self.depth / 2:
                self._armed = True
        if self.keep is not None:
            return self.keep
        return self.closed_to if self.closed else self.open_to
