"""Record Space timings from one attempt in RobTop's Stereo Madness browser demo."""

import argparse
import csv
from pathlib import Path

from playwright.sync_api import Error, sync_playwright

from geo_browser_replay import AUDIO_OBSERVER, GAME_URL, OUTPUTS, VIEWPORT


RECORDER = r"""
(() => {
    let epoch = null;
    let edges = [];
    let spaceDown = false;
    let attempt = 0;
    const initMessage = "Click Play. Use Space. Press F8 on the Level Complete screen.";
    let message = initMessage;
    window.stereoRecording = null;

    function status(text) {
        message = text;
        const banner = document.getElementById("replay-recorder-status");
        if (banner) banner.textContent = text;
    }

    document.addEventListener("DOMContentLoaded", () => {
        const banner = document.createElement("div");
        banner.id = "replay-recorder-status";
        banner.style.cssText = [
            "position:fixed", "z-index:100000", "top:6px", "left:50%",
            "transform:translateX(-50%)", "padding:6px 10px", "background:#18283d",
            "color:#fff", "font:14px system-ui", "border-radius:4px",
            "pointer-events:none", "white-space:nowrap",
        ].join(";");
        banner.textContent = message;
        document.body.appendChild(banner);
    }, { once: true });

    window.addEventListener("replay-audio", ({ detail: { type, at } }) => {
        if (window.stereoRecording) return;
        if (type === "start") {
            epoch = at;
            edges = spaceDown ? [[0, "down"]] : [];
            status(`Recording attempt ${++attempt}. Press F8 after Level Complete.`);
        } else if (type === "crash") {
            epoch = null;
            edges = [];
            status("Attempt discarded. The next attempt will record automatically.");
        }
    });

    window.addEventListener("keydown", event => {
        if (event.code === "F8" && !event.repeat) {
            event.preventDefault();
            if (epoch === null || !edges.length || spaceDown) {
                status("Play a clean attempt and release Space before pressing F8.");
                return;
            }
            window.stereoRecording = edges.slice();
            status("Recording captured.");
        } else if (event.code === "Space" && !spaceDown) {
            spaceDown = true;
            if (epoch !== null && !window.stereoRecording) edges.push([performance.now() - epoch, "down"]);
        }
    }, { capture: true });

    window.addEventListener("keyup", event => {
        if (event.code !== "Space" || !spaceDown) return;
        spaceDown = false;
        if (epoch !== null && !window.stereoRecording) edges.push([performance.now() - epoch, "up"]);
    }, { capture: true });

    window.addEventListener("blur", () => {
        if (!spaceDown) return;
        spaceDown = false;
        if (epoch !== null) {
            epoch = null;
            edges = [];
            status("Focus changed while Space was held. Start a fresh attempt.");
        }
    });
})();
"""


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path, nargs="?", default=OUTPUTS / "my_stereo_madness_browser.csv")
    args = parser.parse_args()
    if args.output.exists():
        parser.error(f"File already exists: {args.output}. Choose a new output path.")
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(channel="chromium", headless=False)
        page = browser.new_page(viewport=VIEWPORT)
        page.add_init_script(AUDIO_OBSERVER + "\n" + RECORDER)
        page.goto(GAME_URL, wait_until="domcontentloaded", timeout=45000)
        page.bring_to_front()
        print("Browser recorder ready. Click Play, beat Stereo Madness with Space, then press F8.", flush=True)
        while not page.is_closed():
            try:
                edges = page.evaluate("window.stereoRecording")
            except Error:
                if page.is_closed():
                    break
                raise
            if edges:
                args.output.parent.mkdir(parents=True, exist_ok=True)
                with args.output.open("x", encoding="utf-8", newline="") as file:
                    writer = csv.writer(file)
                    writer.writerow(["time_ms", "state"])
                    writer.writerows((f"{at:.6f}", state) for at, state in edges)
                print(f"Saved {len(edges) // 2} presses and releases to {args.output}.", flush=True)
                print("The game will stay open until you close its tab.", flush=True)
                page.wait_for_event("close", timeout=0)
                return 0
            page.wait_for_timeout(250)
    print("Browser closed before a recording was saved.", flush=True)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
