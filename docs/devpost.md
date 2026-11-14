# Devpost draft

Drafted by Ben's agent (Person 4). Reworked Sat Nov 14, 6:50 PM around the Steady Hand pivot
in `newcontext.md`; Ben has not reviewed this version. The claims list there binds this text. Initial submission is
due Sat midnight; aim for 11 PM.

How to use this file: the text under each heading is written to paste into Devpost. Lines in
[SQUARE BRACKETS] are not text to paste. They mark a claim that is not true yet, or a choice the
team has not made. Before submitting, every bracket must be either confirmed and rewritten, or
deleted with its sentence. As of this draft the only skill reported to have run on the real arm
is Geometry Dash (Eddy, 4:07 AM), and no note yet says what was run or measured. Whoever was at
the arm must confirm each physical claim.

## Decisions needed before submitting

1. Track: exactly one [HACKUMASS] category. Best Accessibility Hack fits Steady Hand; Best MedTech
   Hack is the alternative (see `docs/demo.md`; all 28 prizes are in `docs/tracks.md`). Sponsor
   prizes are separate opt-ins.
2. Project name: `newcontext.md` uses "Steady Hand". Confirm that is the Devpost title.
3. Which skills are in. Only skills that passed 4 of 5 on the real arm at the freeze are described
   as working. The draft below lists the team's four; cut the ones that did not pass.
