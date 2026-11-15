# Arm session, Sat 14 Nov evening to Sun 15 Nov 00:20: drawing with webcam feedback, and Geometry Dash timing

Written by Daniel's agent (Claude Code) from the laptop the arm is plugged into. Everything here ran on the
real follower arm (COM3) unless it says otherwise. Numbers are the ones measured in this session.

## 1. Drawing: what works now

The follower draws with a Sharpie held in the claw. A house (walls, roof, door, two windows) and a flower
(centre, five petals, stem, two leaves) were drawn on A4 paper and scored by a USB webcam.

Code is in `drawloop/`. It uses Eddy's root `arm.py` and `grid.py` and does not go through the dispatcher.
Run from the repo root on Windows, with `FOLLOWER_PORT` left alone (the scripts set COM3):

| Step | Command | What it does |
|---|---|---|
| Teach the page | `python drawloop/teach_paper.py` | Arm joints limp, claw keeps gripping. Hand-pose 8 points (4 corners pen down, 4 lifted 2 cm). A pose saves when the arm is still for 3 s or a pad key is pressed. Writes `poses/paper_2x2.json`. |
| Measure paper height | `python drawloop/measure.py` | Touches the pen down at 5 points, fits a plane, writes `drawloop/height.json`. Leaves 5 dots. Redo after the pen is re-gripped. |
| Draw and score | `STATE=state_house.json python drawloop/loop.py drawloop/house.json` | Waits for a clean sheet with all 4 corners in view, draws stroke by stroke, photographs after each stroke, scores, saves corrections for the next round. |
| Playtests | `python drawloop/playtest.py`, `playtest2.py` | Eight 16 mm circles per sheet, sweeping pressure/speed/motor gain, then joint-slack lead. |

Strokes are JSON lists of `[X, Y]` in millimetres, X right and Y up as the camera sees the page.
`poses/paper_2x2.json` is a 2 by 2 grid, kept under its own name so `skills/draw.py` does not pick it up:
that skill has none of the corrections below and would draw about 2 cm above the paper.

## 2. Drawing: what was learned (in the order it was found)

1. **The taught "pen down" layer was about 2 cm above the paper** in the middle of the page. The arm blends
   joint angles between the 4 taught corners, and the blend rides high. Fixed by touching down and fitting a plane.
   Contact shows as a drop in the elbow's following error (about 2.1 degrees in free air, falling once the
   table carries the arm); the camera agreed to within one 2 mm step.
2. **A circle on the taught grid came out as a 107 x 46 mm oval.** On this grid "left-right" is base rotation
   and "near-far" is reach. Drawings are now laid out in millimetres and converted to base angle and reach.
3. **Webcam scoring.** The sheet's four corners give a homography to millimetres (A4, long side across the
   camera's view). Each stroke's own ink is what is new since the previous photo. Gate: every stroke left ink,
   95 % of the intended line has ink within 2 mm, ink centre line on average within 1 mm of the plan.
4. **House, ten rounds of correction** (each point moved by 70 %, later 35 %, of its measured error):
   coverage 27, 64, 94, 96, 93, 91, 95, 90, 97.6, 97.6 %; distance ended at 1.0 to 1.2 mm. Never passed the
   1.0 mm gate; best round missed by 0.01 mm. Pictures: `docs/drawloop/house_round9.jpg`, `house_round10.jpg`.
5. **Curves came out as boxes** (flower petals, 15 mm). Playtest 1: light pressure does not touch, firm draws a
   complete line (they are 2 mm apart); 50 mm/s draws as complete a line as 25; motor position gain 32 makes
   the pen chatter (kept at 16). None of these fixed the boxes.
6. **Cause of the boxes: slack in the joints when they reverse.** Playtest 2 pushed the command ahead along
   each axis's direction of travel. Radial spread of a 16 mm circle: 18 to 28 % with no lead, 12.4 % at
   2.5 mm, **10.2 % at 3 mm on both axes** (best of eight). Still 14 % too small, so 3.5 to 4 mm may be better;
   not tested.
7. **Flower with 3 mm lead, firm pressure, 30 mm/s, first attempt:** 9 of 9 strokes, 90 % covered, 1.04 mm
   (before: 58 %, 1.72 mm, square petals). `docs/drawloop/flower_with_slack_lead.jpg`. One run only.

Settings now in `loop.py`: `LEAD=3,3` mm, `PRESS=-0.13`, 30 mm/s with stroke points written straight to the
motors (no position read first; the read capped speed at 23 mm/s).

## 3. Drawing: known problems

- The sheet creeps while the arm draws unless taped on all four sides. Corrections then learn wrong positions.
- A stroke that is mostly missing was mis-read for three rounds as "pen too high"; it was a good square 9 mm
  out of place. The loop now shifts such a stroke as a whole.
- Pressing harder to fix a faint line makes the pen stick. A marker left uncapped for hours draws pale and
  scores as missing. A sprung or padded pen mount would widen the 2 mm working range; not built.
