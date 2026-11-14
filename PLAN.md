# Plan: Helping Hand (working name)

HackUMass XIV, Nov 13 to 15 2026. Current as of late Fri Nov 13. The team looked at a Duplo builder (`context.md`) and a fetch vehicle tonight and came back to this plan. Section 10 of `context.md` (arm hardware, WSL setup, teleoperation commands) and its rules for AI agents still apply.

## Skill list (updated Sat 12:15 AM)

The team's current list, grouped by the mechanism each one uses. Build one skill per mechanism first.

| Mechanism | Skills | Code |
|---|---|---|
| Replayed motion | Feed food, feed water, fixed drawings | `arm.py record` and `arm.py replay` |
| See, point, pick | Command-guided pick up, Duplo building | `see.py`, plus a taught grid (`arm.py teach`, `grid.py`) |
| Taught grid plus strokes | Draw what you ask for: database, text, or generated | `draw.py` |
| Timed key presses | Stereo Madness, hardcoded tap timings | not written yet |

Ping pong is a stretch. Where a skill can be hardcoded, hardcode it. The sections below were written before this list and still describe fetch, feeding and the schedule.

### Notes on each skill

- Feed food: one recorded scoop from a bowl in a fixed spot, stuck down so it does not slide. Dry food that scoops without precision (cereal, M&Ms, rice). The spoon stays in the gripper; a printed holder helps. The arm stops short of the face and the person leans in.
- Feed water: a small lidded cup with a straw, about a third full. A full open cup is too heavy and a spill risk near the electronics.
- Command-guided pick up: `see.py` finds the named object. Still needed: a taught grid over the table and the code that moves the arm to the pixel and grasps.
- Duplo building: run the 30-minute press test in `context.md` section 3 first. If the arm cannot seat a brick, it hands bricks over in build order and a person presses.
- Drawing: `draw.py` output is tested as preview images only. Database doodles look rough, text is clean, and generated drawings were the cleanest but took about 19 seconds, so generate ahead of time. The arm needs a pen that floats (spring, rubber band or foam sleeve) because its height is off by a few millimetres from place to place. Use a thick marker and a small area near the base. Start with `arm.py record` and `replay` of a drawing made with the leader, then try `draw.py --go`.
- Stereo Madness: the level is identical every run, so record the key presses of a person playing it, then have the arm replay those timings with a finger resting just above the spacebar. The risk is timing jitter in the servos. Expect it to get partway through before expecting a full clear.
- Ping pong: needs speed and ball tracking the arm does not have, and shares nothing with the other skills. Recommended to drop.

Cheap extras if there is time, all reusing the code above: sort Duplo by colour into bins on "clean the table", wave or high-five the judge (one recorded motion), play a tune on a keyboard (same key press as Stereo Madness), tic-tac-toe against the judge, hand over the right pills from a labelled organizer, write the judge's name on a card they keep.

### What is tested and what is not

| Piece | State |
|---|---|
| `see.py` object finder | Works on a synthetic still image and a synthesized voice clip. Not tried on real photos, a live camera or a live microphone. |
| `draw.py` strokes and preview | Works for database, text and generated drawings. |
| `grid.py` | Self-check passes. |
| `pick.py` finding and mapping | Dry run works on a synthetic image: the target lands at the right place on the grid, a missing object and an out-of-reach object are refused. The grasp sequence runs against a simulated arm. |
| `arm.py` teach, pose, record, replay, `pick.py --go` and `draw.py --go` | Never run on the arm. Written against LeRobot's GitHub source, so an import may differ on Daniel's install. |

### Other things decided or learned tonight

- The Gemini key is in `.env` on Eddy's laptop and is not in the repo. Each person needs their own copy.
- The repo is private. It must be public for the Devpost submission.
- The arm is weak: plan for objects of roughly one to two hundred grams at full reach, and confirm with the lift test.
- A fetch vehicle with the arm on front was planned and dropped; that plan is in git history at commit 4a88835.
- Idea changes stop at two thirds of the hacking period, about Saturday 8:50 PM.

## Status (Fri night, read this first)

We are building fetch first. Target commands: "pick up the mouse", "pick up the lanyard", "pick up the red brick", "pick up the triangular brick". The bricks are Duplo, which are bigger than Lego and easier to grip.

