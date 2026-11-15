# Demo script and pitch outline

Kept by Ben's agent (demo and pitch; Eddy is managing Devpost). Rebuilt Sat Nov 14, 6:30 PM around the Steady
Hand pivot in `newcontext.md` (merged 6:27 PM, "agreed by all four of us"; Ben confirmed that to his agent at 7:01 PM). Ben has
not yet read this version line by line. The previous script is in git at `dabdbb1`.

## Two pitches are on the table (Sun 3:40 AM). The team has to pick one.

**A. Multipurpose desk arm** (Eddy's direction, 3:32 AM; not yet agreed by all four). RobTop is
pitched as one cheap arm with many jobs, not as Steady Hand and not as MedTech. Written out just
below.

**B. Steady Hand** (the 6:27 PM plan, "agreed by all four"). The rest of this file from "What we
are showing" onward.

Ben's agent's read, as an opinion: A matches the evidence better. By the records, drawing and
Geometry Dash have run on the real arm repeatedly; Steady Hand has run once with no shake
numbers. Under A it becomes one of four tests and does not have to carry the pitch. The fitting
track for A is Best Hardware Hack, and "we 3D printed and built it this weekend" answers the
earlier worry that the arm is only a kit. Under B the track is Accessibility. Ben has not weighed
in; he was asleep when this was written.

### Where Pitch A stands at 4:20 AM (from Eddy's note; Ben has not weighed in)

Eddy says building is over and the rest of the night is the demo. His timeline, with the final
Devpost due 9:00 AM and the team working to 8:00:

| When | Arm laptop | Eddy |
|---|---|---|
| to 4:45 | Second Geometry Dash level, hard stop at 4:45 whether or not it clears | Voiceover; start cutting existing clips |
| 4:45 to 5:15 | Record and replay with a Cheeto or brick between two taped marks; film the hand guiding, then the arm alone | Cutting |
| 5:15 to 5:45 | Unplug the camera and try each piece; time a fresh camera setup; photograph the rig | Last two clips |
| 5:45 to 6:45 | Rehearse switching between programs (only one can hold the arm) | Captions, export, watch it through, upload |
| 6:45 to 8:00 | Working code onto `main` | Devpost text, repo public, submit |

Video order: opening, drawing, tic-tac-toe, Geometry Dash, teach by showing, close. Closing line:
"Everything you just saw was the same arm, and it's less than two days old. What would you teach
it?" Teach by showing moves an object between two spots on the table and never toward a person,
with a teammate on the power switch.

Two things to notice. Hand control with the tremor filter is not in that video order, so Steady
Hand is no longer part of the pitch as Eddy has it; if the Devpost track was set to Accessibility
on that basis, it no longer matches. And "what would you teach it?" is a better close than "what
would you ask it to do?", because teaching by showing is something the arm can actually be shown
doing.

### Pitch A, as Eddy worded it (revised by him at 3:55 AM)

Eddy does not want the demos called separate "skills" or compared to apps: that makes the arm
sound as if it only does what has been installed. The arm is pitched as general purpose, and the
demos are some of what it has done so far.

1. First ten seconds: "RobTop is a robot arm that sits on your desk. We built it to take on
   whatever job is put in front of it. We 3D printed and built it this weekend from an open-source
   design."
2. Each demo says what it shows about the one arm: it is accurate (drawing), it can see
   (tic-tac-toe), its timing is exact (Geometry Dash), it works with a person (hand control with
   the filter). Abilities of one arm, not a list of programs.
3. Geometry Dash for a judge who does not know it: "a game with one button; a cube runs forward by
   itself and you press a key to jump; one late press sends you back to the start; a level lasts
   about ninety seconds." Then: it is the timing test, and the arm plays from memory and does not
   watch the screen.
4. Close: "This is some of what it has done in two days. What would you ask it to do?"
5. Eddy's own limits on this: do not claim it can do anything at all. It lifts light things only,
   and the object-finding tasks did not work. "Built to", "so far" and "some of" keep it true.

One caution from Ben's agent, as an opinion: the closing question invites a judge to name a task,
and the arm cannot take a new task at the table. Each demo was built and tuned by hand over hours.
Have an answer ready that is true, for example "tell us and we would spend an evening teaching
it; here is what that looked like for drawing", or close on the first sentence alone.

### Pitch A at the table

| Test | Live at the table? | Evidence so far |
|---|---|---|
| Timing: Geometry Dash | Yes; needs no overhead camera | Three clears recorded at 11:37, 11:46, 11:51 PM, with deaths among the attempts. No count out of five consecutive tries |
| Working with a person: hand control with the tremor filter | Yes, if it has run; needs no camera | One real-hand run, no shake numbers. Controller cleared 22 fake-device checks |
| Accuracy: drawing | Only if the overhead camera is rebuilt at the table; otherwise video | House and flower drawn, per Daniel's record |
| Seeing and responding: tic-tac-toe | Only with the overhead camera; otherwise video. Typed moves do not remove the camera: the program still needs it to start, to fit the drawn grid and to check its own move. Typing only replaces reading the person's X | One completed game on the earlier version; one illegal move later; current version unplayed on the arm |

So with the rig packed, the table could show two tests live and two on video. Say that plainly.
This table is a presentation plan, not a clearance: neither live test has yet passed 4 of 5
consecutive runs on the arm.

### Proposed fifth piece: teach by showing (Eddy, 4:05 AM; not built into a demo yet)

A person guides the second arm once (pick a Cheeto off a marked spot, bring it to a marked spot),
then the follower repeats it with nobody touching anything, using the record and replay already
in the repo. It would answer "why is feeding not automated", and it is the only piece that picks
something up. Film both halves in one take: the hand guiding, then the arm alone.

Before it goes near a person, the rules this team wrote on Friday in `PLAN.md` still apply, and
they matter more here because a replay is blind: it goes to where the person was during the
recording whether or not they are still there.

- The arm does not move toward a face. The recorded motion ends at a marked spot short of the
  person, and the person leans in to take the food.
- Record it slowly; the replay runs at the recorded speed.
- The keypad stop key does NOT stop these programs. `arm.py record` and `replay`, and
  `teleop_sync.py --record`, talk to the arm directly and do not listen for the keypad's stop
  (reviewer, 4:08 AM, from reading the source). There is no validated keypad stop for these scripts. Ctrl+C in
  their terminal is their software interrupt; how the arm responds to it, and whether cleanup
  runs, has not been tested. The power switch, with someone supporting the arm, is the other
  way to stop. Until a stop has been tried and seen to work on the chosen path, do not run a
  replay with a person in the arm's reach.
- The person being fed is a teammate, never a judge.
- The two recorders are not interchangeable. `arm.py record feed` writes `motions/feed.json`,
  which `arm.py replay feed` reads. `teleop_sync.py --record feed` (on `daniel/arm-core` only)
  writes a different format to `poses/taught/feed.json`, which `arm.py replay` cannot play. Both
  also skip the new wrist-roll power-down. Whoever has run one on the real arm should name the
  matching record and replay pair in a note; `arm.py` still says untested on hardware.

### What Pitch A may claim (Eddy's own checks, 3:32 AM)

- "About a millimetre": that is Daniel's house measurement after the photo is aligned to the plan.
  Say "about a millimetre from the planned shape".
- "The best you can do is a draw": needs a filmed game with no misread square. What the reviewer
  checked is narrower than "cannot lose": every legal reply by the person from an empty board,
  against the program's own choice of moves (521 reachable positions, 123 distinct
  finished boards per version), with no win for the person. It did not test arbitrary or broken board states, and
  the camera can misread a square.