4. AI coding tools: settled by the rules page, read Sat 2:10 PM (`docs/tracks.md`). It has no
   rule about AI tools, and one MLH prize at this event is awarded for building with an AI coding
   agent, so no organizer question is needed (Eddy's view). The rule that does apply: "You must
   document any external code usages in your submission and mention during judging to clearly
   distinguish your contributions." The open-source list below is how we meet it.
5. Repo public, with its link under "Try it out" (required, and it must stay public afterwards).
   All four teammates need a Devpost account and must be listed as contributors. An optional
   demo video under 3 minutes is "recommended". Initial submission is due Sat 11:59 PM. Do NOT tick MLH's Best Use of Gemini API:
   Gemini was removed from the project at 10:34 AM Saturday and is in no live path.

## Title and tagline

Steady Hand [the name used in `newcontext.md`; confirm it is the Devpost name]

Tagline: Your hand shakes. The arm does not.

## Inspiration

For people with essential tremor or Parkinson's, a shaking hand makes ordinary things hard: writing
a name, holding something still. We started the weekend building a robot arm that did things by
itself. By Saturday evening we had learned what our arm was actually good at: following a person.
So we let the person do the aiming and gave the arm one job, taking the shake out.
[Do not add a statistic unless someone has sourced it.]

## What it does

Steady Hand is a pair of small robot arms. You hold and move the leader arm; the follower arm
copies your movement with the tremor filtered out.

- Filters a shaking hand. [CONFIRM ON ARM with numbers: shake in mm with steady mode off and on.]
  Slow, deliberate movement passes through; the fast shake does not.
- Shows what it removed. A dashboard plots the hand's shake against the filtered command sent to
  the arm [say "the arm's measured shake" only if the follower's own readings are plotted] and the
  percent removed, and runs a ten-second "hold still" steadiness test. [CONFIRM the test exists at freeze.]
- Holds things for you. [CONFIRM the skill on the arm; the grasp alone worked 4 of 4.] Hand the
  claw a light object and it holds it steady and gives it back.
- Extras [only those that passed 4 of 5]: it plays Geometry Dash by pressing the key itself
  [so far: one full clear of Stereo Madness in three counted attempts], gestures, voice commands.

What it is not: [ONLY ONCE TRUE: it has been tested by us shaking our own hands on purpose;] it
has not been tested with patients. It
lifts light things only. It does not treat tremor; it measures and tracks steadiness.

## How we built it

- The arms are a Seeed Studio SO-ARM101 Pro leader and follower pair (the SO-101 design by
  TheRobotStudio), driven through Hugging Face's LeRobot.
- Deliberate hand movement is slow, below about 2 Hz; tremor is fast, about 4 to 12 Hz. A low-pass
  filter between the two arms passes the first and holds back the second, and the follower's
  speed is capped. On synthetic input a 0.5 Hz reach passes at 94 percent and a 6 Hz shake is cut
  by 90 percent. [REPLACE with the real-arm numbers when Daniel publishes them.]
- The two arms' zero points differ, so a per-joint offset is measured once with both arms folded
  against their end stops.
- A dispatcher process owns the follower and runs one skill at a time; every skill is one Python
  file with a name, a description and a `run(arm, params, stop)` function. A three-key keypad,
  voice and a typed command line all drive it, and one key always stops the arm.
- Commands are checked before the first motor moves, and those checks run as tests on a mock arm
  with no hardware. A second coding agent reviewed every branch and held changes out of the main
  branch until its reproduced findings were fixed.
- Geometry Dash replays a recording of a person's key presses. The arm laptop's Linux clock ran
  4.2 percent fast against Windows, which made every jump early until the replay was timed on
  Windows. [Daniel's measurement; confirm the figure.]

## Challenges we ran into

- We pivoted late. For most of Saturday we built picking, stacking and drawing, with a camera
  finding objects and the arm reaching for them. In simulation it worked. On the real arm, four
  hours of attempts did not pick one brick off the table.
- The cause of the "weak grip" was not weak motors. The follower's elbow had been calibrated
  through only part of its travel, the motor stored that as a limit, and every pose asking for
  more bend stopped about 23 degrees short without any error. [Daniel's diagnosis; confirm.]
- What worked on the real arm had one thing in common: a person supplied the position. That
  observation is the project we ended up with.
- One arm pair, four people: everyone wrote against a mock arm and took turns on the real one.
- Stopping safely is harder than moving. Early shutdown code moved the arm after a stop, and the
  motor library's own cleanup would have asked the motors to switch off, which can drop an
  unsupported arm. Both were caught in review
  on fake hardware.

## Accomplishments that we're proud of

- [ONLY IF TRUE: a measured before and after on the real arm, with a stranger's hand on the leader.]
- Finding the elbow limit instead of blaming the motors.
- Saying no to our own plan with hours to go, and ending with something that fits the hardware.

## What we learned

- Test the hardest physical thing on day one. We learned what the arm could not do after building
  for it.
- A passing simulation is a claim about the simulation.
- Write down how each thing was tested: on a mock, in simulation, or on the arm.

## What's next for Steady Hand

- Trying it with people who have a tremor, with proper guidance. Nothing here has been.
- A lighter, quicker follower, so the filtered motion trails the hand less.
- Recalibrating the elbow so the arm reaches its full range.

## Built with

python, lerobot, so-101, feetech-sts3215, claude-api, openai-api, opencv, mujoco, playwright,
pynput, sounddevice, hershey-fonts, quick-draw-dataset
[REMOVE any that are not in the final demo path.]

## Open source and data we used (must be disclosed)

- LeRobot (Hugging Face): motor control, calibration, teleoperation.
- SO-101 arm design (TheRobotStudio); Seeed Studio SO-ARM101 Pro kit.
- OpenCV, NumPy, sounddevice, pynput, certifi, feetech-servo-sdk.
- Hershey-Fonts (single-stroke text) and Google's Quick, Draw! dataset (doodles).
- MuJoCo (simulation) and Playwright (browser Geometry Dash replay).
- SayoDevice O3C keypad model files in `keypad/geometry_dash/sayodevice_o3c/` (see its LICENSE).
- Anthropic Claude API and OpenAI API.
- Geometry Dash is RobTop's game; we only press its keys.
[CHECK this list against `requirements.txt` and the README on Saturday night.]

## Cost figures and where they come from (looked up Sat Nov 14, 3:30 AM)

[After the Steady Hand pivot these are background only. The claims list in `newcontext.md` rules
out presenting the arm as a replacement for a medical device, so do not set its price beside
theirs in the pitch.]

Use these in the pitch only as written. They are list or reported prices, several years apart,
found by web search. Open the source links and confirm each number before saying it to a judge.

| Thing | Figure | Source and caveat |
|---|---|---|
| SO-ARM101 Pro motor kit, both arms, no printed parts | $240 at launch (May 2025) | CNX Software launch article. A later retailer listing showed $312; which retailer was not confirmed. |
| Same arm, assembled | A$714 at one Australian retailer | Pakronics. Ours came assembled, so what we paid is likely well above $240. [ASK whoever bought it.] |
| Obi robotic feeding device | $4,500 in 2017; about $8,200 to $9,600 at US distributors now | The Robot Report (2017); current distributor listings. No manufacturer list price found. |
| Kinova Jaco wheelchair-mounted arm | about $35,000; "more than $40,000" in one paper | Futurism; NIH R-ARM project paper. Both around 2019. |

The repo's earlier "$300 arm" is only right for the bare motor kit. Do not say "$300" at the table
if ours was bought assembled. And do not say our arm replaces these devices: they are certified
products that have been used by real patients, and ours is a prototype.

Sources:
- https://www.cnx-software.com/2025/05/02/so-arm101-open-source-dual-robotic-arm-kit-works-with-hugging-faces-lerobot/
- https://uk.robotshop.com/products/seeed-studio-so-arm101-ai-arm-servo-motor-kit-pro-lerobot-w-o-3d-printed-parts
- https://www.pakronics.com.au/products/so-arm101-low-cost-ai-arm-servo-motor-kit-pro-for-lerobot-assembled-version-ss100046482
- https://www.therobotreport.com/obi-dining-robot-helps-disabled-people-feed-themselves/
- https://www.rehab-store.com/p-obi-robotic-independent-feeding-device.html
- https://futurism.com/the-byte/robot-arm-wheelchair
- https://www.nibib.nih.gov/sites/default/files/R-ARM.pdf
