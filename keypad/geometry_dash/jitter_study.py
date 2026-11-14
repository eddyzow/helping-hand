"""How much timing error does the game forgive? Measured in RobTop's browser Stereo Madness.

    python jitter_study.py --runs 3 --offsets -20 0 20 --press-jitter-ms 5 --release-jitter-ms 2

It reuses Jonathan's browser replay (geo_browser_replay.py) and his MuJoCo-modelled key edges, then
disturbs the times the way the real arm does: a shared offset, a random error on each press and
each release, and a shortest possible hold. Every run is one line in outputs/jitter_study.jsonl:
the settings, whether it cleared the level, and how far it got. No arm and no keypad are used.

The browser game is not the desktop game with Mega Hack: treat the numbers as how tolerant this
kind of macro is, not as a promise about the desktop run.
"""
import argparse
import contextlib
import io
import json
import random
import re
import time
from pathlib import Path
from tempfile import mkdtemp

from playwright.sync_api import sync_playwright

from geo_browser_replay import AUDIO_OBSERVER, DEFAULT_PATTERN, GAME_URL, OUTPUTS, VIEWPORT, replay
from simulate import O3CSettings, simulate
from tap_pattern import KeyEvent, command_times, read_pattern


def disturb(edges, offset_ms, press_jitter_ms, release_jitter_ms, min_hold_ms, rng):
    """The same presses with the arm's kind of error added. Order and alternation are kept."""
    out, last_up = [], -1.0
    for down, up in zip(edges[::2], edges[1::2]):
        d = down.at + (offset_ms + rng.uniform(-press_jitter_ms, press_jitter_ms)) / 1000
        u = up.at + (offset_ms + rng.uniform(-release_jitter_ms, release_jitter_ms)) / 1000
        d = max(d, last_up + 0.010, 0.0)          # never before the previous release
        u = max(u, d + min_hold_ms / 1000)         # the arm cannot let go sooner than this
        out += [KeyEvent(d, True), KeyEvent(u, False)]
        last_up = u
    return out


def one_run(edges, seconds):
    """Returns (cleared, crash_seconds or None, events_sent, log text)."""
    log = io.StringIO()
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(channel="chromium", headless=True,
                                             args=["--autoplay-policy=no-user-gesture-required"])
        try:
            page = browser.new_page(viewport=VIEWPORT)
            page.add_init_script(AUDIO_OBSERVER)
            page.goto(GAME_URL, wait_until="domcontentloaded", timeout=45000)
            page.wait_for_selector("canvas", timeout=45000)
            page.wait_for_timeout(1800)
            page.mouse.click(501, 280)
            OUTPUTS.mkdir(parents=True, exist_ok=True)
            run_dir = Path(mkdtemp(prefix="jitter-", dir=OUTPUTS))
            with contextlib.redirect_stdout(log):
                code = replay(page, edges, 0, 0, seconds, run_dir)
        finally:
            browser.close()
    text = log.getvalue()
    crash = re.search(r"crashed at ([\d.]+)s after (\d+)/", text)
    started = "soundtrack started" in text
    if crash:
        return False, float(crash.group(1)), int(crash.group(2)), text
    return bool(code == 0 and started), None, len(edges) if code == 0 else 0, text


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pattern", type=Path, default=DEFAULT_PATTERN)
    parser.add_argument("--runs", type=int, default=3, help="runs per offset")
    parser.add_argument("--offsets", type=float, nargs="+", default=[12.0],
                        help="ms after the soundtrack cue; Jonathan's clear used 12")
    parser.add_argument("--press-jitter-ms", type=float, default=0)
    parser.add_argument("--release-jitter-ms", type=float, default=0)
    parser.add_argument("--min-hold-ms", type=float, default=0)
    parser.add_argument("--seconds", type=float, default=150)
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument("--out", type=Path, default=OUTPUTS / "jitter_study.jsonl")
    args = parser.parse_args()

    desired = read_pattern(args.pattern)
    edges, _, _ = simulate(command_times(desired, 12, 19), False, O3CSettings())
    if [e.down for e in edges] != [e.down for e in desired]:
        raise ValueError("Simulated switch added or missed key events")
    level_s = desired[-1].at
    rng = random.Random(args.seed)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    for offset in args.offsets:
        for run in range(1, args.runs + 1):
            disturbed = disturb(edges, offset, args.press_jitter_ms, args.release_jitter_ms, args.min_hold_ms, rng)
            began = time.time()
            try:
                cleared, crash_s, sent, text = one_run(disturbed, args.seconds)
                error = "" if "soundtrack started" in text else "the level never started"
            except Exception as err:  # a browser or network failure is a failed measurement, not a crash in the level
                cleared, crash_s, sent, error = False, None, 0, f"{type(err).__name__}: {err}"
            row = {"pattern": args.pattern.name, "offset_ms": offset, "press_jitter_ms": args.press_jitter_ms,
                   "release_jitter_ms": args.release_jitter_ms, "min_hold_ms": args.min_hold_ms, "run": run,
                   "cleared": cleared, "crash_s": crash_s,
                   "percent": 100.0 if cleared else round(100 * crash_s / level_s, 1) if crash_s else None,
                   "events_sent": sent, "error": error, "took_s": round(time.time() - began, 1)}
            with args.out.open("a") as file:
                file.write(json.dumps(row) + "\n")
            print(json.dumps(row), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
