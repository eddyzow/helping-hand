# Devpost draft

Drafted by Ben's agent (Person 4). Reworked Sat Nov 14, 5:45 PM after Eddy reported what
the real arm can and cannot do; Ben has not reviewed this version. Initial submission is
due Sat midnight; aim for 11 PM.

How to use this file: the text under each heading is written to paste into Devpost. Lines in
[SQUARE BRACKETS] are not text to paste. They mark a claim that is not true yet, or a choice the
team has not made. Before submitting, every bracket must be either confirmed and rewritten, or
deleted with its sentence. As of this draft the only skill reported to have run on the real arm
is Geometry Dash (Eddy, 4:07 AM), and no note yet says what was run or measured. Whoever was at
the arm must confirm each physical claim.

## Decisions needed before submitting

1. Track: exactly one [HACKUMASS] category. Accessibility or Hardware (see `docs/demo.md`; the
   full list of 28 prizes is in `docs/tracks.md`). Sponsor prizes are separate opt-ins.
2. Project name. Eddy says it will not be "Helping Hand"; the four of you settle it. The title
   below is a placeholder, written as NAME.
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

NAME [placeholder until the team picks one]

Tagline, two options:

- Hardware: A desk robot arm that beats a rhythm game with its own finger, and does what you tell it.
- Accessibility [only if fetching or feeding is somehow back by the freeze]: A desk robot arm that
  helps from one key or one sentence.

## Inspiration

[REWRITTEN 5:45 PM after Eddy reported that the real arm can press a button but cannot grip a
pencil or place blocks. The earlier version compared the arm with assistive feeding devices; with
fetching and feeding out of the live demo, that comparison would promise something we do not show.]

Hobby robot arms are now cheap enough to sit on a desk, but most demos teach them one trick. We
wanted one arm with a library of skills behind a single control point, where adding a skill is one
small file, you can ask for a skill out loud, and a stop key always works. Then we found out what a
$240 motor kit can and cannot physically do, which turned into the most useful part of the weekend.

## What it does

NAME is an SO-101 robot arm with a set of skills you start from a three-key keypad or by speaking.

- Plays Geometry Dash. [CONFIRM with whoever watched: how far it gets, out of how many attempts.]
  The arm physically taps the jump key through Stereo Madness from recorded timings, held presses
  included.
- Reacts. [CONFIRM ON ARM] It waves, nods, celebrates a clear and droops after a crash.
- Points at what you name. [CONFIRM ON ARM] Say "point at the red brick"; a camera looks at the
  table and the arm reaches over and points at it.
- Writes a name. [CONFIRM ON ARM; the riskiest one] With a felt-tip marker taped to its gripper.
- Stops. One keypad key always stops the arm where it is. [CONFIRM ON ARM]
- In simulation only, and we say so: the same code picks up and stacks Duplo by voice and sketches
  what you ask for. The real arm's servos are too weak to grip and not accurate enough to place
  pieces, so these are shown as simulator video.

## How we built it

- The arm is a Seeed Studio SO-ARM101 Pro (the SO-101 design by TheRobotStudio), driven through
  Hugging Face's LeRobot. Poses are taught by switching the follower's motors off and positioning
  it by hand; the leader arm is used to record whole motions.
- A dispatcher process owns the arm and runs one skill at a time. Every skill is one Python file
  with a name, a description and a `run(arm, params, stop)` function. The keypad, the voice router
  and a typed command line all send the dispatcher the same one-line commands.
- Finding objects takes two models. An OpenAI model draws a numbered box around every object in the camera
  frame, because it was accurate about where things are. Claude then picks which numbers match the
  request, because it was better at telling look-alike pieces apart. A spoken request is
  transcribed by an OpenAI speech model in its own call before the boxes are found. We started
  with Gemini for all of this and removed it when its free tier kept timing out.
- Reaching uses no inverse kinematics. We teach the arm a grid of poses over the table by hand and
  blend between them. [CONFIRM: the grid size we ended up using.]
- Writing turns text into pen strokes with a single-stroke Hershey font, then follows them through
  a taught grid over the paper. For a sketch, Claude draws the thing as strokes three times, guided
  by the most typical doodles of it from Google's Quick, Draw! dataset. A second call that is not
  told the subject is asked to name the drawing; if it names something else, the sketch is redone
  once with that feedback.
- Geometry Dash replays a recording of a person's key presses, shifted by the arm's measured press
  and release delay. [CONFIRM: the measured delay in milliseconds.]
- Safety was treated as a feature. Commands are checked before the first motor moves: joint
  values, move durations, settings and the replies from the models. For the dispatcher skills a
  rejected value means no move is sent, and each of those checks has a test that runs on a mock
  arm with no hardware.
  [Keep it this narrow. Closed findings do not prove every bad input gives zero motion: the
  standalone `pick.py`, for one, homes the arm before it refuses.]
  [CONFIRM at the freeze that no review finding about an unchecked value is still open. At
  11:20 AM one was open on `main` (a malformed placement reply becoming a handover, in `a620d95`).]
- A physics simulation of the arm and the Duplo set (MuJoCo) was used to try fetch before
  touching hardware.

## Challenges we ran into

- The arm itself. It is strong enough to press a key and not strong enough to grip a pencil, and
  it cannot place a brick within the few millimetres stacking needs. We found that out on the real
  arm on Saturday afternoon, after building picking, stacking and drawing in simulation.
  [CONFIRM the wording with whoever ran those tests, and add the numbers if anyone measured them.]
- One arm, four people. Everyone wrote against a mock arm with the same interface and booked the
  real arm in short slots.
- Vision models were good at different halves of the job. One pointed accurately but miscounted
  look-alike bricks; the other chose correctly but pointed loosely. Splitting the job fixed it.
- The free model tier rate-limits and sometimes takes over ten seconds. The finder retries, and
  the demo is planned around the worst case.
- The arm has no sense of touch. [CONFIRM ON ARM: what this meant for the pen and the grasp.]
- Stopping safely is harder than moving. Our first shutdown code homed the arm after a stop, and
  the motor library's own cleanup could switch the motors off and drop the arm. Both were found in
  review on fake hardware. [CONFIRM with Daniel whether that was before the arm first moved.]
- [ADD: whatever actually went wrong on the real arm on Saturday.]

## Accomplishments that we're proud of

- [ONLY IF TRUE: N skills working live at the table from one key or one sentence.]
- A stop key that was tested on purpose, including the cases where something else has just failed.
- Four people's coding agents coordinated through notes in the repository, with every claim
  marked as tested on a mock, in simulation, or on the arm.

## What we learned

- Get the hardware moving first, and test the hardest physical thing on day one. We built
  grasping and drawing for most of a day in simulation before learning the arm could not grip.
  [CONFIRM this is how the team sees it.]
- A taught grid of poses is a workable substitute for inverse kinematics on a cheap arm.
  [CONFIRM ON ARM.]
- Say exactly how each thing was tested. "Works" meant three different things on this team until
  we wrote it down.

## What's next for NAME

- [If feeding did not make the demo: feeding, as a recorded scoop that stops short of the face.]
- A wrist camera, so the arm does not have to move out of the way to look.
- Trying it with people who would actually use it. Nothing here has been tested with a person
  with limited hand use, and it is a weekend prototype, not a medical device.

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
