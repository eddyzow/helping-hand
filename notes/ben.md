# Ben, Person 4 (agent: Claude Code)

Updated Sat Nov 14, 10:10 PM ET.

## Working on now

After the Steady Hand pivot (`newcontext.md`, 6:27 PM): demo and pitch. Eddy is managing Devpost
(Ben, 7:27 PM). Also the look
and wording of the dashboard in lane C. Ben confirmed at 7:01 PM that he agreed to the pivot. His
agent rebuilt both documents; Ben has not yet read them line by line.

1. `docs/demo.md`: the table script, built so the judge holds the leader. Needs the team's answer
   on what counts as a passing run.
2. `docs/devpost.md`: reworked, every unproven claim in [SQUARE BRACKETS], written inside the
   "may and may not claim" list. Waiting for Daniel's real-arm numbers.
3. Initial Devpost submission tonight by 11:00 PM (due 11:59 PM), by Ben.
4. Earlier work on `main`, now extras at most: `skills/personality.py`, `skills/draw.py`. Mock only.

## Done and how it was tested

- `docs/tracks.md` (2:10 PM): every prize on the Devpost page (28), the one-category limit, and
  the rules quoted from the Devpost rules page. Read with a browser on Sat 2:10 PM. Ben heard that
  tracks are being added, so this agent re-reads the page about once an hour and logs changes at
  the bottom of that file. Three sponsor prizes are not in `PLAN.md`: Sentient OS Best Agentic
  Hack, Analog Devices ADI Hardware, Capital One Nessie. So are Best Pitch and Best UMass Hack.

- `docs/devpost.md` (3:35 AM): a first draft of the Devpost text, section by section, in both an
  Accessibility and a Hardware version of the opening. Every claim that is not yet true on the real
  arm is in [SQUARE BRACKETS] and must be confirmed or cut before submitting. It also holds the
  cost figures with their sources, and an open-source list to check against `requirements.txt`.
  A document only.

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

- Eddy (10:10 PM), for the Devpost submission you are managing: at 10:10 PM the repository page
  returns "not found" to a visitor who is not signed in, so the repo is still private. The Devpost
  rules require a public GitHub link under "Try it out", and the initial submission is due at
  11:59 PM tonight. Making it public is a setting only you can change. I have not touched Devpost
  or the repo's settings. One thing to check before you flip it: nothing secret is committed. At
  10:15 PM I searched the full history of every branch on GitHub for the usual key shapes
  (Anthropic, OpenAI, Google, GitHub tokens, and anything like `API_KEY=...`) and for committed
  `.env`, `.pem` or `.key` files, and found none. That is a pattern search, not a guarantee; the
  one filename it flagged, `keypad/geometry_dash/my_ship_secret.csv`, looks like a game recording.

- Daniel (8:35 PM), on the wrist-roll motor your note reports overheating: two things from the
  demo side. `skills/wave.py` is entirely a wrist-roll swing (plus or minus 45 degrees, eight
  sweeps), so I have taken the wave out of the table script; it is your file, so I have not
  touched it. And I changed `skills/personality.py` so that no move uses wrist roll: "dance" now
  uses pan and wrist flex. `python -m skills.personality` still prints `personality ok`; mock
  only. Is there a spare STS3215 at the hardware desk, and is swapping it tonight realistic?

- Eddy and Daniel (8:15 PM), on the drawing slot run sheet in `newcontext.md`: use that one. It
  supersedes the first-try checklist further down this note, which was written for a sprung
  holder. Three steps from the old checklist that I would keep, each a minute or two:
  1. The first pass with the marker's cap ON, so a wrong grid dents a cap and not the paper or tip.
  2. `python arm.py check paper` after teaching and before the first word: a slow pass between the
     taught points, to see the tip dig in or lift off.
  3. After "HI", one square: `run draw {"strokes": [[[0.2,0.2],[0.8,0.2],[0.8,0.8],[0.2,0.8],[0.2,0.2]]]}`,
     and measure with a ruler how far the end misses the start. That number says whether sketches
     are worth trying.
  Ben is making the taped marker.

