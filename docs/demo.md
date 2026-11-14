# Demo script and pitch outline

Drafted by Ben's agent (Person 4). Rebuilt Sat Nov 14, 4:15 AM around the team's skill list as Eddy
gave it at 4:05 AM. Ben was asleep and has not reviewed this version; the earlier one is in git at
`78addaa`. Event facts are from `AGENTS.md` and `PLAN.md`.

## The team's skill list (Eddy, 4:05 AM)

"gd (almost done), duplo (almost done), then we are doing drawing tomorrow, and feeding food and
water also tomorrow."

| Skill | Owner | State as recorded in the repo at 4:15 AM |
|---|---|---|
| Geometry Dash | Jonathan, Daniel | Has run on the real arm (Eddy, 4:07 AM: "seems decent", timing offsets being tuned). No note yet says what was run or measured. All of it is on `main` since 5:24 AM (`a1a7599`): the replay skill, tap calibration and delay measurement, macro recording, a software-only replay and a browser timing study. That study reports "no crash heard", not a cleared level. At 1:27 PM a commit on Daniel's branch (`f1e8a18`, not on `main`) is titled "the arm completes Stereo Madness", with replay timed on Windows. That is the owner's report: the reviewer notes the script's own "completed" cannot tell a late death from a win, so it needs someone who watched the level finish, and ideally a video |
| Duplo by voice: pick up, hand over, put next to | Eddy, Daniel | On `main` since 4:38 AM (pull request 3 merged), mock and simulation only. The finding open at the merge (a missing placement destination became a handover) has a fix on `main` from Eddy at 4:45 AM (`f271764`), checked by Daniel's reviewer at 4:54 AM: a valid placement works. The two related cases left open then were fixed by Eddy at 10:24 AM (`b49533d`) and checked by Daniel's reviewer at 10:30 AM. At 10:34 AM the finder was rebuilt without Gemini (`bdea8c0`); that version has not been reviewed. Finder tested on two real phone photos, not from the real camera position |
| Drawing | Ben, Eddy | `skills/draw.py` on `main` writes a word or, since 2:46 PM, sketches a thing you name ("a cat"): Claude makes the strokes, 45 are cached in `drawings/`. Mock and simulation only: in Eddy's simulator, with a pencil modelled in a spring-loaded holder, a blind viewer named 27 of 28 sketches. Never tried with a real pen. Needs a pen holder and a taught paper grid |
| Feeding food and water | Daniel | Nothing in the repo yet. Planned for Saturday |

Wave and the personality moves (`skills/wave.py`, `skills/personality.py`) are on `main`, mock only.
They are not on the team's list, so they are not blocks here. If there is arm time, a celebrate
after a good run or a droop after a crash costs no script time.

## The one rule

A skill is in the table demo only if it passes 4 runs out of 5 on the real arm at the Saturday
8:50 PM freeze. Anything that does not pass is cut from the script, not rehearsed harder.

## Open decisions for the four of you

1. The track: exactly one HackUMass category, at the initial submission (Saturday midnight). The
   team has not decided. With feeding back on the list, the Accessibility pitch has three skills
   behind it (feeding, fetching Duplo by voice, writing) and Geometry Dash is the odd one out. The
   Hardware pitch fits all four, but the arm is a kit and `PLAN.md` noted judges favour custom
   builds. Ben's agent leans Accessibility if feeding or Duplo passes the gate; that is an opinion.
2. The name. Eddy says it will not be "Helping Hand". The Devpost draft uses NAME as a placeholder.
3. How long a judge spends at a table. Nobody has confirmed it. See the time budget below: the
   four skills together do not fit in 90 seconds.

## Pitch outline (about 20 seconds of talking, the rest is the arm)

1. Who it is for, in one sentence. Draft for Accessibility: "Some people cannot reach, grip, write
   or feed themselves. This arm does those things when you press one key or say one sentence."