- "It finishes the level" is fine. "Every time" is not.
- "Ask for a skill in plain words" covers the dispatcher's skills. Tic-tac-toe and the drawing loop
  are scripts in `demo/`, not routed skills, so do not say they are started by voice.
- "We 3D printed and built it this weekend": credit the open-source SO-101 design in the same breath.

## What we are showing (Pitch B: Steady Hand)

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
| Geometry Dash | Per Daniel's session record: Stereo Madness completed at 11:37, 11:46 and 11:51 PM, with four deaths at 40.3 percent and two at 75 seconds among the attempts. Earlier, Eddy reported 3 clears in 5. No single count of clears out of consecutive attempts has been written down | Not shown: needs 4 clears in 5 consecutive attempts, written down |
| Gestures, offline voice phrases | Mock-tested; voice started once | No |
| Drawing by the arm alone | Real, per Daniel's session record: a house and a flower with a Sharpie in the claw, using `drawloop/` and a webcam (numbers above). Each needed a taught page, a height measurement and, for the house, ten correction rounds. Writing a name and sketches from `draw.py` are not yet fed through it. `skills/draw.py` and `skills/write.py` on `main` remain mock and simulation only | Not counted: one flower run, ten house rounds |
| Pointing by the arm alone | Mock and simulation only | No |

