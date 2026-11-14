# Demo script and pitch outline

Draft by Ben (Person 4), Sat Nov 14, 1:00 AM. This is a first draft for the team to change.
Nothing in it has run on the real arm yet. Event facts are from `AGENTS.md` and `PLAN.md`.

## The one rule

A skill is in the table demo only if it passes 4 runs out of 5 on the real arm at the
Saturday 8:50 PM freeze. Anything that does not pass is cut from the script, not rehearsed harder.
Three skills that work beat six that sometimes do.

## Open decision: the track (needs all four people, before Saturday midnight)

We must pick exactly one HackUMass category at the initial submission.

| Option | The pitch it needs | Demo order it needs | Weak point |
|---|---|---|---|
| Best Accessibility Hack | One button or one sentence runs a physical task for someone with limited hand use | Fetch first, then write, then games as "it is also fun" | Geometry Dash does not fit; fetch must work live |
| Best Hardware Hack | A desk robot with many skills on one dispatcher | Any order, lead with the most reliable skill | The arm is a kit, and `PLAN.md` already noted judges favour custom builds |

Ben's recommendation: Accessibility, if fetch passes the gate. Reason: a single key that triggers
a physical task is a real access method (switch access), and the category is mostly apps. If fetch
does not pass by the freeze, switch to Hardware and lead with keypad skills. This is an opinion,
not a measurement. Eddy leans Hardware (`notes/eddy.md`).

## Pitch outline (about 20 seconds of talking, the rest is the arm)

1. Who it is for, in one sentence. Draft: "Some people cannot reach, grip or write. This arm does
   those things when you press one key or say one sentence."
2. What it is: one low-cost arm, one dispatcher, a library of skills, a stop key that always works.
3. Cost line. TO VERIFY before judging: what our kit cost, and the price of one commercial
   assistive feeding or fetching device. Do not say a number we have not looked up.
4. What is honest: which skills are hard-coded and which use the camera. Say it before a judge asks.

## Table script (target 90 seconds, each block stands alone)

Judges score Innovation, Functionality, Practicality and Presentation. Functionality is what they
see work, so blocks are ordered most reliable first. Drop any block that failed the gate.

| # | Time | Trigger | What the judge sees | If it fails | Owner | State today |
|---|---|---|---|---|---|---|
| 1 | 0:00 | Teammate speaks | The one-sentence pitch | | Ben | Draft above |
| 2 | 0:10 | Judge presses the wave key (X) | Arm waves. Then judge presses stop (Z) mid-move and it freezes | See "When something breaks" | Daniel | Mock only |
| 3 | 0:25 | Judge says "bring me the red brick" | Arm picks the brick from the mat and holds it out | Use the taped-spot fetch instead | Eddy, Daniel | On two real phone photos the finder points accurately at the object it picks, but it picks one of two look-alike red bricks without saying so and missed the red bricks in one photo (Eddy's check at 1:30 AM, which corrected an earlier 15 of 16). The free Gemini key rate-limits after about 15 calls in a burst. Fetch skill mock only and held out of `main` |
| 4 | 0:50 | Judge says or types their name | Arm writes it on a card the judge keeps | Hand over a card it wrote earlier | Ben, Eddy | `skills/draw.py` on `main`, mock only. No pen holder and no taught paper grid yet |
| 5 | 1:15 | Teammate runs `geometry_dash`; the keypad listener restarts the level | Arm taps through the start of Stereo Madness, holds included | Show the recorded clip | Jonathan, Daniel | On `main` as a dispatcher skill (`183db5e`), using the taught `tap_key` pose. Mock and simulation only; tap delay on the real key not yet measured |
| 6 | 1:30 | Teammate speaks | Cost line, and what is next | | Ben | |

Notes on the blocks:

- Block 3 only works at the table if the judge cannot ask for an ambiguous object. Until the finder
  handles look-alikes, put out objects that differ in colour or kind (one red brick, not two), and
  space the requests so the Gemini key is not rate-limited.
- Block 2 shows the stop key on purpose. A judge who sees the arm stop on command trusts the rest.
- Block 4 is slow. Planned times from `skills/draw.py` at the default `PEN_SPEED` (computed from
  the stroke plan at 1:40 AM, not timed on the arm): "I" 11 s, "HI" 31 s, "HELLO" 35 s, "EDDY" 36 s,
  "BEN" 42 s, "JONATHAN" 54 s. Every real name is over the 25 seconds this block has. Options, to
  decide once the pen works on the arm: start the writing first and talk over it; raise `PEN_SPEED`
  if the writing stays legible; or write one initial live and hand over a full-name card made earlier.
- Feeding is not in the script. It is the riskiest skill near a person and no part of it exists yet.
  Add it only if it passes the gate and the team agrees.
- Personality moves (nod, celebrate, droop) attach to results: celebrate after a successful fetch,
  droop after a Geometry Dash crash. They cost no script time.

## When something breaks at the table

Press the stop key (Z) and say what failed in one sentence. Then it depends on the failure:

- Understood and harmless (missed the object, the judge spoke too quietly): a teammate types `home`
  at the dispatcher, and the block runs once more. Home is a typed command, not a keypad key.
- Not understood, or the stop key did not stop it: use the power switch with someone supporting the
  arm, and move to the next block. Do not home and retry a failure nobody can explain.

If a block fails twice, move on. The backup video stays open in a browser tab.
(Corrected 12:55 AM from Daniel's note: the first draft said to press home and retry every time.)

## Table setup checklist

- Arm clamped to the table, mat taped down, camera fixed. Nothing that was calibrated may move.
- Stop key within reach of a teammate at all times, and one person on the power switch.
- Cards and a capped marker for block 4. A lamp. A power strip. A phone hotspot for the Gemini calls.
- Dispatcher started and `home` run before the first judge arrives.
- Backup video loaded.

## Submission checklist

| When | What | Owner |
|---|---|---|
| Sat 8:50 PM | Feature freeze. Track decided. Script cut down to skills that passed the gate | Everyone |
| Sat by 11:00 PM | Initial Devpost submission: title, one track, draft text, repo link. Repo made public | Ben |
| Sat night | Backup video of real runs, filmed during the hacking period | Ben |
| Sun by 8:00 AM | Final Devpost text, open source list, all four teammates listed | Ben |
| Sun 9:00 AM to 12:30 PM | Table set up, script rehearsed out loud with a timer, three times | Everyone |

Still to confirm with an organizer: whether the final deadline is 9:00 AM or 10:00 AM, and how long
each judge spends at a table. The 90 seconds above is our assumption, not a stated rule.
