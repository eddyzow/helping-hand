# Demo script and pitch outline

Kept by Ben's agent (demo and pitch; Eddy is managing Devpost). Rebuilt Sat Nov 14, 6:30 PM around the Steady
Hand pivot in `newcontext.md` (merged 6:27 PM, "agreed by all four of us"; Ben confirmed that to his agent at 7:01 PM). Ben has
not yet read this version line by line. The previous script is in git at `dabdbb1`.

## What we are showing

Steady Hand: a person whose hand shakes moves the small leader arm, and the follower arm copies the
movement with the shake filtered out. One line: "your hand shakes, the arm does not."

Why this and not the earlier plans, from `newcontext.md`: everything that worked on the real arm
used positions a person supplied; everything that failed needed the camera to find an object to
within millimetres. Here the person does the aiming.

## State of each piece at 6:45 PM (from `newcontext.md`; nothing here was run by Ben's agent)

| Piece | Evidence so far | Passed 4 of 5 on the arm? |
|---|---|---|
| Plain leader-to-follower teleoperation (`teleop_sync.py`) | Ran on both real arms | Not counted |
| First test of Steady Hand with a real hand | Reported in `docs/steady-contract.md` on `daniel/arm-core` (owner's report, read at 7:35 PM; no shake numbers given). It ran, and showed six problems: the arm stopped following after 283 s because hold was on and nothing on screen said so; the follower does not reach as far as the hand moves; the 3D view drew the arm through the table; the grip was all-or-nothing; the 2 Hz filter lags about 0.16 s and "felt slow"; the page looked generic. A second version of the controller is planned against those | One run, not counted |
| Tremor filter (`steady.py`, `skills/steady.py`) | Synthetic tests with nominal timing: a 0.5 Hz reach passes at 94 percent, a 6 Hz shake is cut by 90 percent. Run once with a real hand (see the row above); no shake numbers from that run. Standalone `steady.py`: all nine findings reproduced on fake devices were fixed in `dfa82a4` and verified on fakes at 6:53 PM (stop during a leader read, hold, torque kept on after a fault, bad offsets and readings refused, sample clock). Not established by that: real stop latency, grip safety, meter accuracy with uneven timing, calibration. Dispatcher `skills/steady.py`: its two findings (start-up speed, leader opened on the follower's port) were fixed in `481ee13` and verified on fakes at 6:57 PM; by Jonathan's own note it still lacks the standalone version's elbow limit and claw protection, and it uses its own copy of the filter. The reviewer says neither branch is fully cleared, and the team has not said which one goes to the table | No |
| Dashboard (`steady_dashboard.html`) | Works against a simulated shaking hand: 16 mm hand, 1.9 mm arm, 88 percent removed. Since `dfa82a4` the arm's figure and its plotted line both come from the follower's own joint readings through a model of the arm, not from the commands sent. That is still not a measurement of the tip. The trend text's time wording was fixed in `b60266b` and verified on fakes at 7:22 PM. Open at 7:18 PM: when the dashboard gets an error from the arm program, or fails to draw, it still shows "Live from the arm" over old readings and leaves its buttons enabled. So if the numbers stop moving at the table, assume it is stale whatever the label says | No |
| Simulated comparison (`sim_steady.py`, Jonathan, 6:44 PM) | His report, not re-run by anyone: placing a brick with a simulated 3 degree, 5 Hz shake succeeded 1 time in 6 unfiltered and 6 in 6 filtered. The simulated servos are stronger and more exact than ours, and the "hand" is a script | Simulation |
| Take, hold, give back (`skills/hand.py`) | Grasp of a brick handed to the claw worked 4 times out of 4 on the real arm. The skill itself is mock-tested | Grasp only, 4 of 4 |
| Geometry Dash | Reported by Eddy in person at 7:17 PM, not yet confirmed in Jonathan's note: 3 full clears of Stereo Madness in 5 attempts, the last 3 in a row; the first two attempts reached 95 percent | Not yet: 3 of 5. One more clear on the next attempt makes the last five 4 of 5 |
| Gestures, offline voice phrases | Mock-tested; voice started once | No |
| Pointing, drawing, writing by the arm alone | Mock and simulation only | No |

## The one rule

A piece is shown live only if it passes 4 runs out of 5 on the real arm. The freeze is 8:50 PM
tonight. For Steady Hand a "run" should be defined before counting; a suggestion: a teammate shakes
the leader on purpose for ten seconds while holding a marker tip over a target, steady mode on, and
the run passes if the follower's shake reads under a set number of millimetres and nothing has to
be stopped. Daniel's lane publishes the counted numbers.

## What we may and may not say (from `newcontext.md`; these bind the pitch and the Devpost text)

- May say, once it is true: a prototype that removes a simulated tremor from a teleoperated arm,
  with numbers. Say which numbers are computed from commands and which are measured.
- May say, once it is true: tested with us shaking the leader on purpose. At 6:45 PM the filter has
  not been run with a person, so this cannot be said yet. Never: tested with patients.
- Do not say it makes anyone stronger. The arm lifts light things only.
- Do not say it measures force or torque. Load readings are the motors' own estimates.
- Do not say it treats or improves tremor, and do not call the tests therapy. Say "steadiness
  tests that measure and track".
- Geometry Dash is "three clears in five attempts, as reported" until Jonathan confirms the count
  and it reaches 4 of 5.

## Open decisions for the four of you

1. The track, due with the initial submission at 11:59 PM tonight. Steady Hand is an accessibility
   project in a way none of the earlier plans were, so Best Accessibility Hack fits. Best MedTech
   Hack is the alternative, but `PLAN.md` warned its judges may expect clinical grounding, and the
   claims list above rules that out. Ben's agent leans Accessibility. That reverses the 5:45 PM
   lean toward Hardware, because the project changed. All 28 prizes are in `docs/tracks.md`.
2. The name: "RobTop" for now (Ben, 7:27 PM, matching what Eddy reported the team wants). "Steady
   Hand" stays as the name of the tremor-filtering mode.
3. What counts as a passing run for Steady Hand (see "The one rule").
4. Settled at 7:14 PM (Eddy, in person; his agent did not verify it): the arms are the open-source
   SO-101 design, and the team 3D printed the parts and assembled both arms at the event. The pitch
   can say "we 3D printed and assembled both arms", and must credit the SO-101 design.

## Pitch (about 20 seconds; then the judge does the demo themself)

1. "Millions of people have hands that shake, from essential tremor or Parkinson's. Writing, or
   holding a cup, gets hard." [Check any number before saying one. None is sourced yet.]
2. "You move this small arm. The big arm copies you, with the shake filtered out."
3. [ONLY ONCE A FILTERED RUN WITH A PERSON HAS HAPPENED] "It is a weekend prototype. We tested it by shaking our own hands on purpose, not with
   patients, and it only handles light things."

## Table script (the judge is the demo)

| # | Who | What happens | If it fails |
|---|---|---|---|
| 1 | Teammate | The three pitch sentences | |
| 2 | Teammate | Filter OFF. Holds the leader and shakes it on purpose; the follower shakes too. The dashboard shows both lines moving | Skip to 3 |
| 3 | Teammate | Filter ON, same shake. The follower holds still while the hand keeps shaking. The dashboard shows the hand's shake and the filtered command; say "the arm's shake, from its own joint readings" | Stop key, one retry, then show the recorded clip |
| 4 | Judge | Takes the leader, shakes it, and watches the arm hold still. Then makes a slow deliberate move, and the arm follows | Teammate takes over |
| 5 | Teammate | "Hold this": hands the claw a marker or a Duplo brick; it holds it steady and gives it back | Skip |
| 6 | Teammate | Extras, only those that passed: Geometry Dash as proof of precise timing, a gesture, a voice command | Skip |
| 7 | Teammate | What it is not: not tested with patients, light objects only. What is next | |

Notes:

- Words for the switch, settled in Daniel's controller at 6:58 PM (`3b7b214`, verified on fakes):
  "filter off" lets the shake through for the comparison, "filter on" removes it, and "steady off"
  FREEZES the arm. So blocks 2 and 3 are "filter off" then "filter on". Never say "steady off" at
  the table unless you mean stop. Switch with the dashboard's filter button or a typed command; the
  voice path for these phrases has not been checked end to end.
- Filming and showing the screen: two findings mean a screen can show data that is not from the
  arm. The dashboard keeps "Live from the arm" over old readings after an error, and the new 3D
  demo page switches to made-up motion after one failed poll without saying so (reviewer, 7:53 PM).
  So the backup video has to show the real arms in the same shot as the screen, and nobody points
  at a screen as proof unless the arm beside it is visibly doing the same thing.
- Blocks 2 and 3 are the whole argument: the same shake with the filter off and on. Run them back
  to back every time. If only one thing is filmed tonight, film these two.
- Block 4 is what a judge remembers. It also means a stranger's hand on the leader, so the
  follower's speed cap and the stop key have to be tested with someone who is trying to break it.
  Do not put a judge on the leader while the review findings above are open: a missed stop, and a
  cleanup that asks the motors to switch off after a read error, are what a stranger is most
  likely to trigger. Putting a teammate on the leader instead does not close those findings or
  make a hardware run safe; they need fixing first. That call is Daniel's and his reviewer's.
- An idea, untested, that makes the result visible without a screen: tape a marker to the follower
  and have the person trace a line or sign a card through the leader, once with steady mode off
  and once on. Two lines on paper, side by side, that the judge keeps. It needs the marker holder
  Ben was building for drawing (taped to the jaw, sliding against a rubber band, not gripped) and a
  check that the pen reaches the paper inside the elbow's limit.
- Voice at the table: the negation bug ("don't release" released) is fixed on the voice candidate
  for all eleven reported phrasings, verified on fakes at 7:37 PM. That candidate is not on `main`,
  and nothing about a real microphone in a loud hall has been tried. Keep the stop key in reach
  and do not rely on voice for anything that releases an object.
- Writing on the real arm is back on the table (Eddy, 7:40 PM): the jaws grip hard enough, and the
  bare Sharpie was only too thin to hold, so the team will wind duct tape round it and try. Two
  things from the simulator to carry into that try: in the simulator a rigidly held pen only wrote cleanly when
  the pressing depth was right to about half a millimetre, so if real lines skip or drag, check
  depth first, as a guess to test and not a known cause (tape slip and the strokes are just as
  unmeasured); and the run sheet for the slot is in
  `newcontext.md` ("Drawing slot", 8:10 PM): writing first, sketches only if "HI" is readable.
- Only one program can hold the follower's serial port. `steady.py`, `teleop_sync.py` and the
  dispatcher cannot run together, so block 6 means stopping one and starting another. Rehearse
  that switch, or drop block 6.
- Latency is part of the feel: in the first real test the arm "felt slow". A second version of the
  filter (a higher cut-off plus a notch at the shake's own frequency) is on Daniel's branch. On
  synthetic input at 50 samples a second it trails by about 86 ms where the first trailed by about
  137 ms, and leaves no measurable shake where the first left 12 percent. At 25 samples a second
  the notch cannot work, and since `b710d2a` (verified on fakes at 8:14 PM) the new version then
  falls back to the old 2 Hz filter, so it is no worse than the first: 12 percent left. Which case
  the real arm is in depends on its loop rate, which nobody has measured. Do not quote the
  50-sample numbers as the arm's. Say the arm trails the hand slightly; do not call it instant.
- From the same test: the arm appeared to die because hold was on and nothing said so. At the
  table, whoever runs the laptop says out loud whenever hold or stop is on, until the screen does.
- The follower reaches less far than the hand moves. Keep the demo's movements small and near the
  middle of the workspace; a big sweep will look like the arm is not following.

## Facts about the real arm that the demo has to respect (from `newcontext.md`)

- Reported by Daniel at 8:27 PM, not seen by anyone else: the follower's wrist-roll motor is
  overheating and sending garbled replies. His controller now leaves that joint out: it does not
  follow the leader's wrist roll, and it is not actively held when Hold is on. So at the table the
  wrist will not rotate with the hand, and "Hold" freezes five joints, not six; say so if asked.
  The wave skill is a wrist-roll swing, so do not run it. `skills/personality.py` no longer uses
  wrist roll in any move (changed 8:35 PM, mock only). Writing keeps the wrist at one angle anyway.

- The follower's elbow stops at about +65 degrees, because its calibration recorded only part of
  its travel. This, not weak motors, is the recorded cause of today's "weak grip" and
  wrong-distance reports. Recalibrating shifts every taught pose and needs Daniel's go-ahead.
- Light objects only: nothing heavier than a marker or a Duplo brick.
- On the arm laptop the follower is COM3 and the leader COM4, run on Windows, not WSL.

## When something breaks at the table

Press the stop key and say what failed in one sentence. If it is understood and harmless, reset
and run the block once more. If it is not understood, or the stop key did not stop it, use the
power switch with someone supporting the arm, and move on. Do not retry a failure nobody can
explain. If a block fails twice, move on. The backup video stays open in a browser tab.

## Table setup checklist

- Both arms clamped, facing the same way, with room around the follower for a stranger's elbow.
- Leader on its 5 V supply, follower on 12 V. Never the 12 V supply on the leader.
- Stop key within a teammate's reach at all times, and one person on the power switch.
- Dashboard open on a screen the judge can see from the leader.
- A marker and a Duplo brick for "hold this". Cards and tape if the two-lines idea is used.
- A power strip. No network is needed for the core demo; a hotspot only if voice extras are shown.
- Backup video loaded.

## Submission checklist

| When | What | Owner |
|---|---|---|
| Sat 8:50 PM | Feature freeze. Track and name decided. Script cut to what passed the rule | Everyone |
| Sat by 11:00 PM | Initial Devpost submission (due 11:59 PM): title, one track, draft text, public repo link under "Try it out" | Eddy (he is managing Devpost) |
| Sat night | Backup video: the same shake with steady mode off and on, filmed during the hacking period; under 3 minutes if uploaded | Ben |
| Sun by 8:00 AM | Final Devpost text with the real numbers, each labelled measured or computed, open source list, all four listed as contributors | Eddy |
| Sun 9:00 AM to 12:30 PM | Table set up, script rehearsed out loud with a timer, three times, once with an outsider on the leader | Everyone |

Still to confirm with an organizer: whether the final deadline is 9:00 AM or 10:00 AM, and how long
each judge spends at a table.
