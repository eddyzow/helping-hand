# Demo commands for the arm laptop. In the WSL terminal, once:
#
#     cd /mnt/c/Users/Khang/helping-hand && source demo/cmds.sh
#
# then type a command name. Only ONE arm program can run at a time (they share COM3): stop one before starting another.
# Stop anything: Ctrl+C in its terminal, or the pad's stop key (Z). After a stop the arm stays powered and holding.

PY=/mnt/c/Users/Khang/so101/.venv/Scripts/python.exe
cd /mnt/c/Users/Khang/helping-hand
# Windows programs only see these settings from WSL if they are listed here.
export WSLENV="STATE:USED:OVERDRAW:FAST:ANY:RESUME:BOARD:GRID_PRESS:O_PRESS:GRIP:LEAD:FOLLOWER_PORT:ARM_NO_PROMPT:KEYPAD_MODE:KEYPAD_WAVE:ROLL_POWER:${WSLENV}"

# --- claw ---------------------------------------------------------------------------------------------------
grip()      { $PY demo/grip.py "${1:-50}"; }      # grip the pen (50 % force; "grip 30" for a long hold)
grip_open() { $PY demo/grip.py open; }            # open the claw: whatever it holds drops
grip_off()  { $PY demo/grip.py off; }             # claw motor off

# --- before drawing: after the pen is put in or moved in the claw ---------------------------------------------
measure()   { $PY demo/measure.py; }              # 5 touch-downs (1.5 min, 5 dots): finds the paper height

# --- tic-tac-toe against a person ------------------------------------------------------------------------------
# ttt2.py is the current game (the squares follow the grid, not the sheet's corners). ttt.py is the first version, kept.
ttt()       { $PY demo/ttt2.py; }                 # waits for a FRESH sheet with hands off, draws the grid, plays O
ttt_loop()  { while true; do $PY demo/ttt2.py; sleep 2; done; }   # game after game: each waits for a fresh sheet. Ctrl+C twice to end
ttt_used()  { ANY=1 $PY demo/ttt2.py; }           # same, on a sheet that already has marks
ttt_lighter() { GRID_PRESS=-0.18 O_PRESS=-0.20 $PY demo/ttt2.py; }  # if the pen sticks or the grid comes out small
ttt_firmer()  { GRID_PRESS=-0.12 O_PRESS=-0.14 $PY demo/ttt2.py; }  # if the lines are too faint

# --- drawings (USED=1 OVERDRAW=1: draw on whatever sheet is there; FAST=1: no photos, just draw) -----------------
flower()    { USED=1 OVERDRAW=1 FAST=1 STATE=state_flower.json $PY demo/loop.py demo/flower.json; }
house()     { USED=1 OVERDRAW=1 FAST=1 STATE=state_house.json  $PY demo/loop.py demo/house.json; }
heart()     { USED=1 OVERDRAW=1 FAST=1 STATE=state_heart.json  $PY demo/loop.py demo/heart.json; }
flower_scored() { USED=1 OVERDRAW=1 STATE=state_flower.json $PY demo/loop.py demo/flower.json; }   # with photos and a score

# --- the other demos ---------------------------------------------------------------------------------------------
steady()    { $PY steady.py; }                    # tremor-filter teleop (leader arm must be plugged in)
dispatcher(){ FOLLOWER_PORT=COM3 ARM_NO_PROMPT=1 $PY -m core.dispatcher; }   # needed for Geometry Dash and gestures
gd()        { $PY keypad/geometry_dash/play_clean.py my_macro_full.csv --press-lead-ms "${1:-106}" --release-lead-ms "${2:-114}" --no-learn; }
keypad()    { $PY keypad/listen.py; }             # the 3-key pad listener, game mode: C is the Geometry Dash key
show_keys() { KEYPAD_MODE=show $PY keypad/listen.py; }   # show mode: X = dance, C = next gesture, Z = stop (needs dispatcher)
gesture()   { $PY -c "import socket,sys; c=socket.create_connection(('127.0.0.1',8765),timeout=5); c.sendall(('run gesture {\"name\": \"'+sys.argv[1]+'\"}\n').encode()); print(c.makefile().readline().strip())" "${1:-dance}"; }   # gesture bow

echo "arm demo commands loaded: grip grip_open grip_off | measure | ttt ttt_used ttt_lighter ttt_firmer | flower house heart | steady dispatcher gd keypad"