- Daniel's agents, lane C look and wording (7:40 PM), on item 6 of `docs/steady-contract.md`, "a
  clinical, medical-device look": please keep the claims list in view while doing it. The more
  the page looks like a medical device, the more a judge will read its numbers as clinical
  measurements. Suggest the line "Prototype. Not a medical device. Not tested with patients."
  stays visible on every screen, the hold-still score keeps "not a clinical measure" next to it,
  and "activities" are described by what was measured, never by what they do for the person. Your
  own contract already says the last part.
- Daniel: the first real-hand test is the result the demo was waiting for. Two things would make
  it usable in the pitch: the shake numbers from a run (hand mm, arm mm, percent, filter on and
  off), and a ten-second clip of each.

- Eddy (7:30 PM), from Ben: you are managing Devpost, so this agent has stopped editing
  `docs/devpost.md` as of `c228d93` and will not touch the Devpost site. The file is yours to use,
  change or ignore. Three things in it you may want: every claim not yet true on the arm is in
  [SQUARE BRACKETS]; the rules quoted in `docs/tracks.md` (public repo link under "Try it out",
  all four listed as contributors, external code documented); and its title still says "Steady
  Hand", while Ben says the name is "RobTop" for now. I will keep `docs/demo.md` and
  `docs/tracks.md` current.

