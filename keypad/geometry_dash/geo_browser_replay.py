"""Replay MuJoCo O3C events against the official Geometry Dash browser demo."""

import argparse
import math
from pathlib import Path
from tempfile import mkdtemp
from time import perf_counter, sleep

from playwright.sync_api import sync_playwright


from simulate import O3CSettings, simulate
from tap_pattern import command_times, read_pattern


PROJECT = Path(__file__).resolve().parent
GAME_URL = "https://geometrydash.com/game/index.html"
VIEWPORT = {"width": 1000, "height": 562}
DEFAULT_PATTERN = PROJECT / "stereo_madness_browser.csv"
OUTPUTS = PROJECT / "outputs"


# Observe the official demo's soundtrack and crash effect via standard Web Audio.
# This leaves the game's update loop, collisions, speed and retry behavior intact.
AUDIO_OBSERVER = r"""
(() => {
    const log = [];
    const tracks = new WeakSet();
    const proto = AudioBufferSourceNode.prototype;
    const originalStart = proto.start;
    const originalStop = proto.stop;
    window.replayAudio = log;
    const emit = (type, details = {}) => {
        const cue = { type, at: performance.now(), ...details };
        log.push(cue);
        window.dispatchEvent(new CustomEvent("replay-audio", { detail: cue }));
    };
    proto.start = function (...args) {
        const result = originalStart.apply(this, args);
        const duration = this.buffer?.duration;
        if (duration >= 80 && duration <= 95 && Math.abs(args[0] - this.context.currentTime) < 0.20) {
            tracks.add(this);
            emit("start");
        } else if (duration > 1.80 && duration < 1.90) {
            emit("crash");
        } else if (duration) {
            emit("sound", { duration });
        }
        return result;
    };
    proto.stop = function (...args) {
        if (tracks.has(this)) emit("stop");
        return originalStop.apply(this, args);
    };
})();
"""


def replay(page, events, adjust_ms, retries, seconds, output_dir):
    cursor = 0
    attempt = 0
    epoch = None
    index = 0
    pressed = False
    stop_at = perf_counter() + seconds
    drained_at = None
    last_dispatched = None
    peak_lateness = 0
    try:
        while perf_counter() < stop_at:
            audio, now = page.evaluate("cursor => [replayAudio.slice(cursor), performance.now()]", cursor)
            cursor += len(audio)
            for cue in audio:
                if cue["type"] == "start":
                    attempt += 1
                    if attempt > retries + 1:
                        return 1
                    index, epoch = 0, cue["at"]
                    drained_at, peak_lateness = None, 0
                    last_dispatched = None
                    print(f"Attempt {attempt}: soundtrack started. Replaying from event 1.", flush=True)
                elif cue["type"] == "crash" and epoch is not None:
                    if pressed:
                        page.keyboard.up("Space")
                        pressed = False
                    elapsed = (cue["at"] - epoch) / 1000
                    print(f"Attempt {attempt}: crashed at {elapsed:.3f}s after {index}/{len(events)} events. Last event: {last_dispatched}.", flush=True)
                    page.screenshot(path=output_dir / f"crash-{attempt}.png")
                    epoch, drained_at = None, None
                    if attempt > retries:
                        return 1
            if epoch is not None and index < len(events):
                event = events[index]
                deadline = epoch + event.at * 1000 + adjust_ms
                if now >= deadline:
                    peak_lateness = max(peak_lateness, now - deadline)
                    if event.down:
                        page.keyboard.down("Space")
                        if index == 0:
                            print(f"First press {(now - epoch):.1f} ms after the soundtrack cue.", flush=True)
                    else:
                        page.keyboard.up("Space")
                    pressed = event.down
                    last_dispatched = (index + 1, event.at, "down" if event.down else "up")
                    index += 1
                    if index == len(events):
                        drained_at = now
                        print(f"Delivered all {index} events. Maximum dispatch delay: {peak_lateness:.1f} ms.", flush=True)
                else:
                    sleep(max(0.0, min(0.008, (deadline - now - 2) / 1000)))
            elif drained_at is not None and now - drained_at > 6000:
                path = output_dir / "end-screen.png"
                page.screenshot(path=path)
                print(f"Check the game result in {path}.", flush=True)
                return 0
            else:
                sleep(0.008)
        path = output_dir / "timeout.png"
        page.screenshot(path=path)
        print(f"Reached the time limit after {attempt} attempts. Screenshot: {path}.", flush=True)
        return 1
    finally:
        if pressed:
            page.keyboard.up("Space")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seconds", type=float, default=190)
    parser.add_argument("--retries", type=int, default=1)
    parser.add_argument("--visible", action="store_true")
    parser.add_argument("--pattern", type=Path, default=DEFAULT_PATTERN)
    parser.add_argument("--offset-ms", type=float, default=12)
    parser.add_argument("--output-dir", type=Path, default=OUTPUTS)
    args = parser.parse_args()
    if args.retries < 0 or not math.isfinite(args.seconds) or args.seconds <= 0:
        parser.error("Use nonnegative retries and a positive finite time limit.")
    if not math.isfinite(args.offset_ms):
        parser.error("The start offset must be finite.")
    desired = read_pattern(args.pattern)
    edges, _, _ = simulate(command_times(desired, 12, 19), False, O3CSettings())
    if [edge.down for edge in edges] != [event.down for event in desired]:
        raise ValueError("Simulated switch added or missed key events")
    if edges[0].at * 1000 + args.offset_ms < 0:
        parser.error("The first input would be before the soundtrack cue.")
    args.output_dir.mkdir(parents=True, exist_ok=True)
    run_dir = Path(mkdtemp(prefix="browser-replay-", dir=args.output_dir))
    print(f"Loaded {len(edges)} modeled O3C edges.", flush=True)
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(
            channel="chromium", headless=not args.visible,
            args=["--autoplay-policy=no-user-gesture-required"],
        )
        try:
            page = browser.new_page(viewport=VIEWPORT)
            page.add_init_script(AUDIO_OBSERVER)
            page.goto(GAME_URL, wait_until="domcontentloaded", timeout=45000)
            page.wait_for_selector("canvas", timeout=45000)
            page.wait_for_timeout(1800)
            page.mouse.click(501, 280)
            return replay(page, edges, args.offset_ms, args.retries, args.seconds, run_dir)
        finally:
            browser.close()


if __name__ == "__main__":
    raise SystemExit(main())
