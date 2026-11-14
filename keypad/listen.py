"""SayoDevice keys -> dispatcher commands. Run on Windows (not WSL): python keypad\\listen.py

The keypad needs no configuring. The first run asks you to press its three keys once (wave,
jump, stop) and saves what they send to keypad/keys.json. After that:
    wave key  -> the arm waves
    jump key  -> a left mouse click while the Geometry Dash window is in front (jump, or Play on the
                 level page), an Up arrow anywhere else. This is the key the arm taps.
    stop key  -> the arm stops at once. Test it at the start of every session.
Geometry Dash sync: when the geometry_dash skill is ready, this presses R (restart) in the game
window and tells the arm to start at that same instant. If the game is not focused, press R yourself.
Only the SayoDevice triggers these (matched by USB id), and it works whichever window has focus.
Needs the dispatcher running for wave and stop. No extra packages.

    python keypad\\listen.py --learn    # relearn the three keys, then quit
    python keypad\\listen.py --record my_macro
        Record your own run. Inside the level, press R (restart): that is time zero. Play with the
        jump key, then press the stop key. Dying and pressing R again starts the recording over.
        Replay: run geometry_dash {"pattern": "my_macro.csv"}  (the listener presses R for the arm)
"""
import ctypes
import json
import os
import socket
import sys
import threading
import time
from ctypes import wintypes
from pathlib import Path

PORT = int(os.environ.get("BUDDY_PORT", "8765"))
DEVICE = os.environ.get("KEYPAD_ID", "VID_8089").upper()  # SayoDevice USB vendor id; "" = any keyboard
KEYS_FILE = Path(__file__).with_name("keys.json")
ROLES = ["wave", "jump", "stop"]
VK_UP, KEYUP, WM_INPUT, WM_TIMER = 0x26, 0x0002, 0x00FF, 0x0113
VK_RESTART = ord(os.environ.get("GD_RESTART_KEY", "R").upper())  # the game's restart key
GAME_TITLE = os.environ.get("GD_WINDOW", "Geometry Dash")

