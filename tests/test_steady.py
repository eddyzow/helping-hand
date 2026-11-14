"""Run with python -m tests.test_steady; synthetic signals only, no arm, no serial port."""
import math

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
    assert steady.command("key down")["hold"] is True and steady.command("hold off")["hold"] is False
    assert steady.command("stop")["hold"] is True
    assert steady.command("cutoff 99")["cutoff"] == 8.0 and steady.command("cutoff x")["ok"] is False
    assert steady.command("dance")["ok"] is False


if __name__ == "__main__":
    test_steady()
    print("steady ok")
