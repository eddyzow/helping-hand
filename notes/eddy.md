# Eddy, Person 1 (agent: Claude Code)

Updated Sat Nov 14, 1:15 AM.

## Working on now

Person 1: voice, object finding, fetch by camera. Owns `voice/`, `learning/` and the root files `see.py`, `pick.py`, `grid.py`, `draw.py`, `arm.py`.

Branch `eddy/fetch` (commit `f652789`), built on `daniel/arm-core` with `main` merged in:

- `skills/fetch.py`: takes a grid position (`u`, `v`), checks it before any move, then home, hover, lower, close, lift, hand over, hold, release, home. Stops cleanly at every step.
- `voice/route.py`: for fetch it now grabs a camera frame, finds the object with `see.py`, converts the pixel to a grid position with `pick.py`, and sends `run fetch {"object", "u", "v"}`. It also speaks short replies with the computer's own voice ("Getting red brick", "I can't see the banana", "I'm busy").
- `tests/test_fetch.py`: `python -m tests.test_fetch` prints `fetch ok`. `tests.test_core` still prints `core ok`.

Tested on the mock arm only: a mock dispatcher on a spare port, typed requests through `voice/route.py`, a synthetic test image in place of the camera. "bring me the red brick" started fetch at the right grid position, "grab the banana" was refused as not visible, a fetch sent during a wave got "busy". Never run on the real arm, a real camera or a live microphone.

Real photos, tested Sat 1:15 AM: two phone photos of the Duplo set are in `photos/`. Across both, 15 of 16 requests for objects in view landed on the right object ("the purple brick", "the white flat brick", "the green brick", "the car chassis with wheels", "the blue car body", "the blue square brick", "the red triangle brick", "the red square brick"), about 1.3 seconds each. Banana and computer mouse were correctly reported as not there. The one miss: in `duplo_b.jpg` the red slope brick lies on its side and does not look triangular, so "the red triangle brick" came back not found. Three requests in a burst of 16 failed with an API error and worked on retry; `see.py` now retries once after 3 seconds and prints the error.

Next:

1. A live microphone and a photo from the real camera position. The finder itself is now proven on real photos.
2. First real fetch, in an arm slot with Daniel, after the poses below are taught.

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

- Daniel: `eddy/fetch` is ready for review and for merging with `daniel/arm-core`. It adds `skills/fetch.py` and `tests/test_fetch.py` and changes only `voice/route.py`. It does not touch `core/`.
- Daniel: `voice/route.py` has to run where the camera and microphone are, which is Windows on your laptop, the same as `keypad/listen.py`. It needs the repo requirements installed there and `.env` with the Gemini key.
- Daniel: for the first real fetch, in an arm slot, teach `handover` (`python arm.py pose handover`), then `python arm.py teach table`, then run `python arm.py check table` and watch for dips. Then `python pick.py --corners` on the camera machine. Try `run fetch {"u": 0.5, "v": 0.5}` from the dispatcher before involving the camera.
- Daniel: the camera looks while the arm is at `home`. If the camera is on the wrist, `home` has to point it at the table; if it is a separate camera, `home` has to keep the arm out of its view. Which camera are we using?
- Daniel: `arm.py follower()` sets `max_relative_target` to 15 per command (`MAX_STEP`). On LeRobot 0.7.0, please confirm that is degrees for body joints.
- Ben: `draw.py` is yours to wrap as `skills/draw.py`. `from_text`, `from_quickdraw`, `from_gemini` return strokes; `preview` writes the image; `draw` moves the arm. Generated drawings take about 20 seconds, so make them ahead of time.
- Everyone: the Gemini key is not in the repo. Ask Eddy or make a free one at aistudio.google.com/apikey and put it in `.env`.

## Answers to questions other notes asked

- Daniel's note: agreed, the root files stay where they are and I own them. No YOLO or inverse kinematics from me.
- Ben, track: agreed it has to be settled. My recommendation is in `PLAN.md`; the desk-buddy framing fits Best Hardware Hack better than Accessibility. This is the humans' call before the Saturday midnight submission.
- Ben, camera and arm in one process: see the proposal to Daniel above.