user32 = ctypes.WinDLL("user32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
WNDPROC = ctypes.WINFUNCTYPE(ctypes.c_ssize_t, wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM)
user32.DefWindowProcW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
user32.DefWindowProcW.restype = ctypes.c_ssize_t
user32.CreateWindowExW.argtypes = [wintypes.DWORD, wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.DWORD] + \
    [ctypes.c_int] * 4 + [wintypes.HWND, wintypes.HANDLE, wintypes.HANDLE, ctypes.c_void_p]
user32.CreateWindowExW.restype = wintypes.HWND
user32.GetRawInputData.argtypes = [wintypes.HANDLE, wintypes.UINT, ctypes.c_void_p,
                                   ctypes.POINTER(wintypes.UINT), wintypes.UINT]
user32.GetRawInputDeviceInfoW.argtypes = [wintypes.HANDLE, wintypes.UINT, ctypes.c_void_p,
                                          ctypes.POINTER(wintypes.UINT)]
kernel32.GetModuleHandleW.restype = wintypes.HANDLE


class WNDCLASS(ctypes.Structure):
    _fields_ = [("style", wintypes.UINT), ("lpfnWndProc", WNDPROC), ("cbClsExtra", ctypes.c_int),
                ("cbWndExtra", ctypes.c_int), ("hInstance", wintypes.HANDLE), ("hIcon", wintypes.HANDLE),
                ("hCursor", wintypes.HANDLE), ("hbrBackground", wintypes.HANDLE),
                ("lpszMenuName", wintypes.LPCWSTR), ("lpszClassName", wintypes.LPCWSTR)]


class RAWINPUTDEVICE(ctypes.Structure):
    _fields_ = [("usUsagePage", wintypes.USHORT), ("usUsage", wintypes.USHORT),
                ("dwFlags", wintypes.DWORD), ("hwndTarget", wintypes.HWND)]


class RAWKEYBOARD(ctypes.Structure):  # RAWINPUTHEADER followed by RAWKEYBOARD
    _fields_ = [("dwType", wintypes.DWORD), ("dwSize", wintypes.DWORD), ("hDevice", wintypes.HANDLE),
                ("wParam", wintypes.WPARAM), ("MakeCode", wintypes.USHORT), ("Flags", wintypes.USHORT),
                ("Reserved", wintypes.USHORT), ("VKey", wintypes.USHORT), ("Message", wintypes.UINT),
                ("ExtraInformation", wintypes.ULONG)]


HEADER_SIZE = RAWKEYBOARD.MakeCode.offset


def send(command: str, timeout: float = 1) -> str:
    try:
        with socket.create_connection(("127.0.0.1", PORT), timeout=timeout) as s:
            s.sendall((command + "\n").encode())
            return s.makefile().readline().strip()
    except OSError as err:
        return f"dispatcher not reachable: {err}"


_open = []  # the one connection kept open for key events


def notify(command: str, retry: bool = True) -> None:
    """Report a key event on a connection that stays open. Opening a new connection for every key
    press took a few milliseconds that varied each time, and the arm's clock starts from this event.
    A key state may be sent again after a failed send, because sending it twice changes nothing.
    A cue may not (retry=False): it might have arrived the first time, and a second one would
    restart the replay."""
    if _open:
        # Look at the kept connection before sending. A send into a connection the dispatcher has
        # closed is lost without any error, and the first key event after every restart used to
        # vanish that way. Nothing has been sent yet here, so replacing the connection is not a retry.
        try:
            if _open[0].recv(4096) == b"":
                raise ConnectionResetError("the dispatcher closed the connection")
        except BlockingIOError:
            pass  # nothing waiting: the connection is alive
        except OSError:
            _open.pop().close()
    for _ in range(2 if retry else 1):  # a second try only if the kept connection had gone stale
        had = bool(_open)
        try:
            if not _open:
                s = socket.create_connection(("127.0.0.1", PORT), timeout=0.2)
                s.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
                s.setblocking(False)
                _open.append(s)
            _open[0].sendall((command + "\n").encode())
            return
        except OSError as err:
            if _open:
                _open.pop().close()  # never keep a dead connection
            if not retry:
                print(f"'{command}' may not have reached the dispatcher ({err}); it is not sent again", flush=True)
            if not had:
                return


def device_name(handle) -> str:
    size = wintypes.UINT(512)
    buf = ctypes.create_unicode_buffer(size.value)
    got = user32.GetRawInputDeviceInfoW(handle, 0x20000007, buf, ctypes.byref(size))  # RIDI_DEVICENAME
    return buf.value.upper() if got > 0 else ""


def main() -> None:
    learn_only = "--learn" in sys.argv
    keys = {} if learn_only or not KEYS_FILE.exists() else json.loads(KEYS_FILE.read_text())  # role -> vk
    held = set()
    jump_as = {}  # what the last jump press was sent as, so its release matches
    # --record NAME: your own presses of the jump key in the game become keypad/geometry_dash/NAME.csv
    recording = {"name": sys.argv[sys.argv.index("--record") + 1], "events": []} if "--record" in sys.argv else {}

    def prompt():
        missing = [r for r in ROLES if r not in keys]
        if missing:
            print(f"Press the {missing[0].upper()} key on the keypad...", flush=True)
        return missing

    def on_key(vk: int, down: bool) -> None:
        missing = [r for r in ROLES if r not in keys]
        if missing:  # learning
            if down and vk not in keys.values():
                keys[missing[0]] = vk
                print(f"  {missing[0]} = key code 0x{vk:02X}", flush=True)
                if not prompt():
                    KEYS_FILE.write_text(json.dumps(keys))
                    print(f"saved {KEYS_FILE}", flush=True)
                    if learn_only:
                        user32.PostQuitMessage(0)
            return
        now = time.perf_counter()
        if vk == keys["jump"]:  # mirror press and release as an Up arrow
            title = ctypes.create_unicode_buffer(200)
            user32.GetWindowTextW(user32.GetForegroundWindow(), title, 200)
            in_game = GAME_TITLE.lower() in title.value.lower()
            if down:
                jump_as["click"] = in_game
            else:  # release what was pressed, even if another window came to the front in between
                in_game = jump_as.get("click", in_game)
            if in_game:
                # in the game: a left mouse click. It jumps in a level and presses Play on the level
                # page (park the mouse pointer on the Play button), so the arm can start the level itself.
                user32.mouse_event(0x0002 if down else 0x0004, 0, 0, 0, 0)
            # Anywhere else it sends nothing at all. It used to send an Up arrow, which scrolled or
            # changed whatever window happened to be in front while the arm kept tapping.
            if not recording:
                notify("key down" if down else "key up")  # lets the arm feel the key: see skills/tap_calibrate.py
            elif in_game and "t0" in recording and (down or recording["events"]):  # first event is a press
                recording["events"].append((now - recording["t0"], down))
        elif down and vk == keys["wave"]:
            print(f"wave -> {send('run wave')}", flush=True)
        elif down and vk == keys["stop"]:
            print(f"STOP -> {send('stop')}", flush=True)  # the stop goes out first; nothing may delay or block it
            if recording.get("events"):
                events = list(recording["events"])
                if events[-1][1]:  # still held when stop was pressed: drop the unfinished press
                    events.pop()
                path = Path(__file__).with_name("geometry_dash") / f"{recording['name']}.csv"
                try:
                    path.write_text("time_ms,state\n" + "".join(
                        f"{t * 1000:.3f},{'down' if d else 'up'}\n" for t, d in events))
                except OSError as err:  # keep the events: the next stop press tries again
                    print(f"could not save {path}: {err}. Press stop again to retry.", flush=True)
                else:
                    print(f"saved {len(events) // 2} presses to {path}", flush=True)
                    recording.clear()

    told = []  # so the "click the game" hint prints once per wait, not twice a second

    def start_game_when_ready() -> None:
        """When a skill waits for the cue, press the restart key in the game. That key press is
        what starts the replay clock (see the R handling below), so game and arm start together."""
        if '"ok": true' not in send("ready", 0.2):
            told.clear()
            return
        game = user32.FindWindowW(None, GAME_TITLE)
        if game:
            user32.SetForegroundWindow(game)
        if game and user32.GetForegroundWindow() == game:
            user32.keybd_event(VK_RESTART, 0, 0, 0)
            user32.keybd_event(VK_RESTART, 0, KEYUP, 0)
        elif not told:
            told.append(1)
            print(f"Arm is ready. Click the {GAME_TITLE} window and press {chr(VK_RESTART)} to start.", flush=True)

    def poll_ready() -> None:
        """Ask the dispatcher twice a second, on a thread of its own. This used to run on a timer
        inside the key-handling loop, where each question could block for up to 0.2 s: a jump key
        pressed during that time reached the game late, by as much as a second when several piled up."""
        while True:
            try:
                start_game_when_ready()
            except Exception as err:  # never let this helper die quietly
                print(f"ready check failed: {err}", flush=True)
            time.sleep(0.3)

    def report_clock() -> None:
        """Tell the dispatcher the Windows time ten times a second, on a connection of its own.
        The clock inside WSL was measured running 4.2% fast, so the dispatcher times a replay by
        this clock, the same one a recording is made with."""
        link = None
        while True:
            try:
                if link is None:
                    link = socket.create_connection(("127.0.0.1", PORT), timeout=0.5)
                    link.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
                    link.setblocking(False)
                link.sendall(f"clock {time.perf_counter():.6f}\n".encode())
                try:
                    if link.recv(4096) == b"":
                        raise ConnectionResetError
                except BlockingIOError:
                    pass
            except OSError:
                if link is not None:
                    link.close()
                link = None
                time.sleep(0.5)
            time.sleep(0.1)

    def wndproc(hwnd, msg, wparam, lparam):
        if msg == WM_INPUT:
            raw = RAWKEYBOARD()
            size = wintypes.UINT(ctypes.sizeof(raw))
            got = user32.GetRawInputData(lparam, 0x10000003, ctypes.byref(raw), ctypes.byref(size), HEADER_SIZE)
            if got != 0xFFFFFFFF and raw.dwType == 1:
                down = not raw.Flags & 1
                key = (raw.hDevice, raw.VKey)  # per device: Z held on the laptop must not hide the keypad's Z
                if down != (key in held):  # ignore auto-repeat while a key is held
                    (held.add if down else held.discard)(key)
                    if DEVICE and DEVICE in device_name(raw.hDevice):
                        on_key(raw.VKey, down)
                    elif down and raw.VKey == VK_RESTART:  # the level restarts: start the replay clock now
                        if recording:
                            # Time zero of a recording is the restart key: a restart begins the level at
                            # once, with no click release or loading in between, and the replay starts
                            # from the same key. Each restart begins the recording again.
                            recording["t0"], recording["events"] = time.perf_counter(), []
                            print("Recording from this restart. Play; press the STOP key when done.", flush=True)
                        else:
                            notify("cue", retry=False)  # on the kept-open connection: the replay clock starts from this
        return user32.DefWindowProcW(hwnd, msg, wparam, lparam)

    proc = WNDPROC(wndproc)  # keep a reference so it is not garbage collected
    cls = WNDCLASS(lpfnWndProc=proc, hInstance=kernel32.GetModuleHandleW(None), lpszClassName="BuddyKeypad")
    user32.RegisterClassW(ctypes.byref(cls))
    hwnd = user32.CreateWindowExW(0, cls.lpszClassName, "keypad", 0, 0, 0, 0, 0,
                                  wintypes.HWND(-3), None, cls.hInstance, None)  # -3 = message-only
    rid = RAWINPUTDEVICE(1, 6, 0x100, hwnd)  # keyboards, delivered even without focus
    if not hwnd or not user32.RegisterRawInputDevices(ctypes.byref(rid), 1, ctypes.sizeof(rid)):
        raise SystemExit(f"Could not listen for keys (Windows error {ctypes.get_last_error()}).")
    threading.Thread(target=poll_ready, daemon=True).start()
    threading.Thread(target=report_clock, daemon=True).start()
    if not prompt():
        print("Keypad ready: wave, jump (Up arrow), stop. Ctrl+C to quit.", flush=True)
    msg = wintypes.MSG()
    while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
        user32.DispatchMessageW(ctypes.byref(msg))


if __name__ == "__main__":
    main()
