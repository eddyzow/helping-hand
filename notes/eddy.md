# Eddy, Person 1 (agent: Claude Code)

Updated Sat Nov 14, 3:32 AM.

## Working on now

Person 1: voice, object finding, fetch by camera. Owns `voice/`, `learning/` and the root files `see.py`, `pick.py`, `grid.py`, `draw.py`, `arm.py`.

Branch `eddy/fetch` (commit `f652789`), built on `daniel/arm-core` with `main` merged in:

- `skills/fetch.py`: takes a grid position (`u`, `v`), checks it before any move, then home, hover, lower, close, lift, hand over, hold, release, home. Stops cleanly at every step.
- `voice/route.py`: for fetch it now grabs a camera frame, finds the object with `see.py`, converts the pixel to a grid position with `pick.py`, and sends `run fetch {"object", "u", "v"}`. It also speaks short replies with the computer's own voice ("Getting red brick", "I can't see the banana", "I'm busy").
- `tests/test_fetch.py`: `python -m tests.test_fetch` prints `fetch ok`. `tests.test_core` still prints `core ok`.

Tested on the mock arm only: a mock dispatcher on a spare port, typed requests through `voice/route.py`, a synthetic test image in place of the camera. "bring me the red brick" started fetch at the right grid position, "grab the banana" was refused as not visible, a fetch sent during a wave got "busy". Never run on the real arm, a real camera or a live microphone.

Real photos, tested Sat 1:15 AM: two phone photos of the Duplo set are in `photos/`. Across both, 15 of 16 requests for objects in view landed on the right object ("the purple brick", "the white flat brick", "the green brick", "the car chassis with wheels", "the blue car body", "the blue square brick", "the red triangle brick", "the red square brick"), about 1.3 seconds each. Banana and computer mouse were correctly reported as not there. The one miss: in `duplo_b.jpg` the red slope brick lies on its side and does not look triangular, so "the red triangle brick" came back not found. Three requests in a burst of 16 failed with an API error and worked on retry; `see.py` now retries once after 3 seconds and prints the error.

Eddy checked the marks on both photos himself at 1:30 AM and corrected my score: the finder silently picks one of the two red square bricks, and on `duplo_b.jpg` it missed the red bricks. Follow-up tests on those hard cases:

- Gemini `gemini-3.5-flash-lite`: points land accurately on the object it picks, but it under-counts look-alikes (one red square where there are two) and missed the slope brick lying on its side until the prompt described it. The free key hits a per-minute rate limit (HTTP 429) after roughly 15 requests in a burst. Larger Gemini models time out.
- Claude (Eddy's Anthropic key, in `.env` as `ANTHROPIC_API_KEY`): lists all 9 objects every time and counts matches better (Opus 5.5 6 of 7 cases, Sonnet 5.5 and Haiku 5.5 5 of 7), at about 3 seconds for Sonnet and 7 to 10 for Haiku and Opus. Its points are loose: several land beside the object, not on it.
- OpenAI (Eddy's key, in `.env` as `OPENAI_API_KEY`), same cases: `gpt-6.1-sol` 5 of 7 at about 9 seconds, `gpt-6.1-terra` 4 of 7 at about 5 seconds, `gpt-6-luna`, `gpt-5.5` and `gpt-5.4-mini` 2 or 3 of 7. Points land on the pieces more often than Claude's but several sit on an edge. Not better than Claude at choosing, and slower.
- So Gemini is good at where and weak at which; Claude is the reverse. Neither alone is good enough for a reliable grasp among look-alike bricks.

Fix, built and on `main` at 2:00 AM: `see.py` now works in two steps. Gemini boxes every object on the table (it is accurate at where). The boxes are numbered on the image and Claude Sonnet 5.5 says which numbers match the request (it is accurate at which). On the two real photos the chooser got 16 of 17 requests right, and the full pipeline got 8 of 8 in a later run, including both red squares and the slope brick on its side. About 4.5 seconds per request. Plain OpenCV colour detection was tried first and was too fragile on the grey table: it missed pieces and took glare for pieces.

What changed for callers: `see.find_all(frame, command, audio_path)` returns `(hits, said, boxes)`. `see.find` still exists and returns the first hit. `pick.locate` now returns `(targets, said)`, a list, and `pick.py` asks "which one?" when more than one object matches instead of picking silently. `eddy/fetch` has the matching `voice/route.py` and is open as pull request 3 (https://github.com/eddyzow/helping-hand/pull/3), ready for review and merge.

Live microphone, tested by Eddy on his Mac at 2:25 AM: he said "pick up the purple brick" into the laptop microphone with `photos/duplo_a.jpg` as the frame. It heard "Pick up the purple brick.", saw 9 objects and matched the purple brick. One run, in a quiet spot; not tried in a noisy room.

Known limits: two touching pieces come back as one box. The grasp point is the box centre, which is a hole on hollow pieces like the upside-down car body. Gemini's free tier still has bad spells (429, 503, timeouts); `see.py` retries up to three times, and one request in this run took 17 seconds because of it. `ANTHROPIC_API_KEY` is needed for the chooser; without it Gemini chooses and gets look-alikes wrong more often.

Also: from 1:16 AM to 2:00 AM `see.py` on `main` had an 8 second timeout that Gemini rejects (minimum 10), so every request failed. That was my bug and it is fixed.

Next:

1. A live microphone and a photo from the real camera position. The finder itself is now proven on real photos.
2. First real fetch, in an arm slot with Daniel, after the poses below are taught.

## Simulation findings (read before the first real grasp)

`sim.py` on `eddy/fetch` (pull request 3) runs fetch in MuJoCo: a rendered overhead camera, the real finder, the real `skills/fetch.py`, and physics for the bricks. Four Duplo-sized bricks were each picked up and carried to the handover; two of those runs went through the whole camera-to-handover path. Its poses come from inverse kinematics, not teaching, and the model's joint zero differs from the real arm's (Daniel's taught home has the elbow at 127 degrees; the model stops at 97), so treat these as leads to check on the arm, not facts about it.

- A 3 by 3 taught grid is too coarse. Blending joint angles put the gripper 7 mm off between taught points (12 mm at worst), and the grasp failed. 4 by 4 gave 3 mm (5 at worst), 5 by 5 gave under 2 mm (3 at worst). `arm.py teach` now defaults to 5 by 5; `python arm.py teach table 4` for 4 by 4.
- The grasp is tight. A 32 mm brick was carried when the gripper was within about 6 mm of the right spot and dropped outside that.
- The model's gripper reference point is the tip of one jaw, not the middle of the opening. Daniel: when teaching the table grid by hand, put a brick on each grid point and pose the arm with the brick between the open jaws. Posing the fixed jaw over the mark will lower it onto the brick.
- Open the gripper fully before going down. At 60 of 100 the jaw landed on top of the brick. `GRIP_OPEN` now defaults to 100.
- Pointing straight down, the model reaches about 12 to 30 cm from its base and can lift about 5 cm. That is the size to plan the table grid around.
- Daniel, for `core/arm.py`: `move_joints` starts every move from the measured joints. While holding a brick the jaw is blocked at about 19 with a command of 5, so each new move starts its gripper command near 19 and ramps back to 5: the squeeze relaxes for a moment at the start of the lift and of the swing. The simulated brick survived it. On the real arm it may not. Suggest starting the gripper from the last commanded value. I have not touched `core/`.
- Gemini's box detection slowed to 14 seconds around 2:30 AM, past its 10 second timeout. `see.py` now falls back to OpenAI (`gpt-6.1-terra`) for the boxes when Gemini fails and `OPENAI_API_KEY` is set: on `photos/duplo_a.jpg` its boxes overlapped Gemini's on 8 of 9 pieces, in about 5 seconds. Claude's boxes were poor (2 of 9), so Claude stays the chooser only.

Update 2:45 AM: the simulated table now holds the Duplo set from `photos/duplo_a.jpg` (two red squares, blue square, purple square, flat white 2x4, red slope, green curved 2x4, car chassis, car body), and `mjpython sim.py --view` opens a live MuJoCo window that takes typed requests one after another. With known grid positions, 6 of the 7 graspable pieces were carried to the handover; the flat white plate is too thin for the fixed grasp height. Through the full finder, 4 of 5 single-match requests were carried (purple, red slope, green curved yes; blue square was found correctly and dropped), two red squares got "which one", and the chassis outside the grid was refused as out of reach.

Update 2:55 AM: Eddy sent close-ups showing three simulated pieces were the wrong shape, and they are remodelled. The red "triangle" is a 2x4 ridge roof (two slopes meeting at a ridge, about 38 mm tall, no studs). The green piece is a 2x4 brick with studs on top and an underside that curves up at both ends. The car body is a hollow open-top shell with wheel arches, three studs and a hitch at the back. The roof and the green brick were each still carried to the handover in simulation. Their sizes are estimated from photos, not measured.

Update 3:00 AM: the simulated car body is now a sculpted curved mesh (`sim_assets/car_body.stl`, built by `sim_assets/make_car_body.py`), not boxes. Blender was not reachable and no downloadable model of the real part turned up, so it is shaped by hand from Eddy's photos. The live window now starts zoomed in on the pieces and prints its mouse controls.

Update 3:15 AM: on `eddy/fetch`, fetch can now put an object down beside another one. Say "put the red triangle next to the purple brick": the chooser returns both objects, `pick.drop_spot` picks a place beside the second one, and `skills/fetch.py` takes optional `to_u` and `to_v` and sets the object down there instead of handing it over. Mock tests cover it, and two requests ran in simulation (the triangle moved 4 cm toward the purple brick; a brick sent "near the car body", which is out of reach, went to the nearest edge of the grid). Also: `see.load_env` now lets `.env` override keys exported in the shell, after an expired `OPENAI_API_KEY` in Eddy's shell broke a run. Still open: in Eddy's live run the purple brick, which sits turned 45 degrees, was lifted and then dropped. The arm cannot turn its wrist to match a brick's angle yet.

Update 3:32 AM, on `eddy/fetch`:

- Position words settle ties in code: "the closest red brick", "farthest", "left", "right" keep one of several matches (`pick.narrow`). Left and right are the arm's own.
- The wrist now turns to match a piece. `see.long_axis` reads which way a piece lies from the image (plain OpenCV inside the finder's box); in simulation it read seven pieces within 1 degree. `pick.jaw_turn` converts that to a turn, and `skills/fetch.py` takes `turn` in degrees and adds it to `wrist_roll`. This needs every grid point taught with the jaws closing left-right across the table, and three numbers for the real setup: `GRID_ASPECT` (grid width over depth), and `JAW_ARM_MM`, `GRID_WIDTH_MM`, `GRID_DEPTH_MM` so fetch can cancel the grasp point swinging as the wrist turns (16 mm on the model). `ROLL_SIGN` flips the direction.
- With that correction the grasp point lands within about 1 mm of its target at every turn from -90 to 90 degrees in simulation. Grasping is still unreliable: with known positions 5 of 7 pieces were carried (one turned red square and the thin white plate were not), and two full-pipeline requests on turned bricks both dropped the brick. I do not know why yet; positioning is not the cause.
- The simulator's pieces were lying at wrong angles before this (the model file measures in radians and I had given degrees). Fixed.
- Eddy's goal is the car body placed onto the chassis. Not attempted. It needs the two pieces within reach, a known grip point on the body, and matching both pieces' directions.

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

- Daniel's reviewer, on torque toggling during connect: fixed at 2:15 AM. The warning now sits inside `arm.follower()`, before the connection, so every caller gets it, including `core/arm.py`. Set `ARM_NO_PROMPT=1` to skip it in unattended runs. Mock tests still pass; not run on hardware.

- Daniel's note: agreed, the root files stay where they are and I own them. No YOLO or inverse kinematics from me.
- Ben, track: agreed it has to be settled. My recommendation is in `PLAN.md`; the desk-buddy framing fits Best Hardware Hack better than Accessibility. This is the humans' call before the Saturday midnight submission.
- Ben, camera and arm in one process: see the proposal to Daniel above.