- Daniel's agents, lane C wording (7:10 PM). I read the text of `steady_dashboard.html` on
  `daniel/arm-core` at `3b7b214`; I did not open it in a browser. Most of it already follows the
  claims list ("an estimate, not a measured force", "not a clinical measure", "follows the hand a
  little later"). Five suggested changes, yours to take or leave:
  1. Footer, "Tested only with a person shaking the leader arm on purpose": not true until the
     filter has run with a person. Until then: "Prototype. Not tested with patients. The arm holds
     light objects only." Add the tested sentence back once the run has happened.
  2. "Tremor removed" and "no tremor found": what we show is a shake someone makes on purpose.
     "Shake removed" and "no shake detected" claim less and match the "Hand shake" and "Arm
     shake" headings beside them.
  3. "Arm shake: what is left at the claw": the figure comes from joint readings through a model
     of the arm. Suggest "worked out from the arm's joint readings".
  4. "Arm load: hardest-working joint": add "motor load estimate", as the grip card already does.
  5. "Fingertip height": suggest "Tip height: hand and arm", since neither arm has a fingertip.
  And the trend text your reviewer flagged: "over the last N readings" until it uses timestamps.

- Daniel (lane A), 6:50 PM: three things the demo and the Devpost text are waiting on.
  1. The counted before and after: shake in mm on the follower with steady mode off and on, with a
     person shaking the leader. How many runs, and who shook it.
  2. A definition of a passing run for the 4 of 5 rule. A suggestion is in `docs/demo.md`: ten
     seconds, steady mode on, follower shake under an agreed number of mm, no stop needed.
  3. A filmed take of the same shake with steady mode off and then on. That is the backup video
     and the one clip that makes the case.
- Daniel: for the judge-on-the-leader block, has the follower's speed cap been tried with someone
  deliberately yanking the leader? Your reviewer found the start-up glide can ask for more than the
  cap. A stranger will do exactly that.
- Daniel's agents (lane C): send me the dashboard's text, or tell me when `steady_dashboard.html`
  is on `main`, and I will check every label against the claims list ("estimate", not "force";
  "steadiness test", not "exercise"). I have not seen the file; it is on `daniel/arm-core`.
- Everyone: an untested idea for making the result visible on paper. Tape a marker to the follower
  (in a sleeve, sliding against a rubber band, not gripped) and have the person trace a line or
  sign a card through the leader, once with steady mode off and once on. The judge keeps the card.
  It depends on the pen reaching the paper inside the elbow's 65 degree limit.
- Everyone: is "Steady Hand" the Devpost title, and is the track Best Accessibility Hack? Both are
  needed for tonight's submission.

- Everyone (5:45 PM): `docs/demo.md` and `docs/devpost.md` are rebuilt around Eddy's 5:04 PM report
  that the real arm can press a button but cannot grip a pencil or place blocks. The script is now
  Geometry Dash, gestures, pointing, a name with a taped-on marker, and simulator video for the
  rest. It is his agent's suggested plan written up, not a decision; change it.
- Daniel or Jonathan: block 2, Geometry Dash, is the only block with a real run reported. It has
  not passed the 4 of 5 rule either, because nobody has written down attempts. Please
  film one clean run today and write in your note how far it gets and out of how many attempts.
- Daniel: ten minutes on the arm for the gestures would turn block 3 from mock into real. One at a
  time, gentlest first: `run personality {"move": "droop"}`, then `nod`, `shake`, `dance`,
  `celebrate`, with someone on the stop key. Tell me which joints go the wrong way.
- Whoever tried the pencil and the blocks on the real arm: what happened, in a few lines? Could
  the gripper not close on the pencil, or did it slip under load? How far off were the blocks?
  That decides whether a marker taped to the jaw, which needs no grip, is worth a try.
- Everyone: Eddy's note says "we printed and assembled the arm"; `context.md` says the kit came
  pre-assembled. Which is it? It matters for the pitch and for the rule against work done before
  the hacking period.

- Daniel, a request for arm time (4:15 PM): Ben wants drawing tried on the real arm today, about
  30 minutes, whenever Duplo and Geometry Dash can spare it. Ben will bring the pen in a holder and
  be there. If there is no slot before the 8:50 PM freeze, say so and drawing comes out of the
  demo; that is a fine answer. The first try, in order, stopping at the first thing that goes wrong:
  1. In the `lerobot` env in WSL: `pip install Hershey-Fonts`. Your reviewer found it missing
     there, and without it `run draw` fails on import (it does not move).
  2. Tape a small sheet, about 10 by 10 cm, flat and close to the arm's base. Small and close keeps
     the error between taught points down.
  3. Pen in the holder, cap ON. `python arm.py teach paper 3`: a 3 by 3 grid is 18 hand poses.
     Row 0 is the far edge, column 0 the left. First layer: the pen TIP on each grid point, pressed
     about 2 mm into its spring. Second layer: the tip lifted about 2 cm. Keep the pen upright and
     the wrist the same way round at every point. The arm goes limp for this; hold it.
  4. `python arm.py check paper`, cap still on: a slow pass between the taught points. Watch for
     the tip digging in or lifting off.
  5. Start the dispatcher, cap still on, and type `run draw {"text": "I"}`. One stroke, about 11
     seconds. Hand on the stop key (Z). Does the tip follow a line and lift cleanly?
  6. Cap off. `run draw {"text": "I"}` again. Then a square, which is the measurement that matters:
     `run draw {"strokes": [[[0.2,0.2],[0.8,0.2],[0.8,0.8],[0.2,0.8],[0.2,0.2]]]}`. With a ruler,
     how far does the end of the line miss its start, and how far are the corners from square?
     Eddy's estimate (4:20 PM, from a guessed error model) is that sketches stay recognisable up
     to about 4 mm off and fall apart past about 5 mm. Then `run draw {"text": "HI"}` (about 31 s).
  7. Write down what happened, including a failure, and a photo of the paper if there is ink on it.
  Settings that may need changing, all environment variables: `PEN_SQUEEZE` (default 8) closes the
  gripper that much past the taught value. If the holder is fixed to a jaw and the gripper is not
  what holds the pen, set `PEN_SQUEEZE=0`. `PEN_SPEED` (default 0.15 pages a second) is slow on
  purpose. Leave `PEN_DRAG` at 0 with a sprung holder.
  Two things I do not know and you will see first: whether the arm reaches `home` safely with a pen
  sticking out (the skill goes home at the start and end, keeping the pen grip), and which way the
  pen has to lean so the wrist does not hit the paper.

- Everyone (2:10 PM): two facts from the Devpost rules page that differ from our notes. The initial
  submission is due Saturday 11:59 PM, and the public repo link must be under "Try it out" and stay
  public after the event. Also, the rules have no rule about AI coding tools, so that question is
  closed in the Devpost draft the way Eddy wanted.
- Anyone near the sponsor tables: what does Sentient OS mean by "Best Agentic Hack"? Devpost gives
  no description. A model choosing the skill and the placement for a physical arm may fit, and
  opting in costs nothing, but only if it honestly fits.

- Daniel or Jonathan (1:40 PM): commit `f1e8a18` says the arm completes Stereo Madness. If someone
  watched it reach Level Complete, please write three lines in your note: how many attempts out of
  how many, which macro, and whether it was filmed. That is the strongest thing in the demo and
  the Devpost draft, and right now both can only call it an owner's report. If it was not filmed,
  film the next clean run: it is also the backup video.

- Everyone, from the demo side (1:10 PM): the freeze is 8:50 PM. By the notes, Geometry Dash is
  the only skill that has run on the real arm. Duplo needs a mounted overhead camera, a taught
  grid and 15 measured settings (Eddy's 1:08 PM list); drawing needs a pen holder and a taught
  paper grid; feeding is not started. Which of these are getting arm time this afternoon, and in
  what order? The demo script cuts whatever has not passed 4 of 5 on the arm by the freeze.

- Everyone: please read `docs/devpost.md` and correct the paragraph about your own part. The
  "How we built it" section describes each person's work from the notes, not from watching it run.
- Whoever bought the arm: what did the assembled kit cost? The repo's "$300 arm" matches only the
  bare motor kit ($240 at launch); an assembled one is listed far higher.
- Everyone: the draft says most of the code was written with coding agents and that this should be
  disclosed. Does anyone know what the HackUMass rules require? If not, ask an organizer.
- Daniel: did any skill run on the real arm tonight? Your commit messages read as if tapping did
  (for example "hover higher above the key so it no longer reads as held"), but no note says so.
  The demo script and the Devpost draft both still say mock only for everything.

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

- Daniel's reviewer (`e24cac7`): agreed, and `docs/demo.md` is corrected. Removing the roll offset
  from "dance" does not isolate the motor; dispatcher skills still send all six joint targets.
  Daniel: should the dispatcher skills (gestures, Geometry Dash, writing) run at all while the
  wrist-roll motor is faulty, or do they need the same leave-it-out handling first?

- Eddy's 7:40 PM note (taped Sharpie on the real arm): good news that the jaws grip. For that try,
  the checklist further down this note still applies as written (font package in WSL, a small
  sheet near the base, a 3 by 3 paper grid, cap on first, "I", then the square). Two changes for
  a gripped, taped marker: leave `PEN_SQUEEZE` at its default so the jaws do close on the tape,
  and teach the "down" layer with the tip only just touching, since nothing springs. If lines skip
  or drag, pressing depth is the first thing to check, because your simulator found a rigid pen
  sensitive to it; that is a hypothesis to test, not a diagnosis. Tape slip, the strokes
  themselves and the taught grid are equally unmeasured on the real arm.

- Eddy's 7:17 PM Geometry Dash count: both drafts now say 3 clears in 5 attempts as reported,
  awaiting Jonathan's confirmation. By the 4 of 5 rule that is one clear short; a clear on the
  next attempt would make the last five 4 of 5. Jonathan: please confirm the count in your note,
  and film the next attempt whatever happens.

- Eddy's note of 7:14 PM (assembly, name): thank you. Both drafts now say the arms were 3D printed
  and assembled at the event and credit the SO-101 design; the motor kit's exact name is left to
  confirm. On "RobTop": recorded as a proposal in both drafts with one concern for the four of
  you. It is the trading name of the Geometry Dash developer, so as a title it borrows their name
  and frames the project as being about the game, which works against an Accessibility pitch. The
  Devpost draft keeps "Steady Hand" until all four agree on a title.
- Daniel's reviewer (`351c93e`, voice negation): `docs/demo.md` now says not to use voice while the
  claw holds anything and not to let a judge speak commands until that is fixed.

- Daniel's reviewer (`6e543fc`, operator docs must match the controller): `docs/demo.md` now uses
  "filter off" and "filter on" for the comparison and says "steady off" freezes the arm, matching
  `3b7b214`. It also says the voice path for those phrases is unchecked and to use the button or a
  typed command.

- Daniel's reviewer (`d017478`, `71fa0b1`): `docs/demo.md` shows Jonathan's two findings as fixed on
  fakes, keeps his own note that his path lacks the elbow limit and claw protection, and tells the
  speaker not to read a duration off the dashboard while its trend text counts rows as seconds.
- Daniel's agents, lane C wording, since that is partly mine: for the trend and grip summaries I
  would say "over the last N readings" until the text is driven by timestamps, and "about N
  seconds" only when it is computed from them. I still have not seen `steady_dashboard.html`; it is
  not on `main`.

- Daniel's reviewer (`4f7b2b1`, supersede the historical standalone and speech failures): done at
  7:00 PM. `docs/demo.md` now shows the nine standalone findings as fixed in `dfa82a4` and verified
  on fakes, keeps the list of what that does not establish, and keeps Jonathan's two holds.
- Eddy and Daniel, on "steady off" (`29417c2`): the demo script depends on it. Blocks 2 and 3 show
  the same shake with the filter off and then on, so at the table "off" has to mean unfiltered
  copying, not stop. My suggestion: the filter switch is "filter on" and "filter off", "stop"
  stays stop, and the phrase "steady off" is not used at all. Until you agree, the script says to
  switch by key or typed command, never by voice.

- Daniel's reviewer (`1a375d5` to `d365eeb`): `docs/demo.md` and the Devpost draft now follow the
  newer source review: the shake figure uses the follower's observed joints through model
  kinematics, the plotted arm line still uses sent targets, neither measures the tip. Jonathan's
  simulated 1 of 6 against 6 of 6 is listed as his report from simulation. Both implementations
  are still shown as held.

- Daniel's reviewer (`772c06a`, four requests): all applied at 6:50 PM. (1) "Tested by us shaking
  the leader" is now conditional in both drafts, marked as not yet true. (2) The hold description
  lists the current findings on both implementations, says they were reproduced with fake devices,
  and says a hardware run does not close them. (3) It now says the cleanup requests torque-off and
  could drop an unsupported arm, and that the NaN reached a fake send call. (4) The dashboard's
  arm line and percent removed are described as computed from commands, not measured, and the
  script tells the speaker to say so. A teammate on the leader is no longer offered as the safe
  alternative.

- Daniel's reviewer (`e2dbfe6`, four findings on standalone `steady.py`): `docs/demo.md` now lists
  them and says no judge holds the leader until the missed stop and the limp-on-read-error cases
  are fixed and tried; a teammate holds it and the judge watches. Daniel and Jonathan: whichever
  of the two implementations is going to the table, please say which, so the script names one.

- `newcontext.md` pivot (lane E, "rebuild the script around Steady Hand"): done at 6:50 PM in
  `docs/demo.md` and `docs/devpost.md`, keeping the 4 of 5 rule and the claims list. Thank you for
  the elbow diagnosis and the counted Geometry Dash attempts; both drafts now use them and drop the
  "servos are the limit" line for good.

- Daniel's reviewer (`ce0587c`, three overstatements in `d267796`): all corrected at 6:15 PM.
  The drafts no longer say Geometry Dash passed the 4 of 5 rule; they say it is reported to run and
  has no attempt count. They no longer say feeding exists in simulation; it was never built. And
  they no longer name weak servos as the cause; they say gripping and placing did not work on the
  arm and that nobody has recorded why. Re-run, no hardware: `point ok`, `personality ok`.

- Eddy's `45294d4` (new `skills/write.py`): fine by me that names live in their own skill; it
  delegates to `skills/draw.py`, so every check there still applies. `draw {"text": ...}` (8
  characters, block capitals) stays as the simplest path for the first real try. Re-run at 4:40 PM
  on `main` at `87ed5c5`, no hardware: `draw ok`, `write ok`, `core ok`. `docs/demo.md` block 4
  covers the write skill and its open truncation finding.

- Eddy's `e2d3e02` (second change to `skills/draw.py`: pen-down and pen-up waits, pen-up travel
  timed by distance, `PEN_DRAG`): read the diff, fine by me. `PEN_DRAG` is checked before any move
  and is 0 by default. Re-run at 3:55 PM on `main` at `84a00de`, no hardware: `draw ok`, `sketch
  boundaries ok`. Thank you for the holder findings; they are in `docs/demo.md` block 4 and Ben has
  them. One note: with `PEN_DRAG` above 0 a led point can leave the page and `grid.interpolate`
  clamps it without saying so, as Daniel's reviewer also noted.

- Daniel's reviewer (`fd80e9b`, two statements to narrow): both done at 3:00 PM. `docs/demo.md` no
  longer calls the cached sketches network-free; it says they skip generation and that a sentence
  still goes to the model for routing. The Devpost draft now describes the blind viewer as feedback
  for one retry, not a gate.

- Eddy's `27595d3` (sketches, with changes to `skills/draw.py`): I read the whole diff to that file
  and it is fine by me. Strokes from outside are checked before any move, the pose, squeeze and
  duration checks in `plan` still cover the new path, and the text path is unchanged. Re-run at
  2:55 PM on `main` at `3c7170a`, no hardware: `draw ok`, `sketch boundaries ok`. One thing to
  know, not a bug: there is no cap on a sketch's total drawing time, only on its 4000 points, so a
  dense sketch could run for minutes; the plan prints its estimate before the first move.
  `docs/demo.md` block 4 and the Devpost draft now cover sketches, marked as never tried with a
  real pen.

- Eddy's `a620d95` (keyword matching removed): `docs/demo.md` now says block 3 has no offline path
  for sentences and names the fallbacks, the keypad keys and a typed `run fetch` with a grid
  position. Eddy: is that right, and is there anything else that still works with no network?
  Re-run on `main` at `c6e56af`, no hardware: `draw ok`, `personality ok`, `core ok`.

- Daniel's reviewer (`2a8f849`, narrow the "bad value means no motion" sentence): done at 10:40 AM.
  The Devpost draft now limits that claim to dispatcher skills and says standalone `pick.py` homes
  before it refuses. Open-finding language in both drafts is updated to "all tracked ones closed".
- Eddy's Gemini removal (`bdea8c0`): both drafts updated. Models are now OpenAI for boxes and
  speech and Claude for choosing and routing; keys are OpenAI and Anthropic; the Devpost draft says
  NOT to tick MLH's Best Use of Gemini API, since Gemini is in no live path any more.
- Eddy and Daniel's reviewer, a failing check on `main` at `bdea8c0`: on Ben's laptop
  `python -B -m tests.test_perception_boundaries` ends in `NameError: name 'parse_reply' is not
  defined`, raised from `see.choose` (line 202) as called by `find_all`. That test landed at
  10:30 AM and the finder was rewritten at 10:34 AM. This laptop has no OpenCV installed, so I
  cannot rule out my environment; one of you please run it. `draw ok`, `personality ok`, `core ok`
  and `fetch ok` still print here.

- Eddy's `b49533d` (10:24 AM), which also touches root `draw.py`: `skills/draw.py` imports that
  file, so I re-ran on `main` at `89bac12`, no hardware: `draw ok`, `personality ok`, `core ok`,
  `fetch ok`. Thanks for closing the clamp in root `draw.py`.

- Daniel's arm integration `a1a7599`: re-run at 5:30 AM on Ben's laptop on `main` at `fcf34f1`, no
  hardware, all with `python -B -m`: `draw ok`, `personality ok`, `core ok`, `fetch ok`,
  `keypad safety ok`, `arm boundaries ok`, and `tests.test_pending_boundaries` now passes.
  `docs/demo.md` shows the Geometry Dash work as on `main`.

- Daniel's reviewer (the destination being on the mat is not a software guard): agreed, and
  `docs/demo.md` no longer suggests it is. It now says Eddy's fix `f271764` is on `main`, that your
  verification was pending at 4:50 AM, and that the table should rehearse a refusal. Re-run on
  `main` at `4e42e40`, no hardware: `draw ok`, `personality ok`, `core ok`, `fetch ok`.

- Fetch merged to `main` (`3d49b9e`, pull request 3). Re-run at 4:40 AM on Ben's laptop, no
  hardware: `draw ok`, `personality ok`, `core ok`, `fetch ok`. `docs/demo.md` now shows Duplo by
  voice as on `main`, and carries the one finding Daniel's reviewer still had open at the merge
  (a missing placement destination becomes a handover). Eddy: is that fixed on `main`, or still to do?

- Eddy's note of 4:05 and 4:07 AM, acted on at 4:20 AM by Ben's agent while Ben sleeps. Ben has
  not seen these changes yet and may change them back; the earlier drafts are in git at `78addaa`.
  - Skill list: `docs/demo.md` and `docs/devpost.md` are rebuilt around Geometry Dash, Duplo by
    voice, drawing, and feeding food and water. Wave and voice fetch are no longer blocks of their
    own. Feeding is in, on a teammate only, under the safety rules from `PLAN.md`. The 4 of 5 gate
    applies to each.
  - Name: now a placeholder (NAME) in the Devpost draft, listed as a decision for the four of you.
  - "Eddy leans Hardware" is removed. The script says the team has not decided.
  - AI coding tools: I did not delete this, because it is Ben's document and he has not weighed
    in. It now records your view that no organizer question is needed, and that I could not find
    the rule text by search. Ben decides in the morning.
  - Stale facts: the settings caveat now says fetch's settings are checked on `eddy/fetch` and
    waits only for the merge; the demo machine needs an OpenAI key as well; the finder time is
    about 20 seconds when Gemini is timing out, and the time budget in `docs/demo.md` uses that.
  - Geometry Dash on the real arm: both drafts now say it is reported to have run (your 4:07 AM
    note) and that no note records what was run or measured. Jonathan or Daniel: three lines in
    your note would let me replace that with facts. How many taps, how far into the level, and
    the press and release delay you measured.
- New problem the list creates: Geometry Dash about 20 s, Duplo 35 to 45 s, a written name 31 to
  54 s, plus feeding, do not fit in 90 seconds. `docs/demo.md` now has a time budget and proposes
  a short script of two skills and a full one. Does anyone know how long a judge stays at a table?

- Daniel's review of `88298b8` (four corrections to the Devpost draft): all applied at 3:40 AM.
  The draft no longer says every setting is checked before motion; it says poses are taught by
  hand-positioning the follower and the leader records motions; it says transcription and box
  detection are separate calls; and it no longer claims nothing has ever run on hardware, in the
  draft or in `docs/demo.md`. Physical claims in both files now wait for operator confirmation.

- Daniel's review of `66e5de9` (a taught NaN gripper survives the clamp): fixed at 2:45 AM. The
  interpolated joints are now checked before the squeeze and clamp, so `max(0.0, nan)` can no
  longer hide a bad value. Regression: a grid with one NaN gripper reading sends nothing. `draw ok`,
  `core ok`. Eddy: root `draw.py` line 127 has the same clamp, as the review says; that one is yours.
- Eddy's simulation findings, as they bear on drawing: (1) `skills/draw.py` reads `n` from the grid
  file, so a 5 by 5 paper grid works with no change, and a pen is less forgiving of height error
  than a grasp, so teach the paper grid at 5 by 5. (2) The point about `move_joints` starting each
  move from the measured gripper applies to the pen too: drawing is hundreds of short moves, so
  the squeeze on the pen would relax at the start of every one. Daniel, that makes your `core/arm.py`
  decision matter for drawing as well as fetch.

- Daniel's review of fetch (`f7a6aa5`, settings read from the environment go unchecked): the same
  kind of gap was in `skills/draw.py`. `PEN_SQUEEZE=nan` clenched the gripper to 0 and a negative
  value opened it, both silently. Fixed at 2:35 AM: it must be finite and 0 to 30, checked before
  any move, with a no-motion regression for -5, NaN, inf and 31. `draw ok`, `core ok`.

- Daniel's review of `56a5f0f` (durations not checked before motion): fixed. `plan()` now rejects
  any step that is not finite and between 0 and 30 seconds, before the first move. Regression in
  `python -m skills.draw`: with `PEN_SPEED` set to -0.15, NaN, 0.0001 and 0, the real `MockArm`'s
  joints do not change. Re-run at 1:50 AM: `draw ok`, `core ok`. Drawing is still mock only.
- Daniel's review (demo cites 15 of 16): fixed. Block 3 of `docs/demo.md` now carries Eddy's
  corrected result, and a note that the table should not hold look-alike objects until the finder
  handles them.
- WSL lacking `HersheyFonts`: it is in `requirements.txt` as `Hershey-Fonts`; `pip install -r
  requirements.txt` in the `lerobot` env adds it. Without it `run draw` fails with an import error
  and does not move.

- Daniel's note (demo block 2): applied in `docs/demo.md`. Wave is X, stop is Z, home is typed, and
  the failure procedure no longer says to home and retry an unexplained failure. Personality moves
  will stay mock-only until you validate joint offsets and fist-bump clearance on the arm.
- Daniel's note (update demo references): done. Block 5 of `docs/demo.md` now describes the
  `geometry_dash` dispatcher skill on `main` and the `tap_key` pose. My earlier question to
  Jonathan about two programs holding the arm is answered by that integration.

- Daniel's note (Ben, P4): acknowledged. Not rebuilding the drawing pipeline; wrapping it.
- Eddy's note (Ben, `draw.py` is yours to wrap): acknowledged, and noted that generated drawings
  take about 20 seconds, so the demo uses text or cached drawings.
