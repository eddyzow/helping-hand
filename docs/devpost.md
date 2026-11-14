# Devpost draft

Draft by Ben (Person 4), Sat Nov 14, 3:35 AM. Initial submission is due Sat midnight; aim for 11 PM.

How to use this file: the text under each heading is written to paste into Devpost. Lines in
[SQUARE BRACKETS] are not text to paste. They mark a claim that is not true yet, or a choice the
team has not made. Before submitting, every bracket must be either confirmed and rewritten, or
deleted with its sentence. As of this draft no note in the repo records a skill running on the
real arm; that is not the same as knowing none has. Whoever was at the arm must confirm each
physical claim, in either direction.

## Decisions needed before submitting

1. Track: exactly one HackUMass category. Accessibility or Hardware (see `docs/demo.md`).
2. Project name: "Helping Hand" is still marked a working name in the README.
3. Which skills are in. Only skills that passed 4 of 5 on the real arm at the freeze are described
   as working. The draft below lists five; cut the ones that did not pass.
4. AI coding tools. Most of this code was written with coding agents (Claude Code, Codex). Check
   the HackUMass rules and Devpost form for how that must be disclosed, and say it plainly either
   way. Ask an organizer if the rules do not say.
5. Repo public, all four teammates added on Devpost, MLH opt-ins ticked (Best Use of Gemini API
   fits: Gemini is in the live path).

## Title and tagline

Helping Hand

Tagline, two options:

- Accessibility: A desk robot arm that fetches, writes and plays for you, from one key or one sentence.
- Hardware: One low-cost robot arm, many skills, one stop key.

## Inspiration

[ACCESSIBILITY VERSION] Robots built to help people who cannot easily reach, grip or write exist,
but they are expensive and each does one job. A robotic feeding device is listed by US distributors
at roughly $8,000 to $9,600, and a wheelchair-mounted assistive arm has been reported at about
$35,000. The motor kit for the hobby arm on our table launched at $240. We wanted to see how much
everyday help one cheap arm could give if every skill could be started with a single key press or
a single spoken sentence.

[HARDWARE VERSION] Hobby robot arms are now cheap enough to sit on a desk, but most demos teach
them one trick. We wanted one arm with a library of skills behind a single control point, where
adding a skill is one small file and a stop key always works.

## What it does

Helping Hand is an SO-101 robot arm with a set of skills you start from a three-key keypad or by
speaking.

- Wave and react. [CONFIRM ON ARM] Press a key and the arm waves; it can also nod, shake its head,
  celebrate and droop.
- Fetch by voice. [CONFIRM ON ARM] Say "bring me the red brick". A camera looks at the table, the
  arm picks the brick up and holds it out. If two things match, it asks which one.
- Write. [CONFIRM ON ARM] Give it a short word and it writes it on a card with a pen.
- Play Geometry Dash. [CONFIRM ON ARM] The arm taps the jump key through the start of Stereo
  Madness from recorded timings, including the held presses.
- Stop. One keypad key always stops the arm where it is. [CONFIRM ON ARM]

## How we built it

- The arm is a Seeed Studio SO-ARM101 Pro (the SO-101 design by TheRobotStudio), driven through
  Hugging Face's LeRobot. Poses are taught by switching the follower's motors off and positioning
  it by hand; the leader arm is used to record whole motions.
- A dispatcher process owns the arm and runs one skill at a time. Every skill is one Python file
  with a name, a description and a `run(arm, params, stop)` function. The keypad, the voice router
  and a typed command line all send the dispatcher the same one-line commands.
- Finding objects takes two models. Gemini draws a numbered box around every object in the camera
  frame, because it was accurate about where things are. Claude then picks which numbers match the
  request, because it was better at telling look-alike pieces apart. A spoken request is
  transcribed by Gemini in its own call before the boxes are found.
- Reaching uses no inverse kinematics. We teach the arm a grid of poses over the table by hand and
  blend between them. [CONFIRM: the grid size we ended up using.]
- Writing turns text into pen strokes with a single-stroke Hershey font, then follows them through
  a taught grid over the paper.
- Geometry Dash replays a recording of a person's key presses, shifted by the arm's measured press
  and release delay. [CONFIRM: the measured delay in milliseconds.]
- Safety was treated as a feature. Commands are checked before the first motor moves: joint
  values, move durations and the replies from the models. A bad value means the arm does not move
  at all, and each check has a test that runs on a mock arm with no hardware.
  [DO NOT widen this to "every setting" unless fetch's grip and hold-time settings are checked
  too. That finding was still open at 3:30 AM.]
- A physics simulation of the arm and the Duplo set (MuJoCo) was used to try fetch before
  touching hardware.

## Challenges we ran into

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

- Get the hardware moving first. [REWRITE honestly after Saturday: when the arm first ran a skill.]
- A taught grid of poses is a workable substitute for inverse kinematics on a cheap arm.
  [CONFIRM ON ARM.]
- Say exactly how each thing was tested. "Works" meant three different things on this team until
  we wrote it down.

## What's next for Helping Hand

- Feeding: a recorded scoop that stops short of the face and waits for the person to lean in.
- A wrist camera, so the arm does not have to move out of the way to look.
- Trying it with people who would actually use it. Nothing here has been tested with a person
  with limited hand use, and it is a weekend prototype, not a medical device.

## Built with

python, lerobot, so-101, feetech-sts3215, gemini-api, claude-api, opencv, mujoco, playwright,
pynput, sounddevice, hershey-fonts, quick-draw-dataset
[REMOVE any that are not in the final demo path.]

## Open source and data we used (must be disclosed)

- LeRobot (Hugging Face): motor control, calibration, teleoperation.
- SO-101 arm design (TheRobotStudio); Seeed Studio SO-ARM101 Pro kit.
- OpenCV, NumPy, sounddevice, pynput, certifi, feetech-servo-sdk.
- Hershey-Fonts (single-stroke text) and Google's Quick, Draw! dataset (doodles).
- MuJoCo (simulation) and Playwright (browser Geometry Dash replay).
- SayoDevice O3C keypad model files in `keypad/geometry_dash/sayodevice_o3c/` (see its LICENSE).
- Google Gemini API and Anthropic Claude API.
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
