# Demo script and pitch outline

Kept by Ben's agent (Person 4). Rebuilt Sat Nov 14, 5:45 PM after Eddy reported what the real arm
can and cannot do. The plan below is his agent's suggestion "for the team to decide"; it is written
up here so there is one script to argue with. The previous version is in git at `46a839e`.

## What the real arm can do (Eddy, reported 5:04 PM)

"The real arm is only strong enough to press a button (Geometry Dash). It cannot grip a pencil, and
it is not accurate enough to place blocks."

This is the first report from the arm about anything other than tapping. It has not been written
up with numbers by whoever ran it. Until it is, treat it as the working assumption: the demo is
built from skills that need neither grip strength nor millimetre accuracy.

## Skills, by whether they fit the real arm

| Skill | Needs | State at 5:45 PM |
|---|---|---|
| Geometry Dash (Jonathan, Daniel) | A light tap, good timing | Has run on the real arm. A 1:27 PM commit on Daniel's branch says "the arm completes Stereo Madness"; that is the owner's report, and no note says how many attempts or whether it was filmed. Replay skill is on `main`; the newer Windows-timed version is on his branch, held in review |
| Gestures: wave, nod, shake, celebrate, droop, dance (Daniel, Ben) | Free movement only | `skills/wave.py` and `skills/personality.py` on `main`, mock only. Never run on the arm. Joint directions and clearance around the taught `wave_up` pose are unchecked |
| Voice picks the skill (Eddy) | Network, Anthropic key | "play Geometry Dash", "wave", "stop". Works on a laptop; not run against the real dispatcher |
| Point at a named object (Eddy) | Camera, taught table grid; a couple of centimetres of accuracy; no grip | New `skills/point.py`, 5:36 PM. Mock and simulation only (three requests, each within 5 mm). Needs an overhead camera mounted, the table grid taught and its corners clicked. None of that exists yet |
| Teach by demonstration (Eddy, Daniel) | Leader arm | `arm.py record` and `replay`. Untested on hardware |
| Write a name with a taped-on marker (Ben, Eddy) | A felt tip that slides and springs back, taped to the jaw, not gripped; a taught paper grid | `skills/draw.py` and `skills/write.py` on `main`, mock and simulation only. Eddy rates this the riskiest and says to try it last. A first-try checklist is in `notes/ben.md` |

Cut from the live demo, per the same plan: picking up and stacking Duplo, feeding, anything that
grips a pencil. They exist in the simulator and can be shown as video, saying plainly that the
servos are the limit.

## The one rule

A skill is in the table demo only if it passes 4 runs out of 5 on the real arm at the Saturday
8:50 PM freeze. Anything that does not pass is cut from the script, not rehearsed harder. By that
rule, at 5:45 PM, only Geometry Dash is in.

## Open decisions for the four of you

1. Whether to adopt this plan. It is a suggestion from Eddy's agent, not a team decision.
2. The track, due with the initial submission at 11:59 PM tonight. Without fetching and feeding the
   Accessibility pitch has little behind it. The honest fit now is Best Hardware Hack, with the
   known weakness that the arm is a kit. This is Ben's agent's opinion and it reverses what this
   file said before, because the facts changed. All 28 prizes are in `docs/tracks.md`.
3. The name. Eddy says it will not be "Helping Hand". The Devpost draft uses NAME.
4. What we say we built. The fallback pitch in Eddy's note is "we printed and assembled the arm,
   built the leader and follower pair". `context.md` says the kit came pre-assembled. Whichever is
   true is what goes in the pitch, and the Devpost rules bar work done before the hacking period,
   so be exact about what was done this weekend.

## Pitch outline (about 20 seconds of talking, the rest is the arm)

1. What it is, in one sentence. Draft: "A desk robot arm you talk to: it plays a rhythm game by
   itself, points at what you name, and reacts, all through one dispatcher with a stop key."
2. What is real: Geometry Dash is the arm physically pressing a key in time. Say that first.
3. What is honest: the arm's servos are too weak to grip and not accurate enough to place things,
   so picking, stacking and drawing are shown in simulation. Say it before a judge asks. Judges
   score Functionality on what they see work.
4. Cost line, only if it helps: the bare motor kit for this arm launched at $240 (source in
   `docs/devpost.md`). Do not compare it with assistive devices now that fetching and feeding are out.

## Table script (blocks stand alone; drop any that failed the gate)

