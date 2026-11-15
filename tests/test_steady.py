"""Run with python -m tests.test_steady; synthetic signals only, no arm, no serial port."""
import json
import math
import tempfile

import numpy as np

import steady


def test_steady():
    hz, dt = steady.HZ, 1 / steady.HZ
    t = np.arange(0, 8, dt)
    half = len(t) // 2

    def size(signal, freq):  # amplitude of one frequency, by projection, after the filter has settled
        return 2 * abs(np.mean(signal[half:] * np.exp(-2j * math.pi * freq * t[half:])))

    # the filter: a slow reach passes, a 6 Hz shake is held back. The low-pass alone at the old 2.0 Hz;
    # and the default since v2, the notch on the measured shake then the low-pass at CUTOFF_HZ, the same
    # (the default low-pass alone no longer removes 85 %: the notch does the rest, see test_notch)
    from core.tremor import Notch
    reach, shake = 20 * np.sin(2 * math.pi * 0.5 * t), 3 * np.sin(2 * math.pi * 6 * t)
    low = steady.LowPass([0.0])
    out = np.array([low.step([a + b], 2.0, dt)[0] for a, b in zip(reach, shake)])
    assert size(out, 0.5) > 17, size(out, 0.5)   # at least 85 % of the reach comes through
    assert size(out, 6.0) < 0.45, size(out, 6.0)  # at least 85 % of the shake is gone
    low, notch = steady.LowPass([0.0]), Notch()
    notch.track(2.0, 6.0)   # what the meter reports for this shake
    out = np.array([low.step(notch.step([a + b], dt), steady.CUTOFF_HZ, dt)[0] for a, b in zip(reach, shake)])
    assert size(out, 0.5) > 17, size(out, 0.5)
    assert size(out, 6.0) < 0.45, size(out, 6.0)

    # the meter: a 5 mm, 6 Hz shake on top of a slow 40 mm movement reads 3.54 mm RMS at 6 Hz
    tips = np.zeros((int(steady.WINDOW_S * hz), 3))
    tips[:, 2] = 5 * np.sin(2 * math.pi * 6 * t[:len(tips)]) + 40 * np.sin(2 * math.pi * 0.4 * t[:len(tips)])
    rms, peak = steady.band_rms_and_peak(tips, hz)
    assert abs(rms - 5 / math.sqrt(2)) < 0.4 and abs(peak - 6.0) < 0.3, (rms, peak)
    assert steady.band_rms_and_peak(tips[:10], hz) == (0.0, 0.0)  # too little data says nothing

    # the keys: middle key toggles steady, jump key toggles hold, stop always holds
    steady.state.update(steady=True, hold=False, cutoff=steady.CUTOFF_HZ)
    assert steady.command("run gesture")["steady"] is False and steady.command("steady on")["steady"] is True
    # "steady off" is what a person says: it must freeze the arm and must NOT let the shake through
    off = steady.command("steady off")
    assert off["hold"] is True and off["steady"] is True, off
    on = steady.command("steady on")
    assert on["hold"] is False and on["steady"] is True, on
    # only "filter off" (the dashboard button, the middle key, a typed line) shows the unfiltered arm
    assert steady.command("filter off")["steady"] is False and steady.command("filter on")["steady"] is True
    assert steady.command("key down")["hold"] is True and steady.command("hold off")["hold"] is False
    assert steady.command("stop")["hold"] is True
    assert steady.command("cutoff 99")["cutoff"] == 8.0 and steady.command("cutoff x")["ok"] is False
    assert steady.command("dance")["ok"] is False


def test_core_tremor():
    from pathlib import Path

    from core import tremor

    # the maths moved, unchanged: steady.py uses core.tremor's copy, and it reads the same numbers
    assert steady.LowPass is tremor.LowPass and steady.band_rms_and_peak is tremor.band_rms_and_peak
    t = np.arange(0, steady.WINDOW_S, 1 / steady.HZ)
    tips = np.zeros((len(t), 3))
    tips[:, 2] = 5 * np.sin(2 * math.pi * 6 * t) + 40 * np.sin(2 * math.pi * 0.4 * t)
    rms, peak = tremor.band_rms_and_peak(tips, steady.HZ)
    assert abs(rms - 3.54) < 0.05 and peak == 6.0, (rms, peak)
    low = tremor.LowPass([0.0])
    assert abs(low.step([1.0], 2.0, 0.02)[0] - (1 - math.exp(-2 * math.pi * 2.0 * 0.02)) ** 2) < 1e-12   # the maths, at 2 Hz
    assert tremor.CUTOFF_HZ == 3.5   # the default since the notch (test_notch)

    # the hold-still test, on a fake clock
    test = tremor.HoldStillTest()
    assert test.view(0.0) == {"running": False, "seconds_left": 0, "score": None, "tremor_mm": None}
    test.start(100.0)
    assert test.view(103.0) == {"running": True, "seconds_left": 7.0, "score": None, "tremor_mm": None}
    for i in range(100):
        assert test.feed(100.0 + i / 10, 0.0) is None
    assert test.feed(110.0, 0.0) == {"score": 100, "tremor_mm": 0.0}
    assert test.view(111.0) == {"running": False, "seconds_left": 0, "score": 100, "tremor_mm": 0.0}
    assert test.feed(112.0, 5.0) is None  # nothing is measured between tests
    assert tremor.score(10.0) == 50 and tremor.score(30.0) == 0 and tremor.score(0.0) == 100

    # the session summary: 10 s of steady at 4 mm / 6 Hz, then 10 s raw at 2 mm / 5 Hz, a quiet bit, one test
    session = tremor.Session("2026-11-14T21:00:00")
    for i in range(200):
        on = i < 100
        session.add(i / 10, 4.0 if on else 2.0, 6.0 if on else 5.0, 0.4 if on else 2.0, on)
    session.add(20.0, 0.1, 9.0, 0.1, False)  # under 0.3 mm: its frequency does not count
    session.tests.append({"score": 80, "tremor_mm": 4.0})
    s = session.summary()
    assert s == {"start": "2026-11-14T21:00:00", "duration_s": 20.0, "mean_tremor_mm": 2.99, "peak_tremor_mm": 4.0,
                 "tremor_hz": 5.5, "mean_arm_mm": 1.19, "removed_pct": 60.0, "steady_share_pct": 49.8,
                 "tests": [{"score": 80, "tremor_mm": 4.0}]}, s

    # the commands and the history file
    assert steady.command("test")["ok"] is True and steady.shared["test"]["running"] is True
    assert steady.shared["test"]["seconds_left"] > 9.5
    assert steady.read_sessions(Path("no_such_folder") / "sessions.json") == []
    with tempfile.TemporaryDirectory() as folder:
        steady.save_sessions([s], Path(folder) / "sessions.json")
        assert steady.read_sessions(Path(folder) / "sessions.json") == [s]