- Open strokes overrun their ends by about 3 mm (the door's legs). A correction for this was written and has
  run once.
- The claw motor reached 62 C gripping continuously (cut-out 70 C). Squeeze force is lowered between drawings.
- Nothing here is in the dispatcher, so the pad's stop key works only because each script listens on port 8765
  itself. Do not run a drawing script and the dispatcher at the same time.

## 4. Geometry Dash: timing findings

- `core/arm.py` now retries motor reads 12 times. Without it the first garbled reply from the faulty
  wrist-roll motor (id 5) ended every skill ("motor 5: Parsing error").
- The keypad listener that had run since 5 PM had stopped delivering key presses. `tap_calibrate` then lowers
  8 units and reports the key never registered. Restarting `keypad/listen.py` fixed it.
- Lead times move with every re-seat of the pad. Three calibrations tonight: key registers at 15.15, 13.35,
  12.45; `tap_delay` (30 taps): press 98 to 100 ms / release 132 to 133 ms, then press 106 / release 114.
  Measure with `run tap_delay {"times": 30}` after every `tap_calibrate` and pass both numbers to `arm_play.py`.
- Stereo Madness (`my_macro_full.csv`): completed at 23:37, 23:46 and 23:51. Deaths at 40.3 % (four times)
  went with the release at 33.65 s being 5.5 to 23.7 ms late.
- **A run started from the level-complete screen died at exactly 75.36 s both times** (23:47, 23:54) with tap
  timing no different from the winning runs. `keypad/geometry_dash/play_clean.py` presses R once and waits
  2.5 s before starting `arm_play.py`, so every attempt starts from inside the level. Untested against the game.
- "game lost focus" ended the second attempt of a batch six times out of six. A foreground-window log caught
  one: the Alt+Tab switcher, then the terminal. Leave the keyboard alone between attempts.
- `arm_play.py` learns per-tap corrections after every run (30 % of each tap's lateness). After a winning run
  this changes the next run's timing. `--no-learn` keeps runs identical.
- `deadlocked.csv`: Daniel's own recording, 112 presses in 59 s. 21 holds are shorter than the arm's 100 ms
  press, 18 pauses shorter than its release, 12 of 111 press-to-press gaps under 235 ms; the first is 1.5 s in.
  Not yet replayed on the arm.

## 5. Not done

- Eddy's `draw.py` output (writing, text, sketches) is not yet fed through the loop. The loop takes any
  stroke list, so this needs a unit-square to millimetre adapter only.
- `python -m tests.test_core` prints `core ok` with the retry change. No other test was run on these files.
- Wrist-roll motor temperature was not read during the Geometry Dash runs; the dispatcher powers all six joints.

## 6. After 02:00 on 15 Nov: tic-tac-toe, circle tuning, and the demo commands

Everything below is in `demo/` (new folder; `drawloop/` holds the earlier versions). Load the commands in WSL with
`cd /mnt/c/Users/Khang/helping-hand && source demo/cmds.sh`; the file lists every demo as one word.

**Tic-tac-toe on paper (`demo/ttt2.py`, command `ttt`).** The arm draws a 66 mm grid and plays O; a person draws X with
their own pen. A webcam reads the board. The arm's move comes from a full search of the game: 400 simulated games
against random play, 0 lost. On the real arm one complete game was played and won by the arm (02:50), reading all three
of the person's moves and re-aiming for a sheet that crept 5 mm. Faults found on the way, each from the game's own log
and photos:

- Grid too faint to find, then drawn at 59 % of size with more pressure (the pen sticks). The game now refuses to play
  if the grid it finds is not between 70 and 150 % of plan size.
- Grid lines cut about 10 mm short: the pen was lifted before the lagging arm arrived. Lines are now drawn at 25 mm/s
  with a 0.6 s wait before the lift.
- A person's X bigger than its square never satisfied "exactly one square changed". The move is now the square that
  gained the most ink, if it holds at least half of the gain.
- Comparing photo against photo broke when the sheet crept: every old line looked new. Ink is now counted inside the
  middle of each square in every photo.
- A faint pen did not register (23 pixels against 256 for a marker). Squares are read with a much lower darkness
  threshold than the grid is.
- **Illegal move, 03:10:** the arm drew its O on the person's X. People were holding the sheet by its corners, which
  bends the corner-based camera mapping, and the squares were read one square off. `ttt2.py` takes the camera-to-table
  mapping once, from the clean hands-off photo before the game, and from then on follows the grid lines themselves.
  **`ttt2.py` has not been played yet.**

**Circles.** Every small circle began with a straight tail (it looked like a 6): the pen lands up to a slack's width
from where it was told, and the tail is the joints taking the slack up. A pen-up run-in along the direction the stroke
leaves in removed it. 14 mm circles, radial spread: without run-in 8.5 to 39 %; with run-in and 4 to 4.5 mm lead,
5.7 to 12.5 % over seven circles (an eighth could not be scored), diameter 11.3 to 13.1 mm. The run-in is in `ttt.py`
and `ttt2.py` only, not yet in `loop.py`.

**Other findings.**
- The wrist-roll motor reached 63 C and stopped answering for a few minutes; every script on the normal connection then
  fails, because it checks six motors. Drawing and game scripts now switch that motor off after connecting.
- One camera-less grab of a Duplo brick at the taught grid's centre: 5.3 s from start to the hand-over pose, but the
  jaws pushed the brick away and it arrived empty.
- Claude found the brick in a webcam photo in 2.2 s (Sonnet) with a tight box. That is perception only.
- Ten gestures pass a MuJoCo check on branch `daniel/gestures-sim` (five new: bow, look_around, victory, impatient,
  droop; none moves the wrist roll). None has run on the real arm.
- Drawing over old ink or with a hand on the sheet makes the scorer's numbers meaningless; three flower runs were
  discarded for this. The last clean flower run: 9 of 9 strokes, 87.7 % covered, 0.99 mm.