2. What it is: one low-cost arm, one dispatcher, a library of skills, a stop key that always works.
3. Cost line, with sources in `docs/devpost.md`: the bare motor kit for this arm launched at $240;
   a robotic feeding device is listed around $8,200 to $9,600; a wheelchair-mounted assistive arm
   was reported at about $35,000. Still to find out: what our assembled kit actually cost, which
   is likely well over $240. Do not say "$300 arm" and do not say it replaces those devices.
4. What is honest: which skills replay a recording and which use the camera. Say it before a judge
   asks.

## Time budget

| Skill | Rough time at the table | Where the number comes from |
|---|---|---|
| Geometry Dash, first section | about 20 s | A guess; set by how many taps are replayed. Jonathan or Daniel to correct |
| Duplo by voice | about 25 to 30 s | A simulated request took about 13 s end to end after Gemini was removed (Eddy, 10:34 AM), plus the real arm's travel. Not timed on the arm |
| Drawing a sketch | 60 to 70 s for a detailed one, plus about 13 s to generate one that is not cached | Eddy's simulator, 3:42 PM, after the drawings were made richer (14 to 36 strokes). Not timed on the arm. Too long for a short script: use a simple cached one or a name |
| Drawing a name | 31 to 54 s | Planned from the stroke plan at the default pen speed, not timed on the arm. "HI" 31 s, "HELLO" 35 s, "BEN" 42 s, "JONATHAN" 54 s |
| Feeding | unknown | Not built |

Three of these plus the pitch is already over two minutes. So there are two scripts: a short one
of two skills for a judge in a hurry, and the full one. Which two go in the short one is decided
at the freeze by which passed the gate most cleanly.

## Table script (blocks stand alone; drop any that failed the gate)

| # | Trigger | What the judge sees | If it fails | Owner |
|---|---|---|---|---|
| 1 | Teammate speaks | The one-sentence pitch | | Ben |
| 2 | Teammate runs `geometry_dash`; the keypad listener restarts the level | Arm taps through the start of Stereo Madness, holds included. A teammate presses stop (Z) once on purpose and the arm freezes | Show the recorded clip | Jonathan, Daniel |
| 3 | Judge says "pick up the red brick" or "put the roof next to the purple brick" | Arm picks the piece from the mat and hands it over or sets it down. If two match, it asks "which one?" | Typed request; then a taped-spot pick | Eddy, Daniel |
| 4 | Judge names a thing to draw, or gives their name | Arm sketches it, or writes the name, on a card the judge keeps | Draw one of the cached sketches; then hand over a card made earlier | Ben, Eddy |
| 5 | Teammate says "feed me" | Arm scoops and holds the spoon out, short of the face; the teammate leans in. Water: a lidded cup with a straw | Skip it. Do not improvise near a person | Daniel |
| 6 | Teammate speaks | Cost line, and what is next | | Ben |

Notes on the blocks:

- Block 2 shows the stop key on purpose. A judge who sees the arm stop on command trusts the rest.
- Block 3: a placement whose destination the camera does not find should now be refused and said
  out loud. Having the destination on the mat is not a guarantee it is found, so rehearse a
  refusal as well as a success.
- Block 3 has no offline path for speech or typed sentences since 11:10 AM (`a620d95`): keyword
  matching was removed, so both picking the skill and picking the object need the Anthropic API.
  If the network or the API is down at the table, the only fallbacks are the keypad keys and a
  typed dispatcher command with a grid position, `run fetch {"u": 0.5, "v": 0.5}`. Rehearse that
  one. A reviewer finding on this version was open at 11:20 AM: a malformed placement reply from
  the model can still turn into a plain handover.
- Block 3 needs two keys on the demo machine: OpenAI (boxes and speech) and Anthropic (choosing and
  routing). Gemini was removed at 10:34 AM. Keep pieces 9 to 10 cm apart: in simulation the open
  jaws knocked neighbours at 6 cm. Keep pieces apart on the mat (two touching pieces come back as one box), avoid
  thin plates and hollow pieces, and have the typed request ready: the hall will be loud, and the
  microphone has been tried once, in a quiet room.