| # | Trigger | What the judge sees | If it fails | Owner |
|---|---|---|---|---|
| 1 | Teammate speaks | The one-sentence pitch | | Ben |
| 2 | Teammate says or types "play Geometry Dash" | The arm taps through Stereo Madness on the keypad, holds included. A teammate presses stop (Z) once on purpose and the arm freezes | Show the recorded clip | Jonathan, Daniel |
| 3 | Judge presses the wave key (X), or says "wave" | The arm waves; after a Geometry Dash run it celebrates or droops | Skip it | Daniel, Ben |
| 4 | Judge says "point at the red brick" | The arm reaches over and points at it, and the laptop says "That's the red brick" | Typed request; then skip it | Eddy |
| 5 | Judge gives a first name | The arm writes it on a card with a taped-on marker | Hand over a card made earlier, or skip it | Ben, Eddy |
| 6 | Laptop screen | Simulator video: picking, stacking and drawing, with the line "this is what the same code does when the motors are strong enough" | | Eddy |
| 7 | Teammate speaks | What is next | | Ben |

Notes on the blocks:

- Block 2 is the demo. Everything else is extra. Get one clean run filmed today: it is both the
  backup video and the proof of the claim. Block 2 also shows the stop key on purpose; a judge who
  sees the arm stop on command trusts the rest.
- Block 3 needs ten minutes on the arm: try the moves one at a time, gentlest first (`droop`,
  `nod`, `shake`, `dance`, `celebrate`), with someone on the stop key, and tell Ben's agent which
  joints go the wrong way. The tables at the top of `skills/personality.py` are one-line edits.
- Block 4 needs the most setup of anything left: an overhead camera fixed about 50 cm above the
  table, a taught table grid, and the grid's corners clicked (`notes/eddy.md`, 1:08 PM). It needs
  the network: sentences go to the Anthropic API to pick the skill and the object, and the boxes
  come from OpenAI. With no network, the fallback is a typed `run point {"u": 0.5, "v": 0.5}`.
- Block 5: the marker is taped to the fixed jaw in a loose sleeve with a rubber band so it can
  slide about 5 mm and spring back; the gripper does not hold it (`PEN_SQUEEZE=0`). Ask for a first
  name: a name of four or more words is cut short by a known bug. Times from the stroke plan, not
  the arm: "HI" 31 s, "BEN" 42 s. Eddy's simulator suggests sketches fall apart once the pen is
  more than about 5 mm off the line; the first real square drawn on the arm will say where we are.
- Block 6 is the simulator. Say it is a simulator. `sim.py` and `sim_draw.py` produce the videos.

## Time budget

| Block | Rough time | Where the number comes from |
|---|---|---|
| Geometry Dash | 20 s for the opening, about 85 s for the whole level | The recorded macros end at 83 to 86 s. Jonathan or Daniel to say how much to show |
| Gestures | 5 to 10 s each | From the move tables; not timed on the arm |
| Pointing | about 20 s | 13 s for the models in simulation, plus the reach. Not timed on the arm |
| Writing a first name | 30 to 45 s | Stroke plan at the default pen speed |
| Simulator video | 20 s | Cut to fit |

A short script is blocks 1, 2 and 7. Nobody has confirmed how long a judge stays at a table.

## When something breaks at the table

Press the stop key (Z) and say what failed in one sentence. Then it depends on the failure:

- Understood and harmless (missed the object, the judge spoke too quietly): a teammate types `home`
  at the dispatcher, and the block runs once more. Home is a typed command, not a keypad key.
- Not understood, or the stop key did not stop it: use the power switch with someone supporting the
  arm, and move to the next block. Do not home and retry a failure nobody can explain.

If a block fails twice, move on. The backup video stays open in a browser tab.

## Table setup checklist

- Arm clamped to the table, keypad taped down under it, mat taped down. Nothing that was
  calibrated may move.
- Stop key within reach of a teammate at all times, and one person on the power switch.
- Game open and focused on the laptop the keypad is plugged into.
- For pointing: overhead camera fixed, table grid taught, corners clicked; three or four pieces
  that differ in colour, well apart.
- For writing: cards, a felt-tip marker in its holder, a taught paper grid, tape.
- A lamp, a power strip, and a phone hotspot for the model calls.
- `.env` on the demo machine with the OpenAI and Anthropic keys. Dispatcher started and `home` run
  before the first judge arrives.
- Backup video and simulator video loaded.

## Submission checklist

| When | What | Owner |
|---|---|---|
| Sat 8:50 PM | Feature freeze. Track and name decided. Script cut down to skills that passed the gate | Everyone |
| Sat by 11:00 PM | Initial Devpost submission (due 11:59 PM): title, one track, draft text, public repo link under "Try it out" | Ben |
| Sat night | Backup video of a real Geometry Dash run, filmed during the hacking period; under 3 minutes if it is uploaded | Ben |
| Sun by 8:00 AM | Final Devpost text, open source list, all four teammates listed as contributors | Ben |
| Sun 9:00 AM to 12:30 PM | Table set up, script rehearsed out loud with a timer, three times | Everyone |

Still to confirm with an organizer: whether the final deadline is 9:00 AM or 10:00 AM, and how long
each judge spends at a table.
