#!/usr/bin/env bash
# The live demo, as a menu. In WSL:   bash demo/run.sh      (or double-click demo\DEMO.bat in Windows)
#
# Live: pen drawing, tic-tac-toe against a person, gestures on the 3-key pad. One arm program at a time.
# Ctrl+C stops whatever is running and comes back to this menu; the arm stays powered and holding.

cd /mnt/c/Users/Khang/helping-hand || exit 1
source demo/cmds.sh >/dev/null

# Stop every pad listener, so there is never more than one (two would send each key twice).
pad_stop() {
  powershell.exe -NoProfile -Command "Get-CimInstance Win32_Process | Where-Object { \$_.Name -like 'python*' -and \$_.CommandLine -match 'keypad/listen.py' } | ForEach-Object { Stop-Process -Id \$_.ProcessId -Force }" 2>/dev/null
}

# Is another arm program holding the arm? (dispatcher, a drawing, tic-tac-toe, steady)
arm_busy() {
  powershell.exe -NoProfile -Command "(Get-CimInstance Win32_Process | Where-Object { \$_.Name -like 'python*' -and \$_.CommandLine -match 'core.dispatcher|demo/loop.py|demo/ttt|demo/measure.py|steady.py' } | Measure-Object).Count" 2>/dev/null | tr -d '\r'
}

gestures() {   # X = hi, C (rightmost) = high five, Z = dance
  if [ "$(arm_busy)" != "0" ]; then echo "Another arm program is still running. Stop it first (Ctrl+C in its window)."; return; fi
  $PY demo/grip.py open
  echo
  echo ">>> TAKE THE PEN OUT OF THE CLAW NOW. Gestures open and close it. Starting in 6 seconds..."
  sleep 6
  pad_stop
  (KEYPAD_WAVE="${1:-hi}" KEYPAD_JUMP="${2:-high_five}" KEYPAD_THIRD="${3:-dance}" $PY keypad/listen.py --show &)
  echo ">>> Pad keys: X = ${1:-hi}   C (rightmost) = ${2:-high_five}   Z = ${3:-dance}"
  echo ">>> Press a key once and wait; the arm takes a moment to rise. Ctrl+C here ends gesture mode."
  dispatcher
  pad_stop
}

pen_ready() {  # after the pen is put in the claw, or moved
  $PY demo/grip.py 50 && $PY demo/measure.py
}

while true; do
  cat <<'MENU'

================  ARM DEMO  ================
 PEN (do these when the pen goes into the claw)
   1  grip the pen, then measure the paper height   (5 dots, about 1.5 min)
   2  grip the pen only
 DRAW
   3  tic-tac-toe, one game            (fresh sheet)
   4  tic-tac-toe, game after game     (fresh sheet each time; Ctrl+C twice to end)
   5  tic-tac-toe on a used sheet
   6  flower        7  house        8  heart
 PAD GESTURES (take the pen out when asked)
   9  gestures on the pad: X = hi, C = high five, Z = dance
 OTHER
   o  open the claw        s  stop a gesture        l  lighter pen for tic-tac-toe        f  firmer pen for tic-tac-toe
   q  quit
MENU
  read -r -p "choose: " pick
  case "$pick" in
    1) pen_ready ;;
    2) grip ;;
    3) ttt ;;
    4) ttt_loop ;;
    5) ttt_used ;;
    6) flower ;;
    7) house ;;
    8) heart ;;
    9) gestures ;;
    o) grip_open ;;
    s) arm_stop ;;
    l) ttt_lighter ;;
    f) ttt_firmer ;;
    q) break ;;
    *) echo "not a choice" ;;
  esac
done