def test_insights():
    from core import tremor

    assert tremor.insights([]) == []
    assert tremor.insights([[i, 0.1, 0.0, 2.0, 0.0] for i in range(20)])[0]["id"] == "calm"
    # 90 s: the shake grows from 6 to 9 mm at 5.5 Hz, the arm stays at 0.6 mm, the claw holds at about 40 %
    trend = [[i, 6.0 + 3.0 * i / 89, 0.6, 40.0 + (i % 3), 5.5] for i in range(90)]
    out = tremor.insights(trend, {"score": 62, "tremor_mm": 7.6})
    by = {o["id"]: o for o in out}
    assert list(by) == ["size", "rate", "change", "grip", "test"], list(by)
    assert by["size"]["value"] == "7.5 mm" and "92% less" in by["size"]["text"], by["size"]
    assert by["rate"]["value"] == "5.5 Hz" and by["change"]["value"] == "31% larger", (by["rate"], by["change"])
    assert by["grip"]["value"] == "41%" and by["test"]["value"] == "62 out of 100"
    # durations come from the timestamps, not from counting rows: five rows two seconds apart span 8 s
    slow = tremor.insights([[2.0 * i, 0.1, 0.0, 40.0, 0.0] for i in range(5)])
    assert "last 8 seconds" in slow[0]["text"], slow
    slow = {o["id"]: o for o in tremor.insights([[2.0 * i, 5.0, 0.5, 40.0, 6.0] for i in range(20)])}
    assert "for 38 seconds" in slow["grip"]["text"] and "of the 38 seconds measured" in slow["size"]["text"], slow
    assert "change" in slow, "38 s of shaking in 20 rows is enough to compare the start with the end"
    # uneven rows: nothing before the first measurement is counted (1, 11, 12, 13, 14 is 13 s, not 23)
    uneven = tremor.insights([[t, 0.1, 0.0, 40.0, 0.0] for t in (1, 11, 12, 13, 14)])
    assert "last 13 seconds" in uneven[0]["text"], uneven
    flat = tremor.insights([[i, 5.0, 0.5, 0.0, 6.0] for i in range(60)])
    assert [o["id"] for o in flat] == ["size", "rate", "change"] and flat[2]["value"] == "about the same"
    for o in out + flat:  # the wording rules: observations only, and grip effort is never called a force
        low = o["text"].lower()
        assert not any(word in low for word in ("torque", "therapy", "treatment", "diagnos", "improv")), o
        assert "force" not in low or "not a measured force" in low, o
    # RobTop's voice script reports to the dashboard through the same command port
    assert steady.command('voice {"heard": "hold this", "said": "I have it"}')["ok"]
    assert steady.shared["voice"]["heard"] == "hold this" and steady.command("voice nonsense")["ok"] is False


