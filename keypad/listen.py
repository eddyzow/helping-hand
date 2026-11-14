"""SayoDevice keys -> dispatcher commands. Run on Windows (not WSL): python keypad\\listen.py

The keypad needs no configuring. The first run asks you to press its three keys once (wave,
jump, stop) and saves what they send to keypad/keys.json. After that:
    wave key  -> the arm waves
    jump key  -> Windows sees an Up arrow (the Geometry Dash jump), whatever the key really sends.
                 This is the key the arm taps.
    stop key  -> the arm stops at once. Test it at the start of every session.
Only the SayoDevice triggers these (matched by USB id), and it works whichever window has focus.
Needs the dispatcher running for wave and stop. No extra packages.

    python keypad\\listen.py --learn    # relearn the three keys, then quit
"""
import ctypes
import json
import os
import socket
import sys
from ctypes import wintypes
from pathlib import Path

PORT = int(os.environ.get("BUDDY_PORT", "8765"))
DEVICE = os.environ.get("KEYPAD_ID", "VID_8089").upper()  # SayoDevice USB vendor id; "" = any keyboard
KEYS_FILE = Path(__file__).with_name("keys.json")
ROLES = ["wave", "jump", "stop"]
VK_UP, KEYUP, WM_INPUT = 0x26, 0x0002, 0x00FF

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


def send(command: str) -> str:
    try:
        with socket.create_connection(("127.0.0.1", PORT), timeout=1) as s:
            s.sendall((command + "\n").encode())
            return s.makefile().readline().strip()
    except OSError as err:
        return f"dispatcher not reachable: {err}"


def device_name(handle) -> str:
    size = wintypes.UINT(512)
    buf = ctypes.create_unicode_buffer(size.value)
    got = user32.GetRawInputDeviceInfoW(handle, 0x20000007, buf, ctypes.byref(size))  # RIDI_DEVICENAME
    return buf.value.upper() if got > 0 else ""


def main() -> None:
    learn_only = "--learn" in sys.argv
    keys = {} if learn_only or not KEYS_FILE.exists() else json.loads(KEYS_FILE.read_text())  # role -> vk
    held = set()

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
        if vk == keys["jump"]:  # mirror press and release as an Up arrow
            if vk != VK_UP:
                user32.keybd_event(VK_UP, 0, 0 if down else KEYUP, 0)
        elif down and vk == keys["wave"]:
            print(f"wave -> {send('run wave')}", flush=True)
        elif down and vk == keys["stop"]:
            print(f"STOP -> {send('stop')}", flush=True)

    def wndproc(hwnd, msg, wparam, lparam):
        if msg == WM_INPUT:
            raw = RAWKEYBOARD()
            size = wintypes.UINT(ctypes.sizeof(raw))
            got = user32.GetRawInputData(lparam, 0x10000003, ctypes.byref(raw), ctypes.byref(size), HEADER_SIZE)
            if got != 0xFFFFFFFF and raw.dwType == 1 and DEVICE in device_name(raw.hDevice):
                down = not raw.Flags & 1
                if down != (raw.VKey in held):  # ignore auto-repeat while a key is held
                    (held.add if down else held.discard)(raw.VKey)
                    on_key(raw.VKey, down)
        return user32.DefWindowProcW(hwnd, msg, wparam, lparam)

    proc = WNDPROC(wndproc)  # keep a reference so it is not garbage collected
    cls = WNDCLASS(lpfnWndProc=proc, hInstance=kernel32.GetModuleHandleW(None), lpszClassName="BuddyKeypad")
    user32.RegisterClassW(ctypes.byref(cls))
    hwnd = user32.CreateWindowExW(0, cls.lpszClassName, "keypad", 0, 0, 0, 0, 0,
                                  wintypes.HWND(-3), None, cls.hInstance, None)  # -3 = message-only
    rid = RAWINPUTDEVICE(1, 6, 0x100, hwnd)  # keyboards, delivered even without focus
    if not hwnd or not user32.RegisterRawInputDevices(ctypes.byref(rid), 1, ctypes.sizeof(rid)):
        raise SystemExit(f"Could not listen for keys (Windows error {ctypes.get_last_error()}).")
    if not prompt():
        print("Keypad ready: wave, jump (Up arrow), stop. Ctrl+C to quit.", flush=True)
    msg = wintypes.MSG()
    while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
        user32.DispatchMessageW(ctypes.byref(msg))


if __name__ == "__main__":
    main()
