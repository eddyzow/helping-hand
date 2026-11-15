"""Play a recorded macro on the real arm, with Windows keeping the time. Run on Windows:

    python keypad/geometry_dash/arm_play.py my_macro_arm.csv --runs 5

The dispatcher must be running and the level open. Each attempt: the arm waits over the jump key
(skill gd_remote), this script presses R to restart the level, then sends "tap press" /
"tap release" at the recorded instants, less the time the arm needs to carry each one out. The
clock inside WSL was measured unsteady (4 to 6% fast), so no timing is left to that side.

It also watches what happened, on the same clock: when the click really reached Windows
(the keypad turns the jump key into a left click), and when the level restarted (the white
"ATTEMPT n" caption = a death). After a death the arm stays over the key and the next attempt
starts at once. Each run goes to outputs/arm_play.jsonl; the last 1.5 s before a death is saved
as a picture.
"""
import argparse
import collections
import ctypes
import json
import socket
import sys
import threading
import time
from ctypes import wintypes
from pathlib import Path

import numpy as np

from tap_pattern import read_pattern

PORT = 8765
OUT = Path(__file__).with_name("outputs")
user32, gdi32 = ctypes.windll.user32, ctypes.windll.gdi32
SW, SH = 640, 400  # size of the small whole-window frames kept for the moments before a death


class BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [("biSize", wintypes.DWORD), ("biWidth", wintypes.LONG), ("biHeight", wintypes.LONG),
                ("biPlanes", wintypes.WORD), ("biBitCount", wintypes.WORD), ("biCompression", wintypes.DWORD),
                ("biSizeImage", wintypes.DWORD), ("biXPelsPerMeter", wintypes.LONG),
                ("biYPelsPerMeter", wintypes.LONG), ("biClrUsed", wintypes.DWORD), ("biClrImportant", wintypes.DWORD)]


class Screen:
    """Light copies of the game window: the caption strip, and a small whole-window frame."""

    def __init__(self, game):
        H = wintypes.HANDLE
        user32.GetDC.restype = gdi32.CreateCompatibleDC.restype = gdi32.CreateCompatibleBitmap.restype = H
        gdi32.CreateCompatibleDC.argtypes = [H]
        gdi32.CreateCompatibleBitmap.argtypes = [H, ctypes.c_int, ctypes.c_int]
        gdi32.SelectObject.argtypes = [H, H]
        gdi32.SetStretchBltMode.argtypes = [H, ctypes.c_int]
        gdi32.StretchBlt.argtypes = [H] + [ctypes.c_int] * 4 + [H] + [ctypes.c_int] * 4 + [wintypes.DWORD]
        gdi32.GetDIBits.argtypes = [H, H, wintypes.UINT, wintypes.UINT, ctypes.c_void_p, ctypes.c_void_p, wintypes.UINT]
        rect = wintypes.RECT()
        user32.GetWindowRect(game, ctypes.byref(rect))
        width, height = rect.right - rect.left, rect.bottom - rect.top
        self.window = (rect.left, rect.top, width, height)
        self.strip = (rect.left + int(width * 0.05), rect.top + int(height * 0.215), int(width * 0.90), int(height * 0.07))
        self.screen = user32.GetDC(None)
        self.strip_dc, self.strip_bmp, self.strip_info, self.strip_buf = self._surface(*self.strip[2:])
        self.small_dc, self.small_bmp, self.small_info, self.small_buf = self._surface(SW, SH)

    def _surface(self, w, h):
        dc = gdi32.CreateCompatibleDC(self.screen)
        bmp = gdi32.CreateCompatibleBitmap(self.screen, w, h)
        gdi32.SelectObject(dc, bmp)
        gdi32.SetStretchBltMode(dc, 3)
        return dc, bmp, BITMAPINFOHEADER(ctypes.sizeof(BITMAPINFOHEADER), w, -h, 1, 32, 0, 0, 0, 0, 0, 0), \
            ctypes.create_string_buffer(w * h * 4)

    def white(self) -> int:
        """How many sampled pixels in the caption strip are pure white."""
        x, y, w, h = self.strip
        gdi32.StretchBlt(self.strip_dc, 0, 0, w, h, self.screen, x, y, w, h, 0x00CC0020)
        gdi32.GetDIBits(self.strip_dc, self.strip_bmp, 0, h, self.strip_buf, ctypes.byref(self.strip_info), 0)
        pixels = np.frombuffer(self.strip_buf, np.uint8).reshape(-1, 4)[::7, :3]
        return int((pixels.min(axis=1) > 245).sum())

    def frame(self) -> bytes:
        gdi32.StretchBlt(self.small_dc, 0, 0, SW, SH, self.screen, *self.window, 0x00CC0020)
        gdi32.GetDIBits(self.small_dc, self.small_bmp, 0, SH, self.small_buf, ctypes.byref(self.small_info), 0)
        return self.small_buf.raw