def test_grip_hold():
    from core import tremor

    def play(grip, trigger_at, seconds, start=0.0, hz=50):
        """Feed the grip a trigger signal (time from 0 within this call); returns the claw target at each tick."""
        return [grip.step(start + i / hz, trigger_at(i / hz)) for i in range(int(seconds * hz))]

    # rest 43, squeezed 0, open 100; the claw spans 60 (open) .. 7 (shut)
    grip = tremor.GripHold(closed_to=7.0)
    assert set(play(grip, lambda t: 43.0, 1.0)) == {60.0}                         # a relaxed hand: open
    out = play(grip, lambda t: 21.5, 1.0, start=1.0)                               # half a squeeze ...
    assert out[2] == 60.0 and abs(out[-1] - 33.5) < 1e-9, out[-1]                  # ... closes half way, after 0.1 s
    out = play(grip, lambda t: 43.0, 2.0, start=2.0)                               # the hand relaxes
    assert set(out) == {33.5}, "the claw must stay where the squeeze left it"
    out = play(grip, lambda t: 40.0, 1.0, start=4.0)                               # a smaller squeeze does nothing
    assert set(out) == {33.5}
    out = play(grip, lambda t: 10.75, 1.0, start=5.0)                              # a deeper one tightens it
    assert abs(out[-1] - 20.25) < 1e-9 and grip.from_hand
    small = tremor.GripHold(closed_to=7.0)
    assert abs(play(small, lambda t: 43.0 - 4.3 * min(1.0, t), 2.0)[-1] - 54.7) < 0.01, "a small squeeze must close a little"
    # opening wide (beyond 43 + 0.4 * 57 = 65.8) for 0.2 s releases; a shorter flick does not
    out = play(grip, lambda t: 90.0, 0.15, start=6.0)
    assert out[-1] == 20.25, "0.15 s of open hand released the grip"
    play(grip, lambda t: 43.0, 0.2, start=6.15)
    out = play(grip, lambda t: 90.0, 0.4, start=6.35)
    assert out[5] == 20.25 and out[-1] == 60.0 and not grip.from_hand
    # a 6 Hz tremor on the trigger, swinging past both the squeeze and the open-wide lines, neither
    # tightens nor releases the grip (each swing lasts under 0.1 s past a line)
    grip = tremor.GripHold(closed_to=7.0, start=33.5)
    out = play(grip, lambda t: 43.0 + 30.0 * math.sin(2 * math.pi * 6 * t), 5.0)
    assert set(out) == {33.5}, ("a tremor moved the grip", min(out), max(out))
    # the same tremor on top of a kept squeeze tightens only to what the hand KEPT, not to the spikes
    grip = tremor.GripHold(closed_to=7.0)
    out = play(grip, lambda t: 43.0 if t < 0.5 else 21.5 + 5.0 * math.sin(2 * math.pi * 6 * t), 2.0)
    # between the squeeze's trough (trigger 26.5: claw 39.7) and its mean (21.5: 33.5); its peaks (16.5) would be 27.3
    assert 33.5 < out[-1] < 60.0 - 53.0 * 16.5 / 43.0 + 0.01, out[-1]
    # start-up keeps the grip it finds: a claw shut at 7 with the hand already open wide stays at 7,
    # and a hand already squeezing does not tighten a claw found half open, until the person acts
    grip = tremor.GripHold(closed_to=7.0, start=7.0)
    assert set(play(grip, lambda t: 80.0, 3.0)) == {7.0}, "starting opened a claw nobody asked to open"
    out = play(grip, lambda t: 43.0 if t < 0.5 else 80.0, 1.0, start=3.0)      # back, then open wide: that is acting
    assert out[-1] == 60.0
    grip = tremor.GripHold(closed_to=7.0, start=33.0)
    assert set(play(grip, lambda t: 5.0, 2.0)) == {33.0}, "starting squeezed the claw harder"
    out = play(grip, lambda t: 43.0 if t < 0.5 else 5.0, 1.0, start=2.0)
    assert out[-1] < 20.0
    grip = tremor.GripHold(closed_to=7.0, start=80.0)                               # found wider than 60: stays that wide
    assert set(play(grip, lambda t: 43.0, 1.0)) == {80.0}
    # grip release opens; hold off copies the squeeze; a calibrated trigger is used
    grip = tremor.GripHold(closed_to=7.0, start=7.0)
    grip.release()
    assert grip.claw() == 60.0 and grip.copy(21.5) == 33.5 and grip.copy(43.0) == 60.0 and grip.copy(0.0) == 7.0
    grip = tremor.GripHold(closed_to=7.0, rest=50.0, squeezed=30.0, opened=90.0)
    assert grip.copy(40.0) == 33.5 and grip.wide == 66.0
    assert tremor.GripHold(closed_to=7.0, rest=40.0, squeezed=40.0, opened=40.0).span == 5.0   # no divide by ~0
    # the commands: grip hold on|off, the old latch alias, grip release (refused while the arm is held)
    steady.state.update(grip_hold=True, hold=False, release=False)
    assert steady.command("grip hold off")["grip_hold"] is False and steady.command("grip hold on")["grip_hold"] is True
    assert steady.command("latch off")["grip_hold"] is False and steady.command("latch")["latch"] is True
    assert steady.command("latch maybe")["ok"] is False and steady.command("grip maybe")["ok"] is False
    assert steady.command("grip release")["ok"] is True and steady.state["release"] is True
    steady.state.update(release=False)
    steady.command("hold on")
    refused = steady.command("grip release")
    assert refused["ok"] is False and "held" in refused["reason"] and steady.state["release"] is False
    assert steady.state["hold"] is True, "grip release must never clear a hold"
    steady.command("hold off")


