# Ben, Person 4 (agent: Claude Code)

Updated Sat Nov 14, 1:00 AM ET.

## Working on now

Person 4: drawing, personality moves, status screen, demo, pitch, Devpost. Owns `skills/draw.py`,
`skills/personality.py`, `skills/tictactoe.py`, `ui/`, `docs/`. Ben accepted the role at 12:49 AM.

Next, in order:

1. Team review of `docs/demo.md` (first draft pushed with this note).
2. `skills/personality.py` (nod, celebrate, droop, fist bump) against `MockArm`. Waiting for
   `daniel/arm-core` to merge to `main` so it lands in the right tree; will build on the branch if
   the merge is not soon.
3. `skills/draw.py` as a thin skill around Eddy's root `draw.py`, one fixed word first.
4. Pen holder: a person's job, not this agent's.

## Done and how it was tested

- `docs/demo.md`: pitch outline, a 90-second table script in blocks, failure procedure, table and
  submission checklists. A document only. No skill in it has run on the real arm.
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
- Daniel: for personality moves I plan to follow `skills/wave.py`: load a taught pose, offset one
  or two joints by a few degrees, return home. That needs no new taught poses except one for fist
  bump. Object if joint offsets from `wave_up` are unsafe on the real arm.
- Jonathan: please push the Geometry Dash code and a `notes/jonathan.md`. Block 5 of the script is
  written without having seen it.
- Eddy: how long does `draw.py --go` take for a five-letter word at the default `PEN_SPEED`? An
  estimate from the stroke length is enough for now; the script assumes it may exceed 25 seconds.
- Anyone who knows: what the arm kit cost, and how long a judge spends at each table.

## Answers to questions other notes asked

- Daniel's note (Ben, P4): acknowledged. Not rebuilding the drawing pipeline; wrapping it.
- Eddy's note (Ben, `draw.py` is yours to wrap): acknowledged, and noted that generated drawings
  take about 20 seconds, so the demo uses text or cached drawings.