def save_frames(frames, path) -> None:
    from PIL import Image, ImageDraw
    cols = 5
    sheet = Image.new("RGB", (cols * SW, -(-len(frames) // cols) * SH))
    for i, (t, raw) in enumerate(frames):
        tile = Image.frombuffer("RGB", (SW, SH), raw, "raw", "BGRX", 0, 1).copy()
        draw = ImageDraw.Draw(tile)
        draw.rectangle((0, SH - 22, 150, SH), fill="black")
        draw.text((4, SH - 18), f"{t:6.2f} s after restart", fill="yellow")
        sheet.paste(tile, (i % cols * SW, i // cols * SH))
    sheet.save(path, quality=85)


def ask(line: str):
    with socket.create_connection(("127.0.0.1", PORT), timeout=3) as s:
        s.sendall((line + "\n").encode())
        return json.loads(s.makefile().readline())


def focus(game) -> bool:
    for _ in range(10):
        if user32.GetForegroundWindow() == game:
            return True
        user32.keybd_event(0x12, 0, 0, 0)  # a tap of Alt lets Windows hand over the foreground
        user32.keybd_event(0x12, 0, 2, 0)
        user32.ShowWindow(game, 9)
        user32.SetForegroundWindow(game)
        time.sleep(0.4)
    return False


def match(wanted, seen, window=0.08):
    """For each wanted (time, down): how late the same change was seen, in ms, or None if never."""
    errors = []
    for at, down in wanted:
        near = [t - at for t, d in seen if d == down and abs(t - at) <= window]
        errors.append(round(min(near, key=abs) * 1000, 1) if near else None)
    return errors


def attempt(game, screen, taps, events, leads, offset, threshold, fix, start=0.0, mark=None):
    """One run from a restart. Returns a dict: survived seconds, why it ended, and the timing seen.
    mark: seconds after the restart at which to place a practice-mode checkpoint (the Z key).
    start: the restart begins at a checkpoint placed at that time, so only the later taps are played;
    a checkpoint restart shows no caption, so the part is played to its end and every frame kept."""
    first = next(i for i, e in enumerate(events) if e.at > start and e.down)
    events, fix = [type(e)(e.at - start, e.down) for e in events[first:]], fix[first:]
    def tap(word):
        taps.sendall(f"tap {word}\n".encode())
        try:
            taps.recv(4096)  # replies are not needed; just keep the buffer empty
        except BlockingIOError:
            pass

    clock = time.perf_counter
    t0, restarted = clock() + 0.3, False  # R goes in 0.3 s, so a tap wanted right after it can start before it
    plan = [[e.at + offset - leads[e.down] - f / 1000, e.at + offset, e.down] for e, f in zip(events, fix)]
    seen, sent, recent = [], [], collections.deque(maxlen=60 if start else 15)
    watching = [True]

    def watch():  # its own thread: a screen copy in the main loop must not delay the time of a click
        was = False
        while watching[0]:
            down = bool(user32.GetAsyncKeyState(1) & 0x8000)  # the left button, as Windows has it now
            if down != was:
                seen.append((clock() - t0, down))
                was = down
            time.sleep(0.0005)

    threading.Thread(target=watch, daemon=True).start()
    read = 0
    was_down, streak, caption, next_look, looks, i = False, 0, True, 0.0, 0, 0
    ended, end_at = "part played" if start else "finished", plan[-1][1] + (1.5 if start else 3.0)
    while (now := clock() - t0) < end_at:
        while read < len(seen):
            at, down = seen[read]
            read += 1
            # Keep the HOLD as long as it was recorded: if this press landed early or late, move its
            # release by the same amount (in the ship parts the length of a hold is what steers).
            if down and 0 < i < len(plan) and not plan[i][2] and abs(late := at - plan[i - 1][1]) < 0.08:
                room = plan[i + 1][0] - 0.06 - plan[i][0] if i + 1 < len(plan) else late
                late = min(late, max(room, 0.0))
                plan[i][0] += late
                plan[i][1] += late
        if not restarted and now >= 0:
            user32.keybd_event(0x52, 0, 0, 0)  # R: Mega Hack's restart level
            user32.keybd_event(0x52, 0, 2, 0)
            restarted = True
        if mark and now >= mark:
            user32.keybd_event(0x5A, 0, 0, 0)  # Z: place a checkpoint
            user32.keybd_event(0x5A, 0, 2, 0)
            mark = None
        if i < len(plan) and now >= plan[i][0]:
            tap("press" if plan[i][2] else "release")
            sent.append(now)
            i += 1
            continue
        wait = plan[i][0] - now if i < len(plan) else 1.0
        if wait > 0.04 and now >= next_look:  # look at the screen only when no tap is near
            next_look, looks = now + 0.05, looks + 1
            if user32.GetForegroundWindow() != game:
                ended = "game lost focus"
                break
            streak = streak + 1 if screen.white() > threshold else 0
            shown = streak >= 3
            if shown and not caption and now > 1.5:  # the caption came back: the level restarted
                ended = "died"
                break
            caption = shown
            if looks % (5 if start else 2) == 0:
                recent.append((now, screen.frame()))
        elif wait > 0.004:
            time.sleep(0.001)
    died_at = clock() - t0
    if ended == "died" and not start and died_at > plan[-1][1] + 1.0:
        ended = "completed"  # the white flash at the end of the level, not a restart caption
    watching[0] = False
    tap("release")
    wanted = [(at, d) for _, at, d in plan[:i]]
    errors = match(wanted, seen)
    presses = [e for e, (_, d) in zip(errors, wanted) if d]
    releases = [e for e, (_, d) in zip(errors, wanted) if not d]

    def spread(values):
        got = sorted(v for v in values if v is not None)
        return {"n": len(values), "missed": len(values) - len(got),
                "min": got[0] if got else None, "median": got[len(got) // 2] if got else None,
                "max": got[-1] if got else None}

    return {"survived_s": round(died_at - (0.15 if ended == "died" else 0), 2), "ended": ended,
            "taps_sent": i, "press_late_ms": spread(presses), "release_late_ms": spread(releases),
            # how much longer each hold was than the recorded one
            "hold_long_ms": spread([round((plan[j + 1][1] - plan[j][1] - events[j + 1].at + events[j].at) * 1000
                                          + errors[j + 1] - errors[j], 1)
                                    for j in range(0, i - 1, 2) if errors[j] is not None and errors[j + 1] is not None]),
            "late_ms": errors, "first_tap": first,
            "last": [{"at": round(at, 3), "down": d, "late_ms": e, "sent_late_ms": round((s - c) * 1000, 1)}
                     for (c, at, d), e, s in list(zip(plan, errors, sent))[-8:]],
            "frames": list(recent)}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pattern")
    parser.add_argument("--runs", type=int, default=1)
    parser.add_argument("--press-lead-ms", type=float, default=89, help="how long the arm takes to press")
    parser.add_argument("--release-lead-ms", type=float, default=96, help="how long the arm takes to release")
    parser.add_argument("--offset-ms", type=float, default=0, help="shift every tap; positive is later")
    parser.add_argument("--first", type=int, help="only the first N presses, for a test")
    parser.add_argument("--practice", type=float, help="practice mode: place a checkpoint this many seconds in, "
                        "then train only the part after it")
    parser.add_argument("--resume", action="store_true", help="the practice checkpoint is already placed")
    parser.add_argument("--learn", type=float, default=0.3, help="share of each tap's lateness to correct next run")
    parser.add_argument("--no-learn", action="store_true")
    parser.add_argument("--threshold", type=int, default=3000, help="white pixels that mean a caption")
    args = parser.parse_args()
    user32.SetProcessDPIAware()
    game = user32.FindWindowW(None, "Geometry Dash")
    if not game:
        sys.exit("Geometry Dash window not found")
    path = Path(args.pattern)
    events = read_pattern(path if path.exists() else Path(__file__).with_name(args.pattern))
    if args.first:
        events = events[:args.first * 2]
    leads = {True: args.press_lead_ms / 1000, False: args.release_lead_ms / 1000}
    # Some taps come out early or late the same way every run (the arm answers differently after a
    # long hold than after a short one). So each tap carries its own learned correction, in ms: after
    # every run a part of the lateness that was seen is added to it. --no-learn leaves the file alone.
    fix_path = OUT / (path.stem + ".fix.json")
    fix = json.loads(fix_path.read_text()) if fix_path.exists() else []
    fix = (fix + [0.0] * len(events))[:len(events)]
    screen = Screen(game)
    OUT.mkdir(exist_ok=True)
    for _ in range(100):  # an earlier run may still be taking the arm away from the key
        if not ask("status")["busy"]:
            break
        time.sleep(0.2)
    reply = ask("run gd_remote")
    if not reply.get("ok"):
        sys.exit(f"dispatcher refused: {reply}")
    taps = socket.create_connection(("127.0.0.1", PORT), timeout=3)
    taps.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
    taps.setblocking(False)
    try:
        began = time.perf_counter()
        while not ask("remote")["ok"]:
            if time.perf_counter() - began > 15 or not ask("status")["busy"]:
                sys.exit(f"the arm did not reach the key: {ask('status')}")
            time.sleep(0.1)
        at_checkpoint = args.resume
        for run in range(1, args.runs + 1):
            if not focus(game):
                sys.exit("could not bring the game to the front")
            time.sleep(0.3)
            result = attempt(game, screen, taps, events, leads, args.offset_ms / 1000, args.threshold, fix,
                             start=args.practice if at_checkpoint else 0.0, mark=args.practice)
            part = at_checkpoint
            at_checkpoint = at_checkpoint or bool(args.practice and result["survived_s"] > args.practice + 0.3)
            if not args.no_learn:
                for i, late in enumerate(result["late_ms"]):
                    if late is not None:
                        i += result["first_tap"]
                        fix[i] = round(max(-40.0, min(40.0, fix[i] + args.learn * max(-20.0, min(20.0, late)))), 2)
                fix_path.write_text(json.dumps(fix))
            frames = result.pop("frames")
            row = {"at": time.strftime("%H:%M:%S"), "run": run, "pattern": path.name, "offset_ms": args.offset_ms,
                   "press_lead_ms": args.press_lead_ms, "release_lead_ms": args.release_lead_ms,
                   "percent_est": round(result["survived_s"] * 1.163, 1), **result}
            if (result["ended"] == "died" or part) and frames:
                row["frames"] = f"{'part' if part else 'death'}_{time.strftime('%H%M%S')}.jpg"
                save_frames(frames, OUT / row["frames"])
            with (OUT / "arm_play.jsonl").open("a") as file:
                file.write(json.dumps(row) + "\n")
            print(json.dumps({k: v for k, v in row.items() if k not in ("last", "late_ms")}), flush=True)
            if result["ended"] in ("game lost focus", "completed") or (result["ended"] == "finished" and not at_checkpoint):
                break
            time.sleep(1.2)  # let the death animation finish before the next restart
    finally:
        taps.setblocking(True)
        taps.sendall(b"tap end\n")
        taps.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