def test_notch():
    from core import tremor

    # the comparison the change was kept on: a 5.5 Hz, 3 degree shake on a 0.5 Hz, 20 degree reach, 50 Hz
    dt = 1 / steady.HZ
    t = np.arange(0, 20, dt)
    half = len(t) // 2
    reach, shake = 20 * np.sin(2 * math.pi * 0.5 * t), 3 * np.sin(2 * math.pi * 5.5 * t)
    part = lambda signal, freq: 2 * np.mean(signal[half:] * np.exp(-2j * math.pi * freq * t[half:]))

    def run(cutoff, notch_hz):
        low, notch = tremor.LowPass([0.0]), tremor.Notch()
        if notch_hz:
            notch.track(3.0, notch_hz)
        out = np.array([low.step(notch.step([v], dt), cutoff, dt)[0] for v in reach + shake])
        lag = -np.angle(part(out, 0.5) / part(reach, 0.5)) / (2 * math.pi * 0.5)   # seconds behind the reach
        return lag, abs(part(out, 5.5)) / 3.0                                         # share of the shake left

    old_lag, old_left = run(2.0, None)
    new_lag, new_left = run(tremor.CUTOFF_HZ, 5.5)
    off_lag, off_left = run(tremor.CUTOFF_HZ, 5.8)   # the notch 0.3 Hz off the shake, as far as it is let drift
    print(f"  filter: old 2.0 Hz low-pass lags {1000 * old_lag:.1f} ms, leaves {100 * old_left:.1f}% of the shake; "
          f"new {tremor.CUTOFF_HZ} Hz + notch lags {1000 * new_lag:.1f} ms, leaves {100 * new_left:.1f}% "
          f"({100 * off_left:.1f}% with the notch 0.3 Hz off)")
    assert new_left <= 0.15 and new_lag < old_lag, "keep CUTOFF_HZ at 2.0: the new design does not beat it"
    assert off_left <= 0.15 and off_lag < old_lag

    # in the loop: the meter finds the shake, tunes the notch, and the arm keeps little of it
    shaky = lambda t: np.array([20 * math.sin(2 * math.pi * 0.5 * t) + 3 * math.sin(2 * math.pi * 5.5 * t), 0, 0, 0, 0, 43.0])
    _, _, final = run_loop(shaky, 10.0)
    assert abs(final["tremor_hz"] - 5.5) < 0.3 and final["removed_pct"] >= 85, (final["tremor_hz"], final["removed_pct"])

    # it engages only on a measured shake of at least 0.5 mm inside the tremor band
    notch = tremor.Notch()
    for mm, hz in ((0.4, 5.5), (2.0, 2.0), (2.0, 13.0)):
        notch.track(mm, hz)
        assert notch.hz is None and np.array_equal(notch.step([1.0, 2.0], dt), [1.0, 2.0])
    # it follows the frequency slowly: 0.25 Hz away never retunes it, a lasting move of 0.5 Hz does
    notch.track(2.0, 5.5)
    for _ in range(100):
        notch.track(2.0, 5.75)
    assert notch.hz == 5.5
    retuned = []
    for _ in range(100):
        notch.track(2.0, 6.0)
        retuned.append(notch.hz)
    assert len(set(retuned)) == 2 and 5.8 < retuned[-1] < 6.0, sorted(set(retuned))
    # and engaging and retuning keep the output continuous (no jump on a slow reach)
    notch, last, worst = tremor.Notch(), 0.0, 0.0
    for i, v in enumerate(reach[:500]):
        if i == 100:
            notch.track(2.0, 5.5)
        if i == 300:
            notch.hz = 7.0
        out = notch.step([v], dt)[0]
        worst, last = max(worst, abs(out - last)), out
    assert worst < 1.5, worst   # the reach itself moves up to 1.26 degrees a step

    # stable at every tremor frequency at 50 Hz, and with uneven steps it never blows up
    rng = np.random.default_rng(1)
    for hz in np.arange(3.0, 12.01, 0.5):
        notch = tremor.Notch()
        notch.track(2.0, hz)
        x = 10 * np.sin(2 * math.pi * 0.7 * t) + 3 * np.sin(2 * math.pi * hz * t) + rng.normal(0, 1, len(t))
        out = np.array([notch.step([v], dt)[0] for v in x])
        assert np.all(np.isfinite(out)) and np.abs(out).max() < 3 * np.abs(x).max(), hz
        steps = rng.uniform(0.001, 0.25, 2000)
        out = np.array([notch.step([10 * math.sin(i / 7)], step)[0] for i, step in enumerate(steps)])
        assert np.all(np.isfinite(out)) and np.abs(out).max() <= 10 + tremor.Notch.LIMIT_DEG, hz


def model_root():
    """A folder holding the SO-101 model (gitignored, so a worktree may lack it): this checkout, or
    one above it (a worktree lives inside the main checkout). None, with a note, if there is none."""
    from core import tremor
    for root in [tremor.ROOT, *tremor.ROOT.parents]:
        if (root / tremor.MODEL / "so101.xml").exists():
            return root
    print("  note: no SO-101 model folder found; the model checks are skipped")
    return None


def get(path):
    """Call the dashboard's handler in memory, no socket: returns (status, content type, body)."""
    import io
    handler = steady.Dashboard.__new__(steady.Dashboard)
    handler.path, handler.command, handler.request_version = path, "GET", "HTTP/1.1"
    handler.requestline, handler.client_address, handler.wfile = f"GET {path} HTTP/1.1", ("test", 0), io.BytesIO()
    handler.do_GET()
    head, _, body = handler.wfile.getvalue().partition(b"\r\n\r\n")
    lines = head.decode().split("\r\n")
    kind = next((line.split(": ", 1)[1] for line in lines if line.startswith("Content-Type")), "")
    return int(lines[0].split()[1]), kind, body


