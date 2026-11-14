# Ben, Person 4 (agent: Claude Code)

Updated Sat Nov 14, 1:40 AM ET.

## Working on now

Person 4: drawing, personality moves, status screen, demo, pitch, Devpost. Owns `skills/draw.py`,
`skills/personality.py`, `skills/tictactoe.py`, `ui/`, `docs/`. Ben accepted the role at 12:49 AM.

Next, in order:

1. Team review of `docs/demo.md` (first draft pushed with this note).
2. `skills/personality.py` is on `main` (merged in `c6a3418`). Originally `ben/personality`, cut from
   `daniel/arm-core` at `bbdfac5`. Mock only; see below. It adds one file and touches nothing else.
3. `skills/draw.py` is on `main`, mock only; see below. Next for it: a taught paper grid and a
   pen holder, then a first try in an arm slot.
4. Pen holder: a person's job, not this agent's.

## Done and how it was tested

- `docs/demo.md`: pitch outline, a 90-second table script in blocks, failure procedure, table and
  submission checklists. A document only. No skill in it has run on the real arm.
- `skills/personality.py` on `ben/personality`: one skill, `run personality {"move": "nod"}`, with
  moves nod, shake, celebrate, droop, dance. Each goes home, to `wave_up`, through a table of small
  joint offsets from `wave_up` (largest is 35 degrees on wrist_flex), back to `wave_up`, home.
  Tested 1:05 AM on Ben's laptop, no hardware: `python -m skills.personality` prints
  `personality ok` (every move starts and ends at home, stays within 35 of `wave_up`, gripper stays
  0 to 100, an unknown move sends nothing, a stop mid-move sends nothing further and does not
  home). `python -m tests.test_core` still prints `core ok`. Through `python -m core.dispatcher
  --mock`: listed, a bad move refused, nod completed, dance stopped by `stop`.
  Not known: the sign of each joint on the real arm, and whether these offsets clear the table and
  the keypad from `wave_up`. No fist bump: it needs its own taught pose.
- `skills/draw.py` on `main`: `run draw` writes "HI", `run draw {"text": "BEN"}` writes a word of
  up to 8 plain characters. It reuses root `draw.py` for strokes (`from_text`, `resample`,
  `PEN_SQUEEZE`, `PEN_SPEED`) and `grid.py`, but moves the arm only through `arm.move_joints`, so
  the dispatcher owns the arm and the stop key works. Root `draw.py --go` opens its own connection
  and is not used. The whole word is planned and checked before the first move.
  Tested 1:40 AM on Ben's laptop, no hardware: `python -m skills.draw` prints `draw ok` on a fake
  arm and a made-up grid (no grid, bad text and a NaN in the grid each send nothing; a normal run
  starts and ends at home with the pen grip unchanged; the pen is only ever down or up; a stop
  mid-word sends nothing further). `core ok` and `personality ok` still print. In
  `python -m core.dispatcher --mock` it is listed and refuses with "no paper grid".
  Not known: everything physical. There is no `poses/paper.json`, so no real plan has been made.
- Earlier code read of Eddy's root scripts. Eddy acted on it in `965bcea`. I read the `draw.py`
  change (pen squeeze) and it does what the note says; I have not read the `arm.py` and `pick.py`
  changes.
- This agent has no arm, camera or keypad. It has run only `python grid.py`.

## Needs from others

- Everyone: the track. `docs/demo.md` lays out Accessibility against Hardware and what each needs
  from the demo. Ben leans Accessibility if fetch works live; Eddy leans Hardware. Four humans need
  to settle it before the Saturday midnight submission.
- Everyone: read the table script in `docs/demo.md` and correct your own row (trigger, fallback,
  state today). Daniel block 2, Eddy block 3, Jonathan block 5.
- Daniel: `skills/personality.py` is on `main` since `c6a3418` (thank you). Re-run at 1:30 AM on
  `main` at `f98debb`: `personality ok`, `core ok`. In an arm slot, please try the moves one at a
  time in this order, slowest and smallest first, with someone on the stop key: `droop`, `nod`,
  `shake`, `dance`, `celebrate`. For each, tell me if a joint goes the wrong way or comes close to
  anything, and I will change the table at the top of the file. `shake` and `dance` swing
  shoulder_pan by 10 to 12 degrees, which moves the whole arm sideways.
- Daniel: `wave_up` was re-tuned for the wider wave. Personality moves start from the same pose, so
  if you re-teach `wave_up` again, the personality clearance check needs repeating.
- Eddy: planned drawing times at your default `PEN_SPEED` 0.15 are 31 to 54 seconds for names of 2
  to 8 letters (table in `docs/demo.md`). About 1.8 seconds of each stroke is lift and lower. Is a
  higher `PEN_SPEED` reasonable, or do you expect the pen to skip? That is yours to tune.
- Eddy: `skills/draw.py` copies three lines of your squeeze logic from `draw.draw()`. If you move
  that into a small function in root `draw.py`, I will call it and delete my copy.
- Daniel: two things `skills/draw.py` assumes that need your eyes on the arm. First, it goes to the
  home pose with the gripper kept at the pen grip, not home's closed gripper, so the motor does not
  strain against the pen. Does home still rest safely with a pen sticking out? Second, the pen has
  to be put in the gripper by a person before `run draw`; is that done with the motors on or off?
- Daniel or whoever has the arm: `python arm.py teach paper` is needed once before the first try.
  Note Daniel's reviewer found that connecting toggles torque before the hold-the-arm prompt.
- Anyone who knows: what the arm kit cost, and how long a judge spends at each table.

## Answers to questions other notes asked

- Daniel's note (demo block 2): applied in `docs/demo.md`. Wave is X, stop is Z, home is typed, and
  the failure procedure no longer says to home and retry an unexplained failure. Personality moves
  will stay mock-only until you validate joint offsets and fist-bump clearance on the arm.
- Daniel's note (update demo references): done. Block 5 of `docs/demo.md` now describes the
  `geometry_dash` dispatcher skill on `main` and the `tap_key` pose. My earlier question to
  Jonathan about two programs holding the arm is answered by that integration.

- Daniel's note (Ben, P4): acknowledged. Not rebuilding the drawing pipeline; wrapping it.
- Eddy's note (Ben, `draw.py` is yours to wrap): acknowledged, and noted that generated drawings
  take about 20 seconds, so the demo uses text or cached drawings.
