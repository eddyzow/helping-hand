# Ben, Person 4 (agent: Claude Code)

Updated Sat Nov 14, 1:05 AM ET.

## Working on now

Person 4: drawing, personality moves, status screen, demo, pitch, Devpost. Owns `skills/draw.py`,
`skills/personality.py`, `skills/tictactoe.py`, `ui/`, `docs/`. Ben accepted the role at 12:49 AM.

Next, in order:

1. Team review of `docs/demo.md` (first draft pushed with this note).
2. `skills/personality.py` is written, on branch `ben/personality` (`79ac6aa`), cut from
   `daniel/arm-core` at `bbdfac5`. Mock only; see below. It adds one file and touches nothing else.
3. `skills/draw.py` as a thin skill around Eddy's root `draw.py`, one fixed word first.
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
- Daniel: when `daniel/arm-core` merges to `main`, say so in your note. `newcontext.md` says poses
  `home`, `wave_up` and `tap_up` are taught, and they are in the branch; your reviewer's note still
  says only `home` was seen. Which is current?
- Daniel: `ben/personality` is ready for you to pull into `daniel/arm-core` or merge after it,
  your call; I have not touched your branch. In an arm slot, please try the moves one at a time in
  this order, slowest and smallest first, with someone on the stop key: `droop`, `nod`, `shake`,
  `dance`, `celebrate`. For each, tell me if a joint goes the wrong way or comes close to anything,
  and I will change the table at the top of the file. `shake` and `dance` swing shoulder_pan by 10
  to 12 degrees, which moves the whole arm sideways.
- Jonathan: please push the Geometry Dash code and a `notes/jonathan.md`. Block 5 of the script is
  written without having seen it.
- Eddy: how long does `draw.py --go` take for a five-letter word at the default `PEN_SPEED`? An
  estimate from the stroke length is enough for now; the script assumes it may exceed 25 seconds.
- Anyone who knows: what the arm kit cost, and how long a judge spends at each table.

## Answers to questions other notes asked

- Daniel's note (demo block 2): applied in `docs/demo.md`. Wave is X, stop is Z, home is typed, and
  the failure procedure no longer says to home and retry an unexplained failure. Personality moves
  will stay mock-only until you validate joint offsets and fist-bump clearance on the arm.
- Jonathan's note: block 5 now reflects your branch. One question for the demo: your script opens
  the follower's COM port itself from Windows, and the dispatcher owns the arm in WSL. At the table
  only one can hold it. Is the plan to move Geometry Dash behind the dispatcher before the freeze?

- Daniel's note (Ben, P4): acknowledged. Not rebuilding the drawing pipeline; wrapping it.
- Eddy's note (Ben, `draw.py` is yours to wrap): acknowledged, and noted that generated drawings
  take about 20 seconds, so the demo uses text or cached drawings.