def test_model_and_meshes():
    from unittest.mock import patch

    from core import tremor
    root = model_root()
    if root is None:
        return
    with patch.object(tremor, "ROOT", root):
        tip = tremor.Fingertip()
        # the elbow's zero shift lives in Fingertip: a real elbow at 30 is the model's elbow at 0
        tip.data.qpos[:] = 0.0
        tip.mj.mj_forward(tip.model, tip.data)
        straight = tip.data.site_xpos[tip.site] * 1000.0
        assert np.allclose(tip.mm([0, 0, tremor.ELBOW_ZERO_DEG, 0, 0, 50]), straight), "the elbow shift is not applied"
        # every visual mesh, and the STL file as it is on disk lands where MuJoCo has the part
        parts = tip.geoms([10, -20, 40, 15, 30, 70])
        assert len(parts) == len(tip.meshes) and all(set(p) == {"mesh", "body", "pos", "quat", "rgba"} for p in parts)
        assert all(abs(np.linalg.norm(p["quat"]) - 1) < 1e-4 for p in parts)
        for part, g in zip(parts, tip.meshes):
            raw = (root / tremor.MODEL / "assets" / part["mesh"]).read_bytes()   # binary STL: 80 byte header, count, 50 byte facets
            facets = np.frombuffer(raw, np.dtype([("n", "<f4", 3), ("v", "<f4", (3, 3)), ("a", "<u2")]),
                                   int(np.frombuffer(raw, np.uint32, 1, 80)[0]), 84)
            rot = np.zeros(9)
            tip.mj.mju_quat2Mat(rot, np.array(part["quat"], float))
            drawn = facets["v"].reshape(-1, 3) @ rot.reshape(3, 3).T * 1000.0 + part["pos"]   # metres on disk, mm out
            k = tip.model.geom_dataid[g]
            vert = tip.model.mesh_vert[tip.model.mesh_vertadr[k]:tip.model.mesh_vertadr[k] + tip.model.mesh_vertnum[k]]
            truth = (vert @ tip.data.geom_xmat[g].reshape(3, 3).T + tip.data.geom_xpos[g]) * 1000.0
            assert np.allclose(drawn.min(0), truth.min(0), atol=0.1) and np.allclose(drawn.max(0), truth.max(0), atol=0.1), part
        # the claw joint turns the jaw (its file's origin sits on the hinge, so the rotation is what changes)
        jaw = lambda claw: next(p["quat"] for p in tip.geoms([0, 0, 0, 0, 0, claw]) if p["mesh"] == "moving_jaw_so101_v1.stl")
        assert jaw(0) != jaw(100)
        # the routes: the list, a file, and nothing from outside the assets folder
        status, kind, body = get("/meshes/index.json")
        names = json.loads(body)
        assert status == 200 and kind == "application/json" and "upper_arm_so101_v1.stl" in names, names
        assert {p["mesh"] for p in parts} <= set(names)
        status, kind, body = get("/meshes/upper_arm_so101_v1.stl")
        assert status == 200 and kind == "model/stl" and body == (root / tremor.MODEL / "assets" / "upper_arm_so101_v1.stl").read_bytes()
        for bad in ("/meshes/../so101.xml", "/meshes/../../../../steady.py", "/meshes/..%2fso101.xml", "/meshes/nothing.stl",
                    "/meshes/C:/Windows/win.ini"):
            assert get(bad)[0] == 404, bad
    assert steady.shared["table_z"] == steady.TABLE_Z == -2.4


def test_calibration_offset():
    from types import SimpleNamespace

    def cal(mids):   # today's calibration files, by their middles; the spread (here +-500) does not matter
        ranges = {j: SimpleNamespace(range_min=m - 500, range_max=m + 500) for j, m in zip(steady.JOINTS, mids)}
        ranges["gripper"] = SimpleNamespace(range_min=1900, range_max=3200)
        return ranges
    leader, follower = cal([2056, 2112.5, 1659, 2035, 2047.5]), cal([2059, 2009.5, 1626, 1990.5, 2047.5])
    offset = steady.calibration_offset(leader, follower)
    assert np.allclose(np.round(offset, 1), [-0.3, 9.1, 2.9, 3.9, 0.0, 0.0]), offset   # follower = leader + offset
    assert abs(offset[1] - 103 * 360 / 4095) < 1e-9
    for broken in ({**leader, "elbow_flex": SimpleNamespace(range_min=float("nan"), range_max=1)},
                   {k: v for k, v in leader.items() if k != "wrist_flex"}, None):
        try:
            steady.calibration_offset(broken, follower)
            raise AssertionError("a broken calibration gave an offset")
        except ValueError:
            pass
    assert steady.LIMIT_LOW[2] == steady.ELBOW_MIN == -64.0 and steady.LIMIT_HIGH[2] == steady.ELBOW_MAX == 118.0


