# Demo commands for the arm laptop. In the WSL terminal, once:
#
#     cd /mnt/c/Users/Khang/helping-hand && source demo/cmds.sh
#
# then type a command name. Only ONE arm program can run at a time (they share COM3): stop one before starting another.
# Stop anything: Ctrl+C in its terminal, or the pad's stop key (Z). After a stop the arm stays powered and holding.

PY=/mnt/c/Users/Khang/so101/.venv/Scripts/python.exe
cd /mnt/c/Users/Khang/helping-hand
# Windows programs only see these settings from WSL if they are listed here.
export WSLENV="STATE:USED:OVERDRAW:FAST:ANY:RESUME:BOARD:GRID_PRESS:O_PRESS:GRIP:LEAD:FOLLOWER_PORT:ARM_NO_PROMPT:KEYPAD_MODE:KEYPAD_WAVE:KEYPAD_JUMP:KEYPAD_THIRD:ROLL_POWER:LEADER_PORT:${WSLENV}"

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

# --- switching: stop every arm program and pad listener started from this repo, so the next one can take COM3 ----
stop_all()  { powershell.exe -NoProfile -Command "Get-CimInstance Win32_Process | Where-Object { \$_.Name -like 'python*' -and \$_.CommandLine -match 'keypad/listen.py|core.dispatcher|demo/loop.py|demo/ttt|demo/measure.py|demo/voice_draw.py|robtop_voice.py|steady.py|teleop_sync.py|play_clean.py' } | ForEach-Object { Stop-Process -Id \$_.ProcessId -Force }" 2>/dev/null; echo "stopped: the arm is free for the next program"; }

# --- the other demos ---------------------------------------------------------------------------------------------
teleop()    { $PY teleop_sync.py; }               # plain teleop: follower copies the leader (leader on COM4). Ctrl+C: follower goes LIMP, hold it
steady()    { $PY steady.py; }                    # tremor-filter teleop (leader arm must be plugged in)
dispatcher(){ FOLLOWER_PORT=COM3 ARM_NO_PROMPT=1 $PY -m core.dispatcher; }   # needed for Geometry Dash and gestures
gd()        { $PY keypad/geometry_dash/play_clean.py my_macro_full.csv --press-lead-ms "${1:-106}" --release-lead-ms "${2:-114}" --no-learn; }
keypad()    { $PY keypad/listen.py; }             # the 3-key pad listener, game mode: C is the Geometry Dash key
arm_stop()  { $PY -c "import socket; c=socket.create_connection(('127.0.0.1',8765),timeout=5); c.sendall(b'stop\n'); print(c.makefile().readline().strip())"; }   # stop a gesture: the pad has no stop key in show mode
# Gestures: nod shake fist_bump high_five dance bow look_around victory impatient droop
show_keys() { KEYPAD_WAVE="${1:-hi}" KEYPAD_JUMP="${2:-high_five}" KEYPAD_THIRD="${3:-dance}" $PY keypad/listen.py --show; }   # X, C, Z: show_keys hi bow dance
# After a drawing: take the pen out, then this. The pad listener goes to the background, the dispatcher takes the arm.
dance_mode() { $PY demo/grip.py open; echo "TAKE THE PEN OUT NOW (the claw is open). Starting in 6 s..."; sleep 6;
               (KEYPAD_WAVE="${1:-hi}" KEYPAD_JUMP="${2:-high_five}" KEYPAD_THIRD="${3:-dance}" $PY keypad/listen.py --show &); dispatcher; }
# --- voice (ElevenLabs; Enter, speak, Enter) -------------------------------------------------------------------
voice()      { $PY robtop_voice.py; }             # gestures by voice: "do a dance", "high five". Needs the dispatcher running
voice_draw() { $PY demo/voice_draw.py; }          # drawings by voice: "draw a flower", "play tic tac toe". Dispatcher must be OFF

# --- Geometry Dash, just in case (dispatcher running in another terminal, keypad in game mode) -----------------
arm_do()   { $PY -c "import socket,sys,time
def send(c):
    s=socket.create_connection(('127.0.0.1',8765),timeout=5); s.sendall((c+'\n').encode()); r=s.makefile().readline().strip(); s.close(); return r
print(send(sys.argv[1]))
while '\"busy\": true' in send('status'): time.sleep(0.5)
print(send('status'))" "$1"; }
gd_place() { arm_do "run tap_place"; }            # arm hovers over its tap spot: slide the pad's C key under the tip, tape it
gd_cal()   { arm_do "run tap_calibrate" && arm_do 'run tap_delay {"times": 30}'; }   # prints press_ms and release_ms: give them to gd
# gd <press_ms> <release_ms>    plays Stereo Madness (my_macro_full.csv), for example: gd 105 116

# The whole live demo as a menu:  bash demo/run.sh   (it stops old pad listeners itself, which dance_mode does not)   # show mode: X = dance, C = next gesture, Z = stop (needs dispatcher)
gesture()   { $PY -c "import socket,sys; c=socket.create_connection(('127.0.0.1',8765),timeout=5); c.sendall(('run gesture {\"name\": \"'+sys.argv[1]+'\"}\n').encode()); print(c.makefile().readline().strip())" "${1:-dance}"; }   # gesture bow

echo "arm demo commands loaded: stop_all | grip grip_open grip_off | measure | ttt ttt_used ttt_lighter ttt_firmer | flower house heart | dance_mode show_keys arm_stop | teleop steady | voice voice_draw | dispatcher keypad gd_place gd_cal gd"
