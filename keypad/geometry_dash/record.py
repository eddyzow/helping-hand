"""Record Space press and release timings from a manual Geometry Dash run."""

import argparse
import csv
from pathlib import Path
from time import perf_counter_ns

from pynput import keyboard


class Recording:
    def __init__(self, restart: str):
        self.restart = restart
        self.started_at = None
        self.space_down = False
        self.restart_down = False
        self.events = []

    def on_press(self, key):
        now = perf_counter_ns()
        if key == keyboard.Key.f8:
            return False

        if getattr(key, "char", None) == self.restart and not self.restart_down:
            self.restart_down = True
            self.started_at = now
            self.events.clear()
            if self.space_down:
                self.events.append((0, "down"))
        elif key == keyboard.Key.space and not self.space_down:
            self.space_down = True
            if self.started_at is not None:
                self.events.append((now - self.started_at, "down"))

    def on_release(self, key):
        now = perf_counter_ns()
        if getattr(key, "char", None) == self.restart:
            self.restart_down = False
        elif key == keyboard.Key.space and self.space_down:
            self.space_down = False
            if self.started_at is not None:
                self.events.append((now - self.started_at, "up"))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    parser.add_argument("--restart", default="r", help="The letter bound to Restart in Geometry Dash")
    args = parser.parse_args()
    if len(args.restart) != 1 or args.restart not in "abcdefghijklmnopqrstuvwxyz":
        parser.error("--restart must be one lowercase letter")
    if args.output.exists():
        parser.error(f"{args.output} already exists. Choose a new filename.")

    recording = Recording(args.restart)
    print(f"Focus the game and press {args.restart.upper()} to restart and begin recording.", flush=True)
    print("Use Space to jump. Release Space and press F8 when the attempt is over.", flush=True)
    try:
        with keyboard.Listener(on_press=recording.on_press, on_release=recording.on_release) as listener:
            listener.join()
    except KeyboardInterrupt:
        print("Recording canceled.")
        return 1

    if not recording.events or recording.events[-1][1] != "up":
        print("The recording needs at least one complete press and release.")
        return 1
    try:
        with args.output.open("x", encoding="utf-8", newline="") as file:
            writer = csv.writer(file)
            writer.writerow(["time_ms", "state"])
            writer.writerows((f"{elapsed_ns / 1_000_000:.6f}", state) for elapsed_ns, state in recording.events)
    except OSError as error:
        print(f"Could not save the recording: {error}")
        return 1
    print(f"Saved {len(recording.events) // 2} presses and releases to {args.output}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
