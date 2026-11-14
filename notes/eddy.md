# Eddy, Person 1 (agent: Claude Code)

Updated Sat Nov 14, 12:50 AM.

## Working on now

Person 1: voice, object finding, fetch by camera. Owns `voice/`, `learning/` and the root files `see.py`, `pick.py`, `grid.py`, `draw.py`, `arm.py`.

Next, in order:

1. Real photos and a live microphone through `see.py`, then the `pick.py` dry run with the camera mounted. Blocked on a person: this agent's terminal has no camera or microphone permission, and no external camera is connected anywhere yet.
2. `skills/fetch.py`, a thin skill around `pick.py`, so "bring me the X" runs through the dispatcher and the stop key. Blocked on `daniel/arm-core` reaching GitHub.
3. Spoken replies and passing the object name as a parameter in `voice/route.py`. Also blocked on `daniel/arm-core`.

## Done and how it was tested

None of the arm code has run on the real arm.

| File | What it does | Tested how |
|---|---|---|
| `see.py` | A typed or spoken request plus a camera frame gives the pixel of the named object. Gemini hears and finds in one call. | Synthetic image with shapes at known positions: within 6 px. Refuses objects that are not there. A synthesized voice clip worked. No real camera, microphone or photos yet. |
| `pick.py` | Pixel, to a position on a taught 3 by 3 grid, to hover, lower, close, lift, hand over. | Dry run on the synthetic image gives the right grid position and refuses out-of-reach objects. Grasp sequence ran against a simulated arm. |
| `arm.py` | `teach`, `pose`, `check`, `record`, `replay`. | Never run on hardware. `check` ran against a simulated arm. |
| `grid.py` | Blends taught poses so any point on the grid maps to joint angles. | Self-check passes. |
| `draw.py` | Pen strokes from the Quick, Draw! database, from text, or generated, with a preview. `--go` traces them through a taught paper grid. | Previews look right. `--go` ran against a simulated arm only. |

Changed at 12:50 AM after Ben's review (thank you, all four points were right):

- `arm.py teach` and `arm.py pose` now tell you to hold the arm and wait for Enter before the motors go limp.
- `draw.py --go` closes the gripper 8 units past the taught value so it squeezes the pen. Tune with `PEN_SQUEEZE`.
- New `python arm.py check table`: moves slowly to the points between taught poses, lifted layer first, waiting for Enter before each, so dips show up before a real grasp.
- `pick.py` now documents the flat-table error on tall objects and says to mount the camera straight above the middle of the grid, as high as possible. The error is not corrected in code.

Model facts, measured Sat 12:10 AM on Eddy's free Gemini key: `gemini-3.5-flash-lite` answered every test correctly in about 1 second. `gemini-3.6-flash` got 3 of 4 at 3 to 4 seconds. `gemini-3.7-flash` and `gemini-3.8-flash` returned server errors. The robotics-ER models are not on this key.

## Needs from others

- Daniel: please push `daniel/arm-core`. Items 2 and 3 above start the moment `core/arm.py` and `core/dispatcher.py` are visible. I will not touch `core/`, `voice/route.py` or `keypad/listen.py` until then, and will build on them, not replace them.
- Daniel: proposal for the camera, since WSL has none. The camera and microphone run in a small script on Windows, the same way `keypad/listen.py` does. It finds the object, converts it to a grid position, and sends the dispatcher `run fetch` with the position as parameters over localhost port 8765. The skill then needs no camera. Does the dispatcher accept parameters over that port, and in what format?
- Daniel: when you wrap `arm.py`, note that `follower()` sets `max_relative_target` to 15 per command (`MAX_STEP`). On your LeRobot 0.7.0, please confirm that is degrees for body joints.
- Whoever has a camera: mount it over the table and push three or four photos of the real objects (mouse, lanyard, Duplo) to `outputs/` or send them to Eddy. That unblocks item 1 without the arm.
- Ben: `draw.py` is yours to wrap as `skills/draw.py`. `from_text`, `from_quickdraw`, `from_gemini` return strokes; `preview` writes the image; `draw` moves the arm. Generated drawings take about 20 seconds, so make them ahead of time.
- Everyone: the Gemini key is not in the repo. Ask Eddy or make a free one at aistudio.google.com/apikey and put it in `.env`.

## Answers to questions other notes asked

- Daniel's note: agreed, the root files stay where they are and I own them. No YOLO or inverse kinematics from me.
- Ben, track: agreed it has to be settled. My recommendation is in `PLAN.md`; the desk-buddy framing fits Best Hardware Hack better than Accessibility. This is the humans' call before the Saturday midnight submission.
- Ben, camera and arm in one process: see the proposal to Daniel above.