def run_loop(leader_at, seconds, commands=(), start=None, users_file=None):
    """Run steady.main() on a fake clock with a fake leader (leader_at(t) -> six joints) and a follower
    that is exactly where it was last told. commands: (time, line) pairs sent at those times.
    Returns the ticks [(t, six sent joints, why_still, limits)], the console text and /state at the end.
    No port, no arm, no LeRobot: the same fakes as tests/test_standalone_steady_safety.py."""
    import contextlib
    import io
    import sys
    from pathlib import Path
    from types import SimpleNamespace
    from unittest.mock import patch

    from core import tremor
    now, ticks, todo = [0.0], [], sorted(commands)
    told = dict(zip(steady.KEYS, start if start is not None else leader_at(0.0)))

    def send(action):
        told.update(action)
        with steady.lock:
            ticks.append((now[0], np.array([action[k] for k in steady.KEYS]), steady.shared["why_still"], list(steady.shared["limits"])))
        while todo and todo[0][0] <= now[0]:
            reply = steady.command(todo.pop(0)[1])
            ticks[-1] += (reply,)

    ranges = {j: SimpleNamespace(range_min=1000, range_max=3000) for j in steady.JOINTS}   # same middles: offset 0
    follower = SimpleNamespace(connect=lambda: None, send_action=send, get_observation=lambda: dict(told),
                               bus=SimpleNamespace(sync_read=lambda *args, **kwargs: {}, calibration=ranges))
    follower.disconnect = lambda: None
    leader = SimpleNamespace(connect=lambda: None, disconnect=lambda: None, bus=SimpleNamespace(calibration=ranges),
                             get_action=lambda: dict(zip(steady.KEYS, leader_at(now[0]))))

    def make_follower(config):
        follower.config = config
        return follower

    fake_follower = SimpleNamespace(SO101Follower=make_follower,
        SO101FollowerConfig=lambda **kwargs: SimpleNamespace(disable_torque_on_disconnect=True, **kwargs))
    fake_leader = SimpleNamespace(SO101Leader=lambda config: leader, SO101LeaderConfig=lambda **kwargs: kwargs)
    server = lambda *args, **kwargs: SimpleNamespace(serve_forever=lambda: None)
    clock = SimpleNamespace(perf_counter=lambda: now[0], strftime=lambda _: "fake",
                            sleep=lambda seconds: now.__setitem__(0, round(now[0] + 1 / steady.HZ, 6)))
    tip = SimpleNamespace(mm=lambda joints: np.array(joints[:3], float), chain=lambda joints: [], geoms=lambda joints: [])
    console = io.StringIO()
    with tempfile.TemporaryDirectory() as temporary:
        offsets = Path(temporary) / "offsets.json"
        offsets.write_text(json.dumps(dict.fromkeys(steady.KEYS, 0.0)))
        with patch.dict(sys.modules, {"lerobot.robots.so_follower": fake_follower, "lerobot.teleoperators.so_leader": fake_leader}), \
                patch.object(sys, "argv", ["steady", "--yes", "--seconds", str(seconds)]), \
                patch.object(steady, "OFFSETS", offsets), patch.object(steady, "OUT", Path(temporary) / "out"), \
                patch.object(steady, "USERS", users_file or Path(temporary) / "users.json"), \
                patch.object(steady, "read_sessions", lambda *args: []), patch.object(steady, "save_sessions", lambda *args: None), \
                patch.object(steady, "Fingertip", lambda: tip), patch.object(steady, "time", clock), \
                patch.object(steady.socketserver, "ThreadingTCPServer", server), patch.object(steady, "HTTPServer", server), \
                patch.object(steady.threading, "Thread", lambda *args, **kwargs: SimpleNamespace(start=lambda: None)), \
                patch.object(steady, "calibration", tremor.Calibration()), patch.dict(steady.users), \
                patch.dict(steady.shared), contextlib.redirect_stdout(console), \
                patch.dict(steady.state, steady=True, hold=False, cutoff=steady.CUTOFF_HZ, quit=False, gain=1.0, user="default",
                           re_ease=False, neutral=False, release=False):
            steady.main()
            status, _, body = get("/state")
            assert status == 200
            final = json.loads(body)
    return ticks, console.getvalue(), final


def at(ticks, t):
    """The tick at (or just after) time t."""
    return next(tick for tick in ticks if tick[0] >= t - 1e-9)


def no_jumps(ticks):
    """Between any two ticks no joint moved faster than the speed cap (0.5 degree of slack for rounding)."""
    for a, b in zip(ticks, ticks[1:]):
        step = np.abs(b[1] - a[1]).max()
        assert step <= steady.MAX_SPEED * (b[0] - a[0]) + 1e-6, ("a jump faster than the speed cap", a[0], step)


def test_scaling_and_why_still():
    pose = np.array([10.0, -20.0, 20.0, 5.0, 0.0, 43.0])

    def hand(t):
        p = pose.copy()
        if t >= 5:
            p[0] += 10.0                 # a 10 degree reach of the shoulder
        if t >= 13:
            p[2] += 40.0                 # the elbow bends 40 degrees: at gain 3 that asks for 140, past its 118 limit
        return p

    commands = [(8.0, "gain 2"), (12.0, "gain 3"), (20.0, "hold on"), (20.5, "gain 1"), (20.6, "neutral"),
                (20.7, "user Sam"), (20.8, "grip release"), (21.0, "calibrate"), (21.5, "calibrate cancel"), (23.0, "hold off")]
    ticks, console, final = run_loop(hand, 27.0, commands)
    no_jumps(ticks)
    assert abs(at(ticks, 4.0)[1][0] - 10.0) < 0.1 and at(ticks, 4.0)[2] == ""        # the start-up glide is over
    assert at(ticks, 1.0)[2] == "easing"
    assert abs(at(ticks, 7.9)[1][0] - 20.0) < 0.1                                    # gain 1: the arm reaches 10 too
    # gain 2 doubles the excursion about the neutral pose (10): 20 becomes 30, gliding there over EASE_S
    assert at(ticks, 9.0)[2] == "easing" and 22.0 < at(ticks, 9.5)[1][0] < 28.0, at(ticks, 9.5)
    assert abs(at(ticks, 11.9)[1][0] - 30.0) < 0.1 and at(ticks, 11.9)[2] == ""
    # gain 3: the elbow asks for 20 + 3 * 40 = 140, is held at its 118 limit, and that is reported
    assert max(tick[1][2] for tick in ticks) <= steady.ELBOW_MAX + 1e-9
    late = at(ticks, 19.0)
    assert abs(late[1][2] - steady.ELBOW_MAX) < 1e-6 and late[3] == ["elbow_flex"] and late[2] == "limit", late
    assert abs(late[1][0] - 40.0) < 0.1                                              # the shoulder: 10 + 3 * 10
    assert "elbow is at its limit" in console
    # hold wins: gain, neutral, user, grip release and calibrate never clear it, and the arm does not move
    held = [tick for tick in ticks if 20.05 <= tick[0] < 23.0]
    assert all(np.array_equal(tick[1], held[0][1]) for tick in held), "the held arm moved"
    assert all(tick[2] == "holding" for tick in held if tick[0] > 20.2)
    replies = {tick[4]["ok"] for tick in held if len(tick) > 4}
    assert False in replies, "grip release while held must be refused"
    assert "ARM STILL: hold is on" in console
    # out of the hold it glides (no jump) to the new target: gain 1 about the new neutral, user Sam
    assert at(ticks, 23.5)[2] == "easing" and at(ticks, 26.9)[2] in ("", "limit")
    assert final["user"]["name"] == "Sam" and final["gain"] == 1.0 and final["hold"] is False
    assert set(final["grip"]) == {"hold", "squeeze_pct", "held_pct", "claw_pct"} and final["table_z"] == -2.4
    assert [a["id"] for a in final["activities"]] == ["hold_still", "range", "steady_time", "grip_hold"]
    assert final["activities"][0]["last"] is None and final["activities"][1]["last"] is None   # nothing measured yet
    assert final["calibration"]["phase"] == "idle"
    # the follower found folded, its elbow past the limit (3088 ticks, about 128.5 degrees): it is brought
    # inside at the speed cap, never jumped there and never pushed further out
    ticks, _, _ = run_loop(lambda t: np.array([0.0, -90.0, 125.0, 60.0, 0.0, 43.0]), 4.0,
                           start=[0.0, -90.0, 128.5, 60.0, 0.0, 10.0])
    no_jumps(ticks)
    assert max(tick[1][2] for tick in ticks) <= 128.5 and abs(ticks[-1][1][2] - steady.ELBOW_MAX) < 1e-6
    assert ticks[-1][3] == ["elbow_flex"]