## At the freeze (Sat 8:50 PM), as the repo records it

- Steady Hand: tried once with a real hand; six problems found; no shake numbers recorded. The
  controller is on `daniel/arm-core`, not on `main`. The reviewer's latest pass (8:50 PM) holds it
  as high priority on fake-device findings in its new link-recovery code: a move that failed to
  send is retried after Stop has arrived; after a brief read loss a held arm takes new targets
  while still showing Hold; a 20-second recovery window can run to a minute; and the page says
  "Following your hand" while the arm is in fact unavailable.
- Geometry Dash: 3 clears in 5 attempts, as reported by Eddy; not confirmed in Jonathan's note.
- Writing with a taped marker: not tried. Gestures: never run on the arm.
- The follower's wrist-roll motor is reported faulty.
- Nothing has passed the rule below. After a freeze the work is fixing and counting, not adding.

Since the freeze:

- 9:29 PM: the reviewer closed every finding it had reproduced on the standalone Steady Hand
  controller (`3378d33`): all 22 fake-device checks pass, including Stop after a failed send, held
  targets through a read loss, the recovery deadline, and the link-loss message on the page. That
  is the software side only. It says nothing yet about the real arm: holding, torque coming back
  after a power dip, the faulty wrist-roll motor, or timing on real hardware. The controller is
  still on `daniel/arm-core`, not on `main`.
- Sun 12:20 AM: the first written record of a real-arm session, `docs/arm-session-2026-11-14.md` on
  `daniel/arm-core`, by Daniel's agent on the arm laptop. Everything in the next four points is
  that record's own measurement, not checked by anyone else; the reviewer looked at three of its
  photos and says they show recognisable drawings with visible line errors.
  - The arm draws on paper with a Sharpie held in the claw. A house and a flower were drawn on A4
    and scored by a USB webcam. House, after ten rounds of camera correction: 97.6 percent of the
    intended points had ink within 2 mm, and the ink sat 1.0 to 1.2 mm from the plan on average; it
    never passed the session's own 1.0 mm gate. Flower, one run: 9 of 9 strokes, 90 percent, 1.04
    mm. Those scores are taken after the photo is aligned to the plan (rotation, shift and
    mirroring allowed) and leave out ink more than 10 mm away, so they are not absolute placement.
  - It does this with new code in `drawloop/`, not with `skills/draw.py`. On the grid taught in
    that session, the record reports the blended "pen down" layer sat about 2 cm above the paper
    mid-page and a circle came out as an oval. `skills/draw.py` on `main` has none of the
    session's corrections (confirmed by reading the source) and has never been run on the arm, so
    its real behaviour is unknown, not measured as failing. Do not offer it for live use.
  - Geometry Dash: Stereo Madness completed at 11:37, 11:46 and 11:51 PM. It also died at 40.3
    percent four times, and twice at 75 seconds when started from the level-complete screen.
  - Hardware: the claw motor reached 62 C gripping continuously (it cuts out at 70 C); the
    wrist-roll motor's garbled replies used to end every skill until reads were retried.
  That record says nothing about Steady Hand. There is still no filter-off and filter-on
  measurement from the real arm.
  The reviewer holds the new drawing code for four fake-device findings (12:26 AM), among them a
  saved depth value that is not range-checked and cleanup that skips disconnecting after an error.