Done:

- `see.py` takes a typed or spoken request plus a camera frame and returns the pixel to grasp. Run commands are in the README.
- Tested on a synthetic image with shapes at known positions: within about 5 pixels on a 1280 by 720 frame, 1.1 to 1.7 seconds per request, and it answers "Not found" for objects that are not there. A synthesized voice clip also worked.

Not tested yet: real photos, the live camera, the live microphone, anything with the arm.

Next, in order:

1. Calibration is done and teleoperation runs on Daniel's Windows laptop under WSL (commands in `context.md` section 10). With the leader, try lifting each target object and a loaded spoon at full reach. Whatever lifts without sagging is the object list.
2. Mount the overhead camera and photograph the real table with the mouse, lanyard and Duplo. Run `see.py --image` on those photos with all four commands.
3. Teach the 3 by 3 grid of hover poses and write the code that turns a pixel into an arm move (see "How it works").
4. Record one grasp motion per object type and chain it: request, pixel, move, grasp, hand over.

Decisions made tonight:

- No YOLO training for now. The Gemini finder already handles colour and shape phrases and new objects with no training. YOLO would cost 2 to 4 hours of labelling and training, and each colour or shape would need its own class. Revisit Saturday afternoon only if fetch already passes and either the Wi-Fi is flaky or we want live boxes on a screen.
- Hardcode the motion. The arm replays taught poses and recorded grasps. Finding the object already works; the grasp is the unproven part, so the hours go there.
- Fallback if the pixel-to-arm mapping is not reliable by Saturday 3 PM: each object gets a marked home spot and one recorded motion. It needs no vision but breaks if a judge moves an object.
- Mounting: the follower and the overhead camera go on one rigid board so they never move relative to each other. Build and test it on a table. If fetch passes Saturday afternoon, try the board as a tray across a chair's armrests for the pitch; if it wobbles, demo on the table beside the chair.
- Idea changes stop at two thirds of the hacking period, about Saturday 8:50 PM, which is also the feature freeze.
- We have one working arm. The follower has the claw. The leader has the trigger handle and no claw, and control only runs from leader to follower. Use the leader to teach motions. You can also switch off the follower's motors and pose it by hand while reading its joint angles.

## What we are building

An SO-101 arm on a table that a person with limited hand use can talk to. It has one overhead camera and one loop: hear a request, find the thing on the table, run a taught motion. Three skills use that loop:

1. Fetch. "Hand me the marker" and the arm picks the marker up and holds it out.
2. Feed. "Feed me" and the arm scoops from a bowl and holds the spoon near the person's mouth.
3. Count. "How much money is on the table?" and it says the total out loud and points at each coin.

The pitch is one sentence: commercial feeding robots cost thousands of dollars and do one job, and this is a $300 arm that does three.

## Feasibility of the original list

| Idea | Verdict | Why |
|---|---|---|
| Pick up objects on voice command | Build first | This is the standard SO-101 demo shape and the base for everything else. A vision model names the pixel, a taught grid turns the pixel into joint angles. About 8 to 10 hours to make it reliable. |
| Feed a person | Build second | The scoop is a recorded trajectory, so there is no hard perception. The risk is safety and mess, both handled by stopping short of the face and choosing dry food. About 5 hours. |
| Count money | Build third, vision only | Counting coins from an overhead camera is 2 to 3 hours. Picking a coin off a flat table with this gripper is not reliable (coins are 1.5 mm thick), so the arm points or slides coins into a tray instead. |
| Look at Duplo and decide what to build | Stretch | A vision model can list the bricks and propose a build in about 2 hours, and the arm can hand bricks over in build order using the fetch skill. Whether the arm can press Duplo together is unknown; the 30-minute press test in `context.md` section 3 answers it. Only after fetch and feed pass. |
| Solve a Rubik's cube | Cut | Solving the cube in software takes minutes. Turning the faces needs a fixture or two coordinated arms with regrasps, and every team that has done it built a dedicated machine. It would eat the whole weekend and share nothing with the other skills. |

Five half-working skills lose to three that work every time. At HackUMass XII the hardware projects that failed at the table lost, and both recent grand prize winners were small and reliable (see `05_synthesis/gameplan_hackumass_14.md` in the playbook folder).