def test_calibration():
    from core import tremor

    # on a fake clock, straight to the class: rest 3 s, then 12 s of moving
    cal = tremor.Calibration()
    cal.start(0.0)
    sweep = np.array([20.0, 10.0, 1.0, 50.0, 30.0])     # half ranges: 40, 20, 2 (barely moved), 100, 60
    neutral = np.array([5.0, -10.0, 30.0, 0.0, 0.0])
    result, t = None, 0.0
    while result is None and t < 20:
        if t < 3.0:
            joints, trigger = neutral, 43.0
        else:
            joints = neutral + sweep * math.sin(2 * math.pi * 0.25 * (t - 3.0))
            trigger = 43.0 - 33.0 * max(0.0, math.sin(2 * math.pi * 0.25 * (t - 3.0))) + 47.0 * max(0.0, -math.sin(2 * math.pi * 0.25 * (t - 3.0)))
        if 5.0 < t < 5.1:
            view = cal.view(t)
            assert view["phase"] == "move" and 0 < view["seen"][0] < 1 and 0 < view["seconds_left"] <= 12
        result = cal.feed(t, joints, trigger)
        t = round(t + 0.02, 6)
    assert result is not None and abs(t - 15.02) < 0.05 and cal.phase == "done"
    assert np.allclose(result["neutral"], neutral) and np.allclose(result["range_deg"], 2 * sweep, atol=0.1)
    # gain = target / covered, 1.0 .. 3.0: 90/40, 70/20 -> 3 (capped), elbow barely moved -> 1.0, 80/100 -> 1.0, 120/60
    assert np.allclose(result["gains"], [2.25, 3.0, 1.0, 1.0, 2.0], atol=0.01), result["gains"]
    assert result["trigger"] == {"rest": 43.0, "squeezed": 10.0, "open": 90.0}, result["trigger"]
    assert cal.view(t)["insufficient"] == ["elbow_flex"] and cal.view(t)["seen"][3] == 1.0
    # a person who did not move at all, nor squeeze: every gain stays 1.0, the trigger keeps its defaults,
    # and the state says the calibration was insufficient
    cal = tremor.Calibration()
    cal.start(0.0)
    result = next(r for r in (cal.feed(i / 50, neutral, 43.0) for i in range(1000)) if r)
    assert result["gains"] == [1.0] * 5 and result["trigger"] == {"rest": 43.0, "squeezed": 0.0, "open": 100.0}
    assert cal.view(20.0)["insufficient"] == tremor.ARM + ["trigger squeeze", "trigger open"]
    cal.start(0.0)
    cal.cancel()
    assert cal.view(1.0)["phase"] == "idle" and not cal.running()
    # default is fixed: calibrate it is refused; a named user can be calibrated
    steady.state.update(user="default", hold=False)
    assert steady.command("calibrate")["ok"] is False and not steady.calibration.running()

    # in the loop: the arm is HELD while calibrating, the profile is saved, then the arm glides to the new
    # target (no jump). A hold set before calibrating is still on after it, and a file that cannot be
    # written changes nothing else.
    def person(t):
        p = np.array([0.0, 0.0, 20.0, 0.0, 0.0, 43.0])
        if t >= 5.0:   # 2 s after "calibrate" at 2: the move phase
            s = math.sin(2 * math.pi * 0.25 * (t - 5.0))
            p[:5] += np.array([20.0, 10.0, 1.0, 50.0, 30.0]) * s
            p[5] = 43.0 - 33.0 * max(0.0, s) + 47.0 * max(0.0, -s)
        return p

    with tempfile.TemporaryDirectory() as folder:
        from pathlib import Path
        users_file = Path(folder) / "users.json"
        ticks, console, final = run_loop(person, 22.0, [(1.0, "user Sam"), (1.9, "calibrate")], users_file=users_file)
        frozen = [tick for tick in ticks if 1.95 <= tick[0] < 16.9]
        assert all(np.array_equal(tick[1], frozen[0][1]) for tick in frozen), "the arm moved during calibration"
        assert all(tick[2] == "calibrating" for tick in frozen if tick[0] > 2.1)
        assert at(ticks, 17.5)[2] == "easing"
        no_jumps(ticks)
        saved = json.loads(users_file.read_text())
        assert list(saved) == ["Sam"] and saved["Sam"]["calibrated"] is True and saved["Sam"]["calibrations"] == 1
        assert np.allclose(saved["Sam"]["gains"], [2.25, 3.0, 1.0, 1.0, 2.0], atol=0.05), saved["Sam"]["gains"]
        assert final["user"]["calibrated"] and final["calibration"]["phase"] == "done"
        assert final["calibration"]["insufficient"] == ["elbow_flex"]
        assert final["activities"][1]["last"] is not None and final["activities"][1]["runs"] == 1
        assert not list(Path(folder).glob("*.tmp")), "the temp file was left behind"
        # held before calibrating: still held after it ends; and the users file cannot be written
        ticks, console, final = run_loop(person, 18.0, [(0.5, "hold on"), (1.0, "user Ana"), (1.9, "calibrate")],
                                         users_file=Path(folder) / "no_such_folder" / "users.json")
        assert final["hold"] is True and final["why_still"] == "holding" and final["calibration"]["phase"] == "done"
        late = [tick for tick in ticks if tick[0] >= 0.6]
        assert all(np.array_equal(tick[1], late[0][1]) for tick in late), "the held arm moved"
        assert "could not write" in console and final["user"]["calibrated"]