## Film before the camera rig is packed (Eddy, Sun 3:06 AM)

The overhead camera has to come down before judging and may not go back up the same way, so
anything that needs it may not run at the table. Film these now, real arm and screen in one shot,
each under a minute, saying on camera what it is:

1. The drawing loop drawing a house or flower, start to finish.
2. Tic-tac-toe against a person. Its code is on `daniel/arm-core` (`demo/`). Per the session
   record as the reviewer reads it (3:13 AM): one game with the earlier version completed, a
   later run drew an O on top of an X, and the current version, `ttt2.py`, has not been played on
   the arm. So film whichever version actually finishes a legal game, and say which. The reviewer
   holds this code on fake-device findings, including camera waits that ignore Stop.
3. A Geometry Dash clear, even though it needs no camera: it is the proof of the claim.
4. Steady Hand with the filter off and then on, same shake, if it runs.

Then, before packing: photograph the rig from two sides, write down the camera height and where
the arm base and paper sit, save the calibration files, and time one fresh camera setup.

What should run at the table with no overhead camera, as far as the notes show: Geometry Dash,
Steady Hand, take and hold, gestures. The quick drawings (`FAST=1` flower, house, heart) still
need the camera for their first and last photographs, so they are not a camera-free fallback.
Check each piece with the camera unplugged before packing.

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
  The wave skill is a wrist-roll swing, so do not run it. In `skills/personality.py` no move adds a
  wrist-roll offset any more (8:35 PM, mock only), but that does not isolate the motor: every
  dispatcher skill, gestures, Geometry Dash and writing included, still sends a target to all six
  joints, wrist roll among them, and the controller's leave-it-out policy applies only to the
  standalone Steady Hand program. Whether any dispatcher skill should run while that motor is
  faulty is Daniel's call. Update, Sun 3:45 AM: on `daniel/arm-core` (`5ad5d53`) the dispatcher's
  arm now switches the wrist-roll motor's torque off when it connects, unless `ROLL_POWER=1` is
  set; checked by the reviewer on a fake. That is not on `main` yet. The same branch has ten
  gestures of Daniel's that pass his reviewer's mock checks, home to home.

- The follower's elbow stops at about +65 degrees, because its calibration recorded only part of
  its travel. This, not weak motors, is the recorded cause of today's "weak grip" and
  wrong-distance reports. Recalibrating shifts every taught pose and needs Daniel's go-ahead.
- Light objects only: nothing heavier than a marker or a Duplo brick.
- On the arm laptop the follower is COM3 and the leader COM4, run on Windows, not WSL.

## Which stop works in which mode (as of Sun 4:28 AM; check this at the table before judging)

There is no single stop key any more. Know which one applies to what is running.

| What is running | How to stop it |
|---|---|
| Dispatcher skills in game mode (Geometry Dash) | Keypad Z, or type `stop` at the dispatcher |
| Dispatcher in show mode (gestures on the keypad) | NOT the keypad: on `daniel/arm-core` all three keys are gestures there (X dance, C high five, Z victory). Type `stop` at the dispatcher, or use its `arm_stop` helper |
| Steady Hand (`steady.py`) | Its own Hold, on the dashboard or by command |
| Standalone scripts: record and replay, the drawing loop, tic-tac-toe | No validated keypad stop. Ctrl+C in their terminal, untested; tic-tac-toe ignores Stop while it waits on the camera |
| Anything, if the above fails | The power switch, with someone supporting the arm |

A judge handed the keypad in show mode cannot stop the arm with it. A teammate stays at the laptop.

## When something breaks at the table

Stop the arm (see the table above for which stop applies) and say what failed in one sentence. If it is understood and harmless, reset
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
