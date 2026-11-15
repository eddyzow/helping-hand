"""Start every arm_play run from the same game state. Run on Windows, same arguments as arm_play.py:

    python keypad/geometry_dash/play_clean.py my_macro_full.csv --press-lead-ms 100 --release-lead-ms 133 --no-learn

Why: on 14 Nov the first run after opening the level completed it (23:46, 23:51) and the next run, started from
the level-complete screen, died at exactly 75.36 s both times (23:47, 23:54) although its measured tap timing was
no different. So this presses R once, waits for the level to be running, and only then starts arm_play (which
presses R again): every attempt then begins from "in the level", never from the end screen.
"""
import ctypes
import subprocess
import sys
import time
from pathlib import Path

user32 = ctypes.WinDLL("user32")
game = user32.FindWindowW(None, "Geometry Dash")
if not game:
    sys.exit("Geometry Dash window not found")
for _ in range(10):
    if user32.GetForegroundWindow() == game:
        break
    user32.keybd_event(0x12, 0, 0, 0); user32.keybd_event(0x12, 0, 2, 0)  # a tap of Alt lets Windows hand over the foreground
    user32.ShowWindow(game, 9); user32.SetForegroundWindow(game)
    time.sleep(0.4)
else:
    sys.exit("could not bring the game to the front")
user32.keybd_event(0x52, 0, 0, 0); user32.keybd_event(0x52, 0, 2, 0)      # R: restart, so the level is live
time.sleep(float(2.5))
sys.exit(subprocess.call([sys.executable, str(Path(__file__).with_name("arm_play.py")), *sys.argv[1:]]))