- Block 4: a sketch the judge names needs the Anthropic API and 10 to 20 seconds before the pen
  moves. The 45 cached sketches in `drawings/sketch_*.json` skip that generation step, so offer the
  judge a short list ("a dog, a robot, a dragon...") if the network is slow. They are not
  network-free: a spoken or typed sentence still goes to the model first to pick the skill.
- Block 4, the pen holder (Eddy's simulator, 3:42 PM; a lead to test, not a fact about the arm):
  a pencil pinched in the bare jaws swings; held rigidly it needs the pressing depth right to half
  a millimetre, which a hand-taught grid will not give; in a holder where it can slide up about
  8 mm against a light spring, aimed 2 mm into the paper, no ink was skipped. So the holder
  should let the pen slide and spring back. A felt tip gives a little of the same effect by itself.
- Block 4 is slow at the default pen speed. Options once the pen works on the arm: raise
  `PEN_SPEED` if the writing stays legible, or write one initial live and hand over a full-name
  card made earlier.
- Block 5, feeding, is done on a teammate, never on a judge. The rules from `PLAN.md` stand: the
  arm stops short of the face and the person leans in, speed is capped, dry food that scoops
  without precision, a cup a third full with a lid and straw, and one person on the power switch.
  It goes in only if it passes the same 4 of 5 gate.

## When something breaks at the table

Press the stop key (Z) and say what failed in one sentence. Then it depends on the failure:

- Understood and harmless (missed the object, the judge spoke too quietly): a teammate types `home`
  at the dispatcher, and the block runs once more. Home is a typed command, not a keypad key.
- Not understood, or the stop key did not stop it: use the power switch with someone supporting the
  arm, and move to the next block. Do not home and retry a failure nobody can explain.

If a block fails twice, move on. The backup video stays open in a browser tab.

## Table setup checklist

- Arm clamped to the table, mat taped down, camera fixed. Nothing that was calibrated may move.
- For the Duplo block, Eddy's setup list (`notes/eddy.md`, "From the simulator to the real arm",
  1:08 PM): a camera fixed about 50 cm straight above the table, seeing the whole grid, with the arm
  out of view at home; a taught 4 by 4 or 5 by 5 table grid and a handover pose; the grid's four
  corners clicked in the camera picture; and 15 settings measured once on the real arm (gripper
  open and closed, wrist range and direction, grid size, jaw and held-brick offsets, layer gap,
  camera height, arm base position). If the camera or the arm moves afterwards, redo the corners.
  As of 1:10 PM none of this had been reported done, and no overhead camera had been mounted.
- Stop key within reach of a teammate at all times, and one person on the power switch.
- Cards and a capped marker. Dry food, a bowl with a non-slip base, a lidded cup with a straw.
- A lamp, a power strip, and a phone hotspot for the model calls.
- `.env` on the demo machine with the OpenAI and Anthropic keys. Dispatcher started and `home` run before the
  first judge arrives.
- Backup video loaded.

## Submission checklist

| When | What | Owner |
|---|---|---|
| Sat 8:50 PM | Feature freeze. Track and name decided. Script cut down to skills that passed the gate | Everyone |
| Sat by 11:00 PM | Initial Devpost submission: title, one track, draft text, repo link. Repo made public | Ben |
| Sat night | Backup video of real runs, filmed during the hacking period | Ben |
| Sun by 8:00 AM | Final Devpost text, open source list, all four teammates listed | Ben |
| Sun 9:00 AM to 12:30 PM | Table set up, script rehearsed out loud with a timer, three times | Everyone |

Still to confirm with an organizer: whether the final deadline is 9:00 AM or 10:00 AM, and how long
each judge spends at a table.
