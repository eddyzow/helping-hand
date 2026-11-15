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

    # the filter: a slow reach passes, a 6 Hz shake is held back
    reach, shake = 20 * np.sin(2 * math.pi * 0.5 * t), 3 * np.sin(2 * math.pi * 6 * t)
    low = steady.LowPass([0.0])
    out = np.array([low.step([a + b], steady.CUTOFF_HZ, dt)[0] for a, b in zip(reach, shake)])
    assert size(out, 0.5) > 17, size(out, 0.5)   # at least 85 % of the reach comes through
    assert size(out, 6.0) < 0.45, size(out, 6.0)  # at least 85 % of the shake is gone

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
    assert abs(low.step([1.0], tremor.CUTOFF_HZ, 0.02)[0] - (1 - math.exp(-2 * math.pi * 2.0 * 0.02)) ** 2) < 1e-12

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
        assert len(parts) == len(tip.meshes) and all(set(p) == {"mesh", "pos", "quat", "rgba"} for p in parts)
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
    assert steady.shared["table_z"] == steady.TABLE_Z == -12.0


if __name__ == "__main__":
    test_steady()
    test_core_tremor()
    test_insights()
    test_grip_hold()
    test_model_and_meshes()
    print("steady ok")
