# Plan: Helping Hand (working name)

HackUMass XIV, Nov 13 to 15 2026. Rewritten Fri Nov 13 at 11:30 PM ET after the team pivoted. This replaces the assistive tabletop plan and the Duplo builder described in `context.md`. Section 10 of `context.md` (arm hardware, WSL setup, teleoperation commands) and its rules for AI agents still apply.

## What we are building

A vehicle with the SO-101 follower arm on the front. You give it one spoken request, such as "go to the kitchen and bring me the red brick". It drives there by camera, out of your sight, picks the item up, and drives back. After the voice request, nobody touches it.

Decisions the team has made:

- Navigation uses vision only. No markers or tags on the floor or walls.
- The route is a track we set up and practice on.
- Judging: we show a video of the full run, filmed during the hacking period, and at the table we demo the arm picking things up and the vehicle driving as two separate live pieces. That way we need no floor space.

## How it works

```
mic -> Gemini -> destination + item
drive: front camera frame -> "forward / left / right / arrived" -> motors, repeat
pick:  deck camera frame -> pixel of item (see.py) -> taught arm pose -> grasp
return: drive again with "home" as the destination
```

Calls made here; change them if a teammate knows better.

- Driving, first version: every step, send the front camera frame and the destination to Gemini and ask for one move (forward, left, right, arrived). Move a short fixed distance and ask again. It needs no training data and can work the hour the wheels turn. It is slow, about one move every 1 to 2 seconds, which is fine for a video.
- Driving, upgrade if there is time: drive the practiced route by remote 10 to 20 times, record frames and steering, and train a small network to steer from the image (the DonkeyCar method). It is smooth and fast but needs the remote driving and a training run first.
- The arm and a downward camera sit on one rigid deck at the front of the vehicle. They never move relative to each other, so the arm is taught a grid of poses over the patch of floor in front of the vehicle, and `see.py` turns the request into a pixel on that patch. The vehicle's job is to stop with the item inside the patch.
- Build and test the deck on a table first. The arm lane must not wait for the vehicle.
- One computer rides on the vehicle and runs everything over USB: arm, cameras, motor controller. The arm currently runs on Daniel's Windows laptop under WSL; decide tonight whether that laptop rides along or the Pi 5 takes over.
- Motors: an Uno or ESP32 with a motor driver takes simple serial commands (forward, left, right, stop) from the computer.
- Internet: only the Gemini calls need it. A phone hotspot rides on the vehicle.
- Safety: a physical switch that cuts motor and arm power, and a speed cap.

## Known hard parts

- The base. It carries the arm (about a kilogram, reaching forward), a computer and a battery. It needs to be low and wide with weight at the back so it does not tip when the arm reaches, and it has to stop within a few centimetres.
- Power. The follower needs 12 V at several amps from a battery, alongside the drive motors. Never put 12 V on the leader.
- Stopping in the right place. If the vehicle stops with the item outside the arm's patch, the pick fails. Expect to add a "creep forward until the item is in the patch" step.
- Picking from the floor. Test early that the arm reaches the floor from the deck height and can lift each item.

## Schedule (ET)

Idea changes stop at two thirds of the hacking period, about Saturday 8:50 PM. That is also the feature freeze.

| When | Goal | Gate |
|---|---|---|
| Fri 11:30 PM to Sat 2 AM | Choose the base (existing chassis or built at a makerspace), list parts, confirm makerspace hours. Spin one drive motor from code. Arm lane: teach the pose grid on a table and get one voice pick working. | A parts list and a base sketch exist. One motor turns from code. |
| Sat 2 AM to 9 AM | Sleep. | |
| Sat 9 AM to 1 PM | Base built and driving by keyboard while carrying the arm, computer and battery. Arm running from the battery. | It drives 3 metres, turns and stops without tipping. If not by 1 PM, simplify the base before anything else. |
| Sat 1 PM to 5 PM | Vision driving to one named place on the practice track. Deck bolted on; arm picks from the floor patch. | Reaches the destination 3 times out of 5. Picks from the floor 4 times out of 5 while parked. |
| Sat 5 PM to 9 PM | Full run: voice, drive, pick, return. | One complete run, however slow. |
| Sat 9 PM | Feature freeze and track locked. | |
| Sat 9 PM to 11 PM | Initial Devpost submission, repo public. | Submitted by 11 PM, an hour early. |
| Sat 9 PM to Sun 2 AM | Film the full run. Take as many attempts as it needs; keep the best. Also film the pick and the drive separately as backup. | One clean take of the full run, or honest separate clips if the full run never completes. |
| Sun 7 AM to 8 AM | Final Devpost text and video. | Final submitted by 8:00 AM. |
| Sun 9 AM to 12:30 PM | Set up the table and rehearse the two live pieces. | |

## Who does what

| Lane | Owner | First job tonight |
|---|---|---|
| Base and power: chassis, motors, battery, kill switch | | Decide the base and get one motor turning from code |
| Driving: front camera, vision steering, stop-at-item | | Write the step-driving loop against a phone video of the track |
| Arm and pick: deck, camera, pose grid, grasps | Daniel | Teach the grid on a table and run a voice pick with `see.py` |
| Voice, glue and submission: request parsing, the run loop, video, Devpost | | Parse "go to X and bring me Y" into destination and item |

## Judging

Deadlines: initial submission Sunday 12:00 AM (Saturday midnight). Final is 10:00 AM ET on Devpost and 9:00 AM on hackumass.com; we work to 9:00 and submit by 8:00. Table judging is 12:30 to 3:00 PM.

At the table:

1. The full-run video plays on a loop.
2. Live: the judge asks for an item by voice and the arm, on the parked vehicle, picks it up.
3. Live: the vehicle drives a short stretch on the table or the floor beside it.

Say plainly in the pitch and on Devpost that the route is one we practiced. All video must be filmed during the hacking period.

The four criteria are Innovation, Functionality, Practicality and Presentation. Functionality is scored on what the judges see work, so the two live pieces have to be reliable even if the full run only worked once on camera.

## Track

Pick one [HACKUMASS] category. Now that we are building the base ourselves, the candidates are:

| Category | Fit | Prize |
|---|---|---|
| Best Accessibility Hack | Strong if we pitch it as fetching things from another room for someone who cannot get up | Life 360 Tiles |
| Best Hardware Hack | Good. A custom vehicle with an arm is clearly hardware. Probably the most contested. | Arduino Uno |
| Best Mechanical Hack | Good only if the base is a real mechanical build worth showing | Mechanical keyboard |
| Best MedTech Hack | Weaker than before; the feeding skill is gone | Fitbit |

Lean: Accessibility, with Hardware as the alternative. Lock it at the Saturday 9 PM freeze. Opt in to Best Use of Gemini API, since Gemini does the hearing, driving decisions and item finding.

## Rules that can disqualify us

- No work from before Friday 8:30 PM.
- Disclose open source in the README.
- The repo must be public at submission. It is private now.
- Four people at most.

## Open questions

- What is the base: an existing chassis, or built from makerspace parts? What motors and battery do we have?
- Which computer rides on the vehicle?
- Where is the practice track, and can we keep it set up through Saturday night for filming?
- How high does the deck sit, and can the arm reach the floor from there?