def test_profiles():
    from pathlib import Path
    from unittest.mock import patch

    good = {"calibrated": True, "gains": [2.0, 1.0, 1.5, 1.0, 3.0], "range_deg": [40, 70, 50, 80, 40],
            "trigger": {"rest": 40, "squeezed": 5, "open": 95}, "neutral": [0, -10, 20, 0, 0], "calibrations": 2, "best_range": 56.0}
    with tempfile.TemporaryDirectory() as folder:
        path = Path(folder) / "users.json"
        assert set(steady.load_users(path)) == {"default"}                          # missing: default only
        # a good profile loads; a bad one (out of range, not finite, missing, wrong type, bad name) is left out
        path.write_text(json.dumps({"Sam": good, "Big": {**good, "gains": [5.0, 1, 1, 1, 1]},
                                    "Nan": {**good, "neutral": [float("nan"), 0, 0, 0, 0]}, "Few": {**good, "gains": [1.0]},
                                    "Odd": {**good, "trigger": {"rest": 140, "squeezed": 0, "open": 100}},
                                    "Typ": {**good, "calibrated": "yes"}, "Hole": {"gains": [1] * 5}, "bad/name": good,
                                    "default": {**good, "gains": [3.0] * 5}}))
        loaded = steady.load_users(path)
        assert set(loaded) == {"default", "Sam"}, set(loaded)
        assert loaded["Sam"]["gains"] == good["gains"] and loaded["default"] == steady.default_profile()
        # a corrupt file: default only, and the file is kept aside so a later save cannot overwrite it
        path.write_text("{not json")
        assert set(steady.load_users(path)) == {"default"} and (Path(folder) / "users.bad").exists()
        unreadable = Path(folder) / "a_folder.json"
        unreadable.mkdir()
        assert set(steady.load_users(unreadable)) == {"default"} and unreadable.is_dir()   # a read error: default, left alone
        # atomic save: through a temp file; a failed replace leaves the old file whole and raises
        steady.save_users({"default": steady.default_profile(), "Sam": loaded["Sam"]}, path)
        assert steady.load_users(path)["Sam"] == loaded["Sam"] and not (Path(folder) / "users.tmp").exists()
        before = path.read_text()
        with patch.object(steady.os, "replace", side_effect=OSError("disk full")):
            try:
                steady.save_users({"default": steady.default_profile()}, path)
                raise AssertionError("a failed save must raise")
            except OSError:
                pass
        assert path.read_text() == before
    # the commands
    steady.state.update(hold=False, gain=1.0, user="default", re_ease=False)
    assert steady.command("gain 2")["gain"] == 2.0 and steady.state["re_ease"] is True
    assert steady.command("gain 9")["gain"] == 3.0 and steady.command("gain 0")["gain"] == 1.0
    assert steady.command("gain nan")["ok"] is False and steady.command("gain x")["ok"] is False and steady.state["gain"] == 1.0
    assert steady.command("user ../../etc")["ok"] is False and steady.command("user " + "a" * 25)["ok"] is False
    assert steady.command("neutral")["ok"] and steady.state["neutral"] is True
    steady.state.update(neutral=False, re_ease=False)
    # activities report measured numbers only
    acts = {a["id"]: a for a in tremor_activities()}
    assert acts["hold_still"]["last"] == 70 and acts["hold_still"]["best"] == 81 and acts["hold_still"]["runs"] == 3
    assert acts["steady_time"]["last"] == 2.0 and acts["steady_time"]["best"] == 5.0 and acts["range"]["last"] is None
    assert acts["grip_hold"]["last"] is None and acts["grip_hold"]["runs"] == 0
    for a in acts.values():
        low = a["detail"].lower()
        assert not any(word in low for word in ("torque", "therapy", "treatment", "diagnos", "improv", "force")), a


def tremor_activities():
    from core import tremor
    past = [{"duration_s": 600.0, "steady_share_pct": 50.0, "tests": [{"score": 81, "tremor_mm": 3.8}, {"score": 60}]}, "junk"]
    return tremor.activities([{"score": 70, "tremor_mm": 6.0}], past, steady.default_profile(), 120.0, 0.0, 0)


if __name__ == "__main__":
    test_steady()
    test_core_tremor()
    test_insights()
    test_grip_hold()
    test_model_and_meshes()
    test_notch()
    test_calibration_offset()
    test_scaling_and_why_still()
    test_calibration()
    test_profiles()
    print("steady ok")
