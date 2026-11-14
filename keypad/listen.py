"""Keypad keys -> dispatcher commands. Run on Windows (not WSL): python keypad\\listen.py

Works whichever window has focus, so the stop key still works while a game is open.
Set the SayoDevice keys to F13, F14 and F15 in its configurator so they clash with nothing.
Needs the dispatcher running (python -m core.dispatcher). No extra packages.
"""
import ctypes
import os
import socket
from ctypes import wintypes

PORT = int(os.environ.get("BUDDY_PORT", "8765"))
KEYS = {  # virtual-key code -> command
    0x7C: "run wave",    # F13
    0x7D: "run gd_tap",  # F14
    0x7E: "stop",        # F15: emergency stop. Test it at the start of every session.
}
WM_HOTKEY, MOD_NOREPEAT = 0x0312, 0x4000


def send(command: str) -> str:
    try:
        with socket.create_connection(("127.0.0.1", PORT), timeout=1) as s:
            s.sendall((command + "\n").encode())
            return s.makefile().readline().strip()
    except OSError as err:
        return f"dispatcher not reachable: {err}"


def main() -> None:
    user32 = ctypes.windll.user32
    commands = list(KEYS.values())
    for i, vk in enumerate(KEYS):
        if not user32.RegisterHotKey(None, i, MOD_NOREPEAT, vk):
            raise SystemExit(f"Could not claim key 0x{vk:02X}; another program has it.")
    print("Listening for F13 (wave), F14 (gd_tap), F15 (stop). Ctrl+C to quit.", flush=True)
    msg = wintypes.MSG()
    while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
        if msg.message == WM_HOTKEY:
            command = commands[msg.wParam]
            print(f"{command} -> {send(command)}", flush=True)


if __name__ == "__main__":
    main()
