"""Run with python -m tests.test_steady; synthetic signals only, no arm, no serial port."""
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
    flat = tremor.insights([[i, 5.0, 0.5, 0.0, 6.0] for i in range(60)])
    assert [o["id"] for o in flat] == ["size", "rate", "change"] and flat[2]["value"] == "about the same"
    for o in out + flat:  # the wording rules: observations only, and grip effort is never called a force
        low = o["text"].lower()
        assert not any(word in low for word in ("torque", "therapy", "treatment", "diagnos", "improv")), o
        assert "force" not in low or "not a measured force" in low, o
    # RobTop's voice script reports to the dashboard through the same command port
    assert steady.command('voice {"heard": "hold this", "said": "I have it"}')["ok"]
    assert steady.shared["voice"]["heard"] == "hold this" and steady.command("voice nonsense")["ok"] is False


def test_grip_latch():
    from core import tremor

    def play(latch, trigger_at, seconds, start=0.0, hz=50):
        """Feed the latch a trigger signal; returns the claw target at each tick."""
        return [latch.step(start + i / hz, trigger_at(i / hz)) for i in range(int(seconds * hz))]

    latch = tremor.GripLatch(closed_to=7.0)
    assert set(play(latch, lambda t: 80.0, 1.0)) == {60.0} and not latch.closed          # an open hand: the claw stays open
    out = play(latch, lambda t: 10.0 if 0.5 < t < 1.2 else 80.0, 3.0, start=1.0)             # one squeeze, then let go
    assert out[-1] == 7.0 and latch.closed, "the claw must stay closed after the hand lets go"
    assert out.count(7.0) > 100 and out[30] == 60.0                                          # it closed only after the dwell
    out = play(latch, lambda t: 10.0 if 0.5 < t < 1.2 else 80.0, 3.0, start=4.0)             # the next squeeze opens it
    assert out[-1] == 60.0 and not latch.closed
    # a 6 Hz tremor on the trigger around the threshold must not click it (each dip lasts under 0.1 s)
    latch = tremor.GripLatch(closed_to=7.0)
    out = play(latch, lambda t: 28.0 + 12.0 * math.sin(2 * math.pi * 6 * t), 5.0)
    assert set(out) == {60.0} and not latch.closed, "a tremor toggled the latch"
    # a squeeze that is held does not toggle twice, and a hand hovering half-open does not re-arm it
    latch = tremor.GripLatch(closed_to=7.0)
    out = play(latch, lambda t: 10.0, 3.0)
    assert latch.closed and out[-1] == 7.0
    play(latch, lambda t: 35.0, 2.0, start=3.0)   # between the two thresholds: not released yet
    play(latch, lambda t: 10.0, 1.0, start=5.0)
    assert latch.closed, "a half release must not allow a second toggle"
    # the command
    steady.state.update(latch=False)
    assert steady.command("latch on")["latch"] is True and steady.command("latch")["latch"] is False
    assert steady.command("latch maybe")["ok"] is False


if __name__ == "__main__":
    test_steady()
    test_core_tremor()
    test_insights()
    test_grip_latch()
    print("steady ok")
