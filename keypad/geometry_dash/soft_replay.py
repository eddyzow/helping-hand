"""Replay a restart-recorded macro in software only: no arm, no keypad. A diagnostic.

    python keypad\\geometry_dash\\soft_replay.py my_macro_r.csv --offset-ms 0 --runs 3

Run on Windows, then bring Geometry Dash to the front with the level running. Each run presses R
(restart) and then sends the macro's presses as left mouse clicks at the recorded times, accurate to
about a millisecond. If this dies at different places with the same offset, the inconsistency is in
the game or the macro, not in the arm. If it is steady, the arm's path is where to look.
It stops at once if the game stops being the front window.
"""
import argparse
import ctypes
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from tap_pattern import read_pattern  # noqa: E402

user32 = ctypes.windll.user32
LEFT_DOWN, LEFT_UP, KEY_UP = 0x0002, 0x0004, 0x0002


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pattern")
    parser.add_argument("--offset-ms", type=float, default=0, help="plus = every click later")
    parser.add_argument("--runs", type=int, default=1)
    parser.add_argument("--first-taps", type=int)
    parser.add_argument("--restart-key", default="R")
    parser.add_argument("--window", default="Geometry Dash")
    args = parser.parse_args()
    events = read_pattern(Path(__file__).parent / args.pattern)
    if args.first_taps:
        events = events[:2 * args.first_taps]
    game = user32.FindWindowW(None, args.window)
    if not game:
        return print(f"No window titled {args.window!r}") or 1

    print("Bring the game to the front (level running)...", flush=True)
    while user32.GetForegroundWindow() != game:
        time.sleep(0.2)
    for run in range(1, args.runs + 1):
        time.sleep(1.5)
        key = ord(args.restart_key.upper())
        user32.keybd_event(key, 0, 0, 0)
        start = time.perf_counter() + args.offset_ms / 1000
        user32.keybd_event(key, 0, KEY_UP, 0)
        print(f"run {run}: restarted, replaying {len(events) // 2} presses", flush=True)
        down = False
        try:
            for event in events:
                while (left := event.at - (time.perf_counter() - start)) > 0:
                    if user32.GetForegroundWindow() != game:
                        return print("The game is no longer in front: stopped.") or 1
                    time.sleep(min(left, 0.002) if left > 0.003 else 0)  # spin for the last few ms
                user32.mouse_event(LEFT_DOWN if event.down else LEFT_UP, 0, 0, 0, 0)
                down = event.down
        finally:
            if down:
                user32.mouse_event(LEFT_UP, 0, 0, 0, 0)
        print(f"run {run}: done. Note the percent it reached.", flush=True)
        time.sleep(3)
    return 0


if __name__ == "__main__":
    sys.exit(main())
