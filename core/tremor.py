"""The tremor maths shared by steady.py and skills/steady.py: the filter, the shake meter, the
fingertip model, the hold-still test and the session summary. Nothing here touches the arms or
imports LeRobot, so anything (tests included) can import it."""
import collections
import math
import statistics
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
CUTOFF_HZ = 3.5          # movement slower than this passes; tremor above it is held back. Was 2.0; raised with the
                         # Notch on the measured tremor (tests/test_steady.py: test_notch has the numbers)
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


NOTCH_Q = 2.0          # notch width: about f/2 Hz wide at half depth, so a tremor that wanders 0.3 Hz is still cut deeply
NOTCH_RETUNE_HZ = 0.3  # the notch moves only when the measured tremor has moved this far


class Notch:
    """A band-stop (biquad notch, per joint) on the hand's own tremor frequency, so the low-pass after it
    can have a higher cut-off and the intended movement arrives sooner.

    It is engaged only while the shake meter reports a hand shake of at least SHAKING_MM at a
    frequency inside TREMOR_BAND, and it follows that frequency slowly: the meter's reading is smoothed
    and the notch moves only when that has moved more than NOTCH_RETUNE_HZ. Its state is kept across a
    retune, so it never jumps. Uneven time steps: the coefficients come from each step's dt; a step too
    long for the frequency (under about 4.4 samples per cycle), or any output that is not a number or
    strays far from the input, lets the input through and restarts the filter settled there."""

    LIMIT_DEG = 20.0   # a notch only takes the tremor out; an output this far from its input has gone wrong

    def __init__(self, q=NOTCH_Q):
        self.q, self.hz, self.heard, self.z = q, None, None, None

    def track(self, tremor_mm, tremor_hz):
        """The shake meter's latest reading (about ten times a second)."""
        if tremor_mm < SHAKING_MM or not TREMOR_BAND[0] <= tremor_hz <= TREMOR_BAND[1]:
            self.hz = self.heard = self.z = None   # off: the next engage starts settled on the input
        elif self.hz is None:
            self.hz = self.heard = float(tremor_hz)
        else:
            self.heard += 0.1 * (tremor_hz - self.heard)   # about a second to follow a change
            if abs(self.heard - self.hz) > NOTCH_RETUNE_HZ:
                self.hz = self.heard

    def step(self, value, dt):
        x = np.asarray(value, float)
        if self.hz is None or not 0.0 < self.hz * dt < 0.225:   # off, or too few samples per cycle to place a notch
            self.z = None
            return x
        w = 2.0 * math.pi * self.hz * dt
        alpha = math.sin(w) / (2.0 * self.q)
        b0, b1, a2 = 1.0 / (1.0 + alpha), -2.0 * math.cos(w) / (1.0 + alpha), (1.0 - alpha) / (1.0 + alpha)
        # (the notch's b2 = b0 and a1 = b1, transposed direct form II)
        if self.z is None:   # settled on x: for a steady input the output is the input
            self.z = [x * (b0 - a2), x * (b0 - a2)]
        y = b0 * x + self.z[0]
        self.z = [b1 * x - b1 * y + self.z[1], b0 * x - a2 * y]
        if not np.all(np.isfinite(y)) or np.any(np.abs(y - x) > self.LIMIT_DEG):
            self.z = None
            return x
        return y


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
            out.append({"mesh": self.files[k], "body": m.body(m.geom_bodyid[g]).name, "pos": [round(float(v) * 1000.0, 2) for v in pos],
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


TRIGGER = {"rest": 43.0, "squeezed": 0.0, "open": 100.0}   # the real leader's trigger, 0..100: it rests mid-range
                                                           # and opens wider than rest (seen 14 Nov)


class GripHold:
    """The claw closes as far as the hand squeezes, STAYS there when the hand relaxes, tightens on a
    later, deeper squeeze, and opens when the hand opens wide (or on "grip release").

    Why: holding a squeeze for as long as you hold the object is what a weak or trembling hand does
    worst (Eddy, 14 Nov), and the on/off latch before this needed the trigger's full travel and jumped
    between fully open and fully shut (first real test, 14 Nov).

    Tremor safety: it is fed the already filtered trigger; `held` only rises to the smallest squeeze of
    the last `dwell_s`, so the hand must KEEP a squeeze for it to count and a spike cannot tighten the
    grip; opening wide must last `release_s` (a 5 Hz tremor stays past a line for well under 0.1 s)."""

    def __init__(self, closed_to, open_to=60.0, rest=43.0, squeezed=0.0, opened=100.0, start=None,
                 dwell_s=0.1, release_s=0.2):
        """start: where the claw is now. `held` starts from it, so starting (or switching hold on) neither
        drops nor crushes anything: a claw at 7 stays at 7 until the person acts. A claw found wider than
        open_to gives a held below 0 and stays that wide too."""
        self.closed_to, self.open_to = closed_to, open_to
        self.rest = rest
        self.span = max(5.0, rest - squeezed)              # a calibration that saw almost no squeeze must not divide by ~0
        self.wide = rest + 0.4 * max(5.0, opened - rest)  # beyond this the hand is "open wide"
        self.dwell_s, self.release_s = dwell_s, release_s
        claw = open_to if start is None else min(100.0, max(closed_to, start))
        self.held = min(1.0, (open_to - claw) / (open_to - closed_to))   # 0 open_to .. 1 closed_to
        self.squeeze = 0.0
        self.from_hand = False   # True once a squeeze (not the start-up) set the grip; for the grip_hold activity
        self._recent = collections.deque()   # (t, squeeze) covering the last dwell_s
        self._wide_since = None
        # a hand found already squeezing, or already open wide, at the start has not acted yet: each
        # counts only after the trigger has been back on the near side of it once
        self._armed_squeeze = self._armed_wide = False

    def squeeze_of(self, trigger):
        return min(1.0, max(0.0, (self.rest - trigger) / self.span))

    def claw(self):
        return self.open_to - self.held * (self.open_to - self.closed_to)

    def copy(self, trigger):
        """Hold mode off: the claw simply follows how far the hand squeezes now."""
        self.squeeze = self.squeeze_of(trigger)
        return self.open_to - self.squeeze * (self.open_to - self.closed_to)

    def release(self):
        self.held, self.from_hand = min(self.held, 0.0), False

    def step(self, t, trigger):
        """Hold mode on: feed the filtered trigger (0 shut .. 100 open) at time t; returns the claw target."""
        self.squeeze = self.squeeze_of(trigger)
        self._armed_squeeze |= self.squeeze <= max(0.0, self.held)
        self._armed_wide |= trigger <= self.wide
        self._recent.append((t, self.squeeze))
        while len(self._recent) > 1 and self._recent[1][0] <= t - self.dwell_s:
            self._recent.popleft()
        if self._armed_squeeze and self._recent[0][0] <= t - self.dwell_s:   # covered: the hand has KEPT at least this
            kept = min(s for _, s in self._recent)
            # 0.05: the trigger's reading wanders a unit or two at rest; that is not a squeeze
            if kept >= 0.05 and kept > self.held:
                self.held, self.from_hand = kept, True
        if trigger > self.wide and self._armed_wide:
            self._wide_since = t if self._wide_since is None else self._wide_since
            if t - self._wide_since >= self.release_s:
                self.release()
        else:
            self._wide_since = None
        return self.claw()


ARM = ["shoulder_pan", "shoulder_lift", "elbow_flex", "wrist_flex", "wrist_roll"]   # the five arm joints, motor names
TARGET_RANGE_DEG = np.array([90.0, 70.0, 70.0, 80.0, 120.0])   # how far the ROBOT should be able to go on each, degrees
BARELY_DEG = 5.0      # a joint moved less than this in calibration was not really moved: it keeps gain 1.0
REST_S, MOVE_S = 3.0, 12.0


class Calibration:
    """The user calibration: 3 s of rest (the neutral pose and the trigger's resting place), then 12 s
    of moving every joint and the trigger as far as is comfortable. feed() takes the filtered joints
    every tick and returns the result once, on the tick that ends it."""

    def __init__(self):
        self.phase, self.end, self.short = "idle", 0.0, []
        self.seen, self.trigger_seen = np.zeros(5), 0.0

    def running(self):
        return self.phase in ("rest", "move")

    def start(self, now):
        self.phase, self.end, self.short = "rest", now + REST_S, []
        self.seen, self.trigger_seen, self.poses, self.triggers = np.zeros(5), 0.0, [], []

    def cancel(self):
        self.phase = "idle"

    def feed(self, now, joints, trigger):
        joints = np.asarray(joints[:5], float)
        if self.phase == "rest":
            self.poses.append(joints)
            self.triggers.append(float(trigger))
            if now >= self.end:
                self.neutral, self.rest = np.median(self.poses, axis=0), float(np.median(self.triggers))
                self.low, self.high, self.t_low, self.t_high = self.neutral.copy(), self.neutral.copy(), self.rest, self.rest
                self.phase, self.end = "move", now + MOVE_S
        elif self.phase == "move":
            self.low, self.high = np.minimum(self.low, joints), np.maximum(self.high, joints)
            self.t_low, self.t_high = min(self.t_low, trigger), max(self.t_high, trigger)
            covered = self.high - self.low
            self.seen, self.trigger_seen = np.minimum(1.0, covered / TARGET_RANGE_DEG), min(1.0, (self.t_high - self.t_low) / 100.0)
            if now >= self.end:
                self.phase = "done"
                barely = covered < BARELY_DEG   # noise, not a range: dividing by it would give gain 3 from nothing
                gains = np.where(barely, 1.0, np.clip(TARGET_RANGE_DEG / np.maximum(covered, BARELY_DEG), 1.0, 3.0))
                squeezed = self.t_low if self.rest - self.t_low >= 5.0 else TRIGGER["squeezed"]   # under 5: not seen, default
                opened = self.t_high if self.t_high - self.rest >= 5.0 else TRIGGER["open"]
                self.short = [name for name, b in zip(ARM, barely) if b] + \
                             ["trigger squeeze"] * (self.rest - self.t_low < 5.0) + ["trigger open"] * (self.t_high - self.rest < 5.0)
                return {"calibrated": True, "neutral": [round(float(v), 2) for v in self.neutral],
                        "range_deg": [round(float(v), 1) for v in covered], "gains": [round(float(g), 2) for g in gains],
                        "trigger": {"rest": round(self.rest, 1), "squeezed": round(float(squeezed), 1), "open": round(float(opened), 1)}}
        return None

    def view(self, now):
        """For /state. `insufficient`: what the person barely moved in the last calibration (left at the defaults)."""
        return {"phase": self.phase, "seconds_left": round(max(0.0, self.end - now), 1) if self.running() else 0.0,
                "seen": [round(float(v), 2) for v in self.seen], "trigger_seen": round(self.trigger_seen, 2),
                "insufficient": list(self.short)}


def activities(tests, past, user, steady_s, grip_s, grips):
    """The session's activities for the dashboard, from measurements only: a value is None until measured.
    tests: this session's hold-still results; past: earlier sessions.json summaries; user: the profile;
    steady_s: seconds with the filter on; grip_s, grips: the longest held grip and how many."""
    past = [s for s in past if isinstance(s, dict)]
    scores = [t["score"] for s in past for t in s.get("tests", []) if isinstance(t, dict) and isinstance(t.get("score"), (int, float))]
    scores += [t["score"] for t in tests]
    steady_min = [s["duration_s"] * s["steady_share_pct"] / 6000.0 for s in past
                  if isinstance(s.get("duration_s"), (int, float)) and isinstance(s.get("steady_share_pct"), (int, float))]
    reach = round(float(np.mean(user["range_deg"])), 1) if user.get("calibrated") else None
    return [
        {"id": "hold_still", "title": "Hold still", "unit": "score", "last": scores[-1] if scores else None,
         "best": max(scores) if scores else None, "runs": len(scores),
         "detail": "10 seconds; 100 means no shake. A display scale, not a clinical measure."},
        {"id": "range", "title": "Comfortable range", "unit": "degrees", "last": reach, "best": user.get("best_range"),
         "runs": user.get("calibrations", 0),
         "detail": "Mean range over the five arm joints in the last calibration, as the person chose to move."},
        {"id": "steady_time", "title": "Steady time", "unit": "minutes", "last": round(steady_s / 60.0, 1),
         "best": round(max(steady_min + [steady_s / 60.0]), 1), "runs": len(steady_min) + 1,
         "detail": "Minutes with the filter on, this session; best over the saved sessions and this one."},
        {"id": "grip_hold", "title": "Grip hold", "unit": "seconds", "last": round(grip_s, 1) if grips else None,
         "best": None, "runs": grips, "detail": "The longest grip kept by grip hold this session."},
    ]