## Track

Each project is in the Best Overall pool automatically and picks one HackUMass category. The XIV categories that fit:

| Category | Fit | Concern |
|---|---|---|
| Best Accessibility Hack (Public Good) | Strong. Fetch, feed and count are all things a person with limited hand use needs help with. | Software projects can enter too, so the field may be larger. |
| Best Hardware Hack | Medium. | The arm is a kit. Teams that designed their own circuits or mechanisms look more like "hardware" to these judges. |
| Best MedTech Hack | Medium. Feeding only. | Judges may expect clinical grounding we do not have. |
| Best Mechanical Hack | Weak unless we build a custom gripper or spoon mount worth showing. | |
| Most Impactful AI Hack | Weak. Crowded, and the AI here is a means. | |

Prizes, one winner each: Mechanical is a mechanical keyboard, MedTech a Fitbit, Accessibility Life 360 Tiles, Hardware an Arduino Uno. Devpost does not say whether each teammate gets one. The grand prizes (monitor, Beats, FPV drone) are bigger and every project is in that pool.

Recommendation: Best Accessibility Hack, with MedTech as the alternative if feeding works well enough to lead the pitch. Our edge is a moving robot in a category that is mostly apps, and the story carries all three skills. Decide for good by Saturday 8 PM, before the initial submission.

MLH opt-ins: tick Best Use of Gemini API only if Gemini is really the vision model in the demo. The DEV Writing Challenge is a blog post after the event, so it costs nothing this weekend. Skip Solana, Tiger Data, Vultr, MongoDB, GoDaddy and SpaceXSI: none of them belongs in this project. Do not build anything for a sponsor prize.

### What the judges score

Devpost lists four criteria. Each one maps to something we control:

| Criterion | What it asks | Our answer |
|---|---|---|
| Innovation | A new idea or a fresh take on an old one | One cheap arm doing three assistive jobs, where commercial devices do one |
| Functionality | Works as intended, reliably, with readable code | Three skills that pass 4 out of 5, and the 20-run hardening block. This is why we cut the cube. |
| Practicality | Realistic in the real world, resources reasonable for the impact | Say the arm's cost next to the price of a feeding robot. Know both numbers before judging. |
| Presentation | Clear communication, teamwork, purpose | The 90-second script below, rehearsed, with each teammate owning one part |

## Rules that can disqualify us

- Initial submission on Devpost is due Sunday 12:00 AM (Saturday midnight). Judging is 12:30 to 3:00 PM at tables, live demo.
- Final deadline: Devpost says Sunday 10:00 AM ET (7:00 AM PST), hackumass.com says 9:00 AM. We work to 9:00 AM and submit by 8:00 AM. Ask an organizer which is right, but do not plan around the extra hour.
- Pick exactly one [HACKUMASS] category on Devpost. Sponsor and MLH prizes are separate opt-ins and do not count toward that limit.
- No work from before Friday 8:30 PM. This repo was created after the start. Do not copy in code written earlier.
- Open source is allowed if we disclose it. Keep the list in the README current.
- The repo must be public at submission. It is private now; flip it Saturday night.
- Teams are four people at most.

## How it works

```
mic -> speech to text -> intent (fetch X / feed / count)
overhead camera -> vision model -> pixel of X -> table cell -> joint pose
                                                           -> taught motion on the SO-101
speaker <- spoken reply
```

Calls made here, change them if a teammate knows better:

- Python, with LeRobot for the motor bus, calibration, teleoperation, and recording and replaying trajectories. Use the leader arm to teach motions.
- Pixel to arm position without inverse kinematics. Tape a 3 by 3 grid on the table, teach the arm a "hover over this cell" pose for each of the 9 cells with the leader arm, and interpolate joint angles between them. This absorbs servo slop and camera angle in one step. Move to real IK only if interpolation misses by more than the gripper width.
- Camera fixed overhead on a rigid mount (makerspace: clamp or printed bracket). Four ArUco tags at the grid corners so the mapping survives a bumped camera.
- Vision model returns a point for the named object. We use `gemini-3.5-flash-lite` (set `GEMINI_MODEL` to change it). Our key has no access to Google's robotics models, `gemini-3.8-flash` timed out, and `gemini-3.5-flash` was just as accurate but took 7 to 11 seconds.
- Speech in with push to talk (a key or a big button on the ESP32). Open mics fail in a loud atrium. The recorded audio goes to Gemini in the same call as the image, so there is no separate speech-to-text step. Speech out with the laptop's built-in voice.
- Feeding: one recorded scoop. The spoon stops at a fixed point about 10 cm from where the person's mouth is, found with face tracking, and the person leans in. The arm never moves toward a face. Cap speed and torque. A physical stop button cuts servo power.
- Coins: detect circles, convert diameter to millimeters using the tags, classify (dime 17.9, penny 19.05, nickel 21.2, quarter 24.3), use color to confirm pennies. Fall back to asking the vision model.
- Everything runs on one laptop over USB. No venue Wi-Fi in the control loop except the vision call, and that needs a phone hotspot as backup.

## Schedule (ET)

The clock hook in this repo prints the current phase into every Claude session.

| When | Goal | Gate |
|---|---|---|
| Fri 10 PM to Sat 2 AM | Leader and follower calibrated, teleoperation working, camera mounted, one pick recorded and replayed | The arm replays a taught pick 5 times out of 5. If the arms are not moving by 2 AM, that is the only problem anyone works on. |
| Sat 2 AM to 9 AM | Sleep. One person may stay to print the camera mount and spoon holder. | |
| Sat 9 AM to 3 PM | Fetch works end to end by voice. In parallel, one person records the feeding scoop. | "Hand me the X" works 4 out of 5 times across 3 objects placed anywhere on the grid. |
| Sat 3 PM to 8 PM | Feeding with face tracking and the stop button. Coin counting on camera. | Feeding works 4 out of 5. If fetch is still below 4 out of 5 at 3 PM, drop coins and fix fetch. |
| Sat 8 PM | Feature freeze. Lock the track. No new skills after this. | |
| Sat 8 PM to 11 PM | Initial Devpost submission (title, track, draft text, repo link, repo public). Record a backup video of a real run. | Submitted by 11 PM, an hour early. |
| Sat 11 PM to Sun 2 AM | Harden: 20 runs in a row, fix what fails, write the reset procedure. LEGO stretch only if all three skills pass. | |
| Sun 7 AM to 8 AM | Final Devpost text, open source list, teammates listed. | Final submitted by 8:00 AM. |
| Sun 9 AM to 12:30 PM | Set up the table, rehearse the pitch out loud with a timer. | |

Every 2 hours on Saturday, ask whether we could demo right now. If the answer is no, stop adding and fix that.

## Who does what

Four lanes. Put names here tonight.

| Lane | Owner | First job tonight |
|---|---|---|
| Arm: teaching poses, replay, safety stop | Daniel (has the arms on his laptop) | Run the lift test, then teach the 3 by 3 grid of hover poses |
| Vision: camera mount, tags, grid mapping, object pointing, coins | | Mount the camera, photograph the real objects, run `see.py` on the photos |
| Voice and glue: speech in and out, intent, the main loop | | Test `see.py` with a live microphone, then add a spoken reply |
| Hardware and demo: spoon holder, gripper pads, stop button, table layout, Devpost, pitch | | Find out what the makerspaces can print or cut tonight and their hours |

## The demo (90 seconds at the table)

1. One line: who this is for and what feeding robots cost.
2. The judge puts three objects on the grid and asks for one. The arm hands it over.
3. The judge drops a handful of coins. The arm says the total and points at the quarter.
4. A teammate says "feed me". The arm scoops and holds the spoon out.
5. If something fails, say what failed, reset in 10 seconds, run it again. Have the backup video open in a tab.

Bring: dry scoopable food (cereal or M&Ms), a bowl with a non-slip base, a lamp, a dark mat for contrast, spare servos, tape, a power strip, a phone hotspot for the vision calls.

## Open questions for the team

- Which laptop runs the demo, and does it have a GPU? This decides local speech to text or a cloud call.
- Which camera, and can a makerspace print a mount tonight?
- Does anyone on the team count as a beginner? Not for the track, only for pairing.
