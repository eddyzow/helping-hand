# Eddy, Person 1 (agent: Claude Code)

Updated Sat Nov 14, 1:08 PM.

## Working on now

Merged at 4:40 AM: pull request 3 (`eddy/fetch`) is on `main` as `3d49b9e`, at Eddy's request. `main` now has `skills/fetch.py` (hand over, or put down beside another object, with a wrist turn), the camera-aware `voice/route.py`, the two-step finder with its OpenAI backup, `sim.py` with the Duplo set, and `tests/test_fetch.py`. On the merged `main`, `tests.test_fetch`, `tests.test_core` and `grid.py` all pass. The simulator and the finder changes were reviewed only by me; the fetch checks were reviewed by Daniel's reviewer. Anything below that says "on `eddy/fetch`" now means `main`.

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

- Daniel, when Geometry Dash can spare the arm for about 30 minutes: the first real pick-up. Nothing here is urgent enough to interrupt Jonathan's timing work. Everything is on `main`. In order, stopping at the first thing that goes wrong:
  1. `python arm.py pose handover`: save where the arm should hold an object out. This also shows whether `arm.py` imports cleanly on your LeRobot.
  2. With the leader, open and close the gripper on a 2x2 Duplo and note the gripper readings fully open and squeezing. Those become `GRIP_OPEN` and `GRIP_CLOSED` (defaults 100 and 5 are guesses).
  3. `python arm.py teach table 4`: a 4 by 4 grid is 32 hand poses. At each point put a brick on the mark and pose the arm with the brick between the open jaws, jaws closing left to right across the table, first at grasp height, then lifted about 5 cm. In simulation a 3 by 3 grid missed by 7 mm and failed; 4 by 4 missed by 3 mm.
  4. `python arm.py check table`: slow pass between the taught points. Watch for dips into the table.
  5. Start the dispatcher and type `run fetch {"u": 0.5, "v": 0.5}` with a brick at the grid's centre. No camera involved. This is the test that matters: does a taught grasp hold a brick to the handover.
  6. Write down what happened, including a failure. Ten real grasps tell us more than tonight's simulation did.
  Things the simulation suggests watching for: the jaw landing on top of the brick if the gripper is not fully open on the way down; the grip loosening for a moment at the start of each move (the `move_joints` point above); and bricks turned at an angle being dropped.

- Daniel's reviewer: the last fetch finding is fixed in `f271764` (4:45 AM) on `main`. The chooser now says whether the person asked to put the object somewhere; if they did and that place is missing or ambiguous, `voice/route.py` and `sim.py` refuse and say why (`pick.place_problem`). " on " and " by " no longer split a request, so "the brick on the left" keeps its position word. Self-checks cover it; in simulation "put the red triangle next to the banana" was refused and "put the green brick next to the white brick" moved the brick.

- Everyone, from Eddy at 4:07 AM: Geometry Dash has run on the real arm. In his words it "seems decent" and the team is working on timing offsets. My earlier lines in this note saying nothing had run on the real arm were wrong about Geometry Dash; they came from the notes in the repo, which did not record it. Ben: the Devpost and demo drafts can stop treating it as mock only once Jonathan or Daniel writes down what was run and what was measured.

- Ben, from Eddy himself at 4:05 AM (his words, not my reading): the team's skill list is "gd (almost done), duplo (almost done), then we are doing drawing tomorrow, and feeding food and water also tomorrow." He does not recognise the list in `docs/demo.md` and `docs/devpost.md`, which leaves out feeding and Duplo and adds wave and voice fetch as their own blocks. Please rebuild the script and the Devpost draft around his list. The 4 of 5 gate still applies to each.
- Ben: Eddy says the project will not be called "Helping Hand". The name is for the four of you to settle in the morning. Treat the title in the Devpost draft as a placeholder.
- Ben: `docs/demo.md` says "Eddy leans Hardware". That was my recommendation, not his position. He says the team is not sure yet.
- Ben: Eddy does not want an organizer question about AI coding tools; he treats their use as expected at hackathons this year. Decision 4 in the Devpost draft can come out.
- Ben, three stale facts in your drafts: fetch's grip and hold-time settings are now checked before any move (`b274c92`), so the "do not widen this" caveat can go. The finder now falls back to OpenAI for the boxes when Gemini stalls, so the demo machine needs `OPENAI_API_KEY` as well, or it retries Gemini alone. And the finder took about 20 seconds on most runs tonight because Gemini kept timing out; 25 seconds for a fetch block is tight.

- Daniel: `eddy/fetch` is ready for review and for merging with `daniel/arm-core`. It adds `skills/fetch.py` and `tests/test_fetch.py` and changes only `voice/route.py`. It does not touch `core/`.
- Daniel: `voice/route.py` has to run where the camera and microphone are, which is Windows on your laptop, the same as `keypad/listen.py`. It needs the repo requirements installed there and `.env` with the Gemini key.
- Daniel: for the first real fetch, in an arm slot, teach `handover` (`python arm.py pose handover`), then `python arm.py teach table`, then run `python arm.py check table` and watch for dips. Then `python pick.py --corners` on the camera machine. Try `run fetch {"u": 0.5, "v": 0.5}` from the dispatcher before involving the camera.
- Daniel: the camera looks while the arm is at `home`. If the camera is on the wrist, `home` has to point it at the table; if it is a separate camera, `home` has to keep the arm out of its view. Which camera are we using?
- Daniel: `arm.py follower()` sets `max_relative_target` to 15 per command (`MAX_STEP`). On LeRobot 0.7.0, please confirm that is degrees for body joints.
- Ben: `draw.py` is yours to wrap as `skills/draw.py`. `from_text`, `from_quickdraw`, `from_gemini` return strokes; `preview` writes the image; `draw` moves the arm. Generated drawings take about 20 seconds, so make them ahead of time.
- Everyone: the Gemini key is not in the repo. Ask Eddy or make a free one at aistudio.google.com/apikey and put it in `.env`.

## Answers to questions other notes asked

- Daniel's reviewer, findings on `eddy/fetch` through `00f02d5`: all addressed in `b274c92` (3:50 AM), with regressions in `tests/test_fetch.py` and the self-checks in `pick.py`.
  - A wrist turn that carries the corrected target off the grid is refused before any move, not clamped.
  - `GRIP_OPEN` and `GRIP_CLOSED` must be finite and 0 to 100, `HOLD_SECONDS` finite and 0 or more, checked before any move.
  - `arm.py teach` refuses a grid size below 2 before connecting, so a bad size cannot wipe a taught grid.
  - A position word only narrows the object it describes: "put the red brick next to the right blue brick" leaves two red bricks ambiguous (`pick.split_request`).
  - More than one match for the place to put something is refused in `voice/route.py` and `sim.py`; it no longer falls back to a handover.
  - The `beside` field is gone from the command parameters.
  - README now gives the grip default as 100.

- Daniel's reviewer, on torque toggling during connect: fixed at 2:15 AM. The warning now sits inside `arm.follower()`, before the connection, so every caller gets it, including `core/arm.py`. Set `ARM_NO_PROMPT=1` to skip it in unattended runs. Mock tests still pass; not run on hardware.

- Daniel's note: agreed, the root files stay where they are and I own them. No YOLO or inverse kinematics from me.
- Ben, track: agreed it has to be settled. My recommendation is in `PLAN.md`; the desk-buddy framing fits Best Hardware Hack better than Accessibility. This is the humans' call before the Saturday midnight submission.
- Ben, camera and arm in one process: see the proposal to Daniel above.

## Reviewer findings closed Sat Nov 14, 10:24 AM (commit `b49533d`)

- Daniel's reviewer: a chooser reply with `put_down` missing or not true/false now picks nothing (`see.to_choice`), so it can never become a handover. Checks are in the `see.py` self-check.
- Standalone `pick.py` refuses a request that asks to put something down, before any grasp. Checked with a fake finder: refusal for a placement, unchanged for a plain pick-up.
- Root `draw.py` rejects a taught paper pose that is not a finite number before the clamp. Import checked only; not run.
- `fetch ok` and `core ok` still print. Nothing here ran on the arm.

## Gemini removed Sat Nov 14, 10:34 AM

Eddy asked for Gemini to go: its free tier timed out or refused most requests. Everything older in this note that says Gemini does a step is out of date.

- `see.py`: OpenAI `gpt-6.1-terra` boxes the frame, OpenAI `gpt-4o-mini-transcribe` writes down speech, Claude Sonnet 5.5 chooses. `voice/route.py`: Claude Haiku 5.5 picks the skill from the written-down sentence. `draw.py --gen`: Claude. `google-genai` is out of `requirements.txt`.
- Everyone: `.env` now needs `OPENAI_API_KEY` and `ANTHROPIC_API_KEY`; `GEMINI_API_KEY` is unused. `.env` also wins over keys exported in the shell, in `voice/route.py` too.
- Tested: `python see.py --image photos/duplo_a.jpg "pick up the purple brick"` found 9 objects and the purple brick; `draw.from_model("a rocket")` returned 9 strokes; `fetch ok`, `core ok`. A simulated request takes about 13 seconds end to end. Not tested: the new speech-to-text call with a real recording, and `voice/route.py` against a dispatcher.
- `sim.py`: the pieces are now 9 to 10 cm apart (Eddy saw the open jaws knock neighbours at 6 cm) on a wider grid. Six simulated pick-ups: purple (turned 45), left red square and red triangle carried to the handover; blue square, right red square and green brick were not, with no other piece disturbed. So spacing was one cause, not the only one.

## Wrist limit fix and more placements, Sat Nov 14, 10:54 AM

- Eddy saw turned bricks being grabbed with one jaw on a face and one on a corner. Cause, measured in the simulator: the wrist turn pushed `wrist_roll` past its joint limit, the joint stopped 12 degrees short, and the brick dropped. `skills/fetch.py` now turns the other way round (the same grasp) when the turn would pass `ROLL_MIN`/`ROLL_MAX` (default -150 and 150), and refuses if neither way fits. Daniel: set those two from the real arm's wrist range. Six of seven simulated pieces now reach the handover through the whole camera path; the thin white plate still does not, and the blue square is still not lifted (two arm joints stop short of their targets there, so something is in the way; not found yet).
- New in fetch: `to_lift` (0 to 1, lets go partway between the table layer and the lifted layer, for "on top of") and `hold` (seconds to hold it up, 0 to 30).
- New in `pick.drop_spot(picked, near, said)`: returns `(u, v, lift)`. "left of", "right of", "behind", "in front of" pick the side (the arm's own left and right; in front is towards the arm); "on top of" and "onto" stack. `STACK_LIFT` (default 0.5) has to be set on the real arm so the held brick just touches the one below.
- Simulated: purple stacked on a red square (resting 19 mm up, twice); red triangle put left of the green brick; a red square put behind the purple brick landed on the edge of the red triangle and slid off, because the drop spot still does not check for other pieces.
- The chooser prompt now tells Claude to ignore position words and list every object of the kind; the code picks by position. Before that, "the left red square brick" came back with no match in two of three runs.
- Not done: car body onto the chassis. It needs both in reach, a taught grip on the body, the body's direction matched to the chassis, and pressing it on.

## No keyword matching any more, Sat Nov 14, 11:08 AM

Eddy: "your system looks like it uses hardcoded keywords. that wont work if we are having an llm parse". This replaces the section above about `pick.drop_spot`.

- The chooser (Claude Sonnet 5.5) now gets every box's position on the taught grid as text (centre and span in u, v) and returns `{"matches", "put_down", "place": {"u", "v", "on_top"}}`. It settles left, right, closest, "a/any", and works out the exact drop point: on top of a piece, a named end of a piece, a side of a piece, between two pieces, a corner of the table.
- Removed from `pick.py`: `PLACE_WORDS`, `split_request`, `TIEBREAKS`, `narrow`, `drop_spot`, `place_problem`. `pick.locate` returns `(targets, said, place, problem)`; `place` is `(u, v, lift)` or None; a `problem` must be refused, never handed over. Removed from `voice/route.py`: `by_keyword`, so routing needs `ANTHROPIC_API_KEY`.
- I edited two shared tests to match: `tests/test_core.py` no longer imports or checks `by_keyword`; `tests/test_model_adapters.py` loads `by_model` and `main` only. `core ok`, `model adapters ok`, `fetch ok`.
- Simulated, one run each: purple onto the white plate (resting on it); a square brick onto the far right end of the green 2x4 (landed there); the left red square behind the purple brick; the triangle to the front right corner (it chose the corner, which was occupied, and landed on that brick; the prompt now says to use the nearest free spot); green between the two red squares; "the closest red brick". "stack the blue one on the red square on my right" was parsed correctly but the blue square is still not lifted in this layout.
- Known: a box at the robot's own base was once picked as "the triangle brick"; the prompt now says boxes at v above 1 are the robot.

- For Daniel's reviewer: I changed four of your tests to follow this rewrite. `tests/test_placement_options.py`: the two `drop_spot` checks are gone with the function; the fetch `to_lift` and `hold` checks are kept. `tests/test_perception_boundaries.py`: the chooser check now covers `put_down` plus `place`, and the standalone check covers a place, a problem, and a plain handover. All ten modules in `tests/` print ok.

## Simulator findings that matter on the real arm, Sat Nov 14, 11:43 AM

- Daniel, when teaching the table grid: put the jaw tips almost on the table (3 to 6 mm up). With the tips 10 mm up, only the top of a 19 mm brick was between the jaws and two of seven simulated pieces tipped out during the swing to the handover; at 3 to 6 mm, six of seven were carried (the thin white plate still is not).
- Daniel: check which way round the wrist is when you teach. In the model, with the jaws one way round the wrist camera mount hits the arm's own shoulder for targets near the middle of the table, 12 to 16 cm out; the other way round, nothing collides anywhere on the grid. That was why the blue brick was never lifted.
- I tested my earlier worry that `core/arm.py` relaxes the squeeze at the start of each move: in the simulator, keeping the squeeze made no difference to the drops, so it is lower priority than I said. `KEEP_SQUEEZE=0` in `sim.py` shows today's behaviour.
- Stacks: the chooser now returns heights in mm (`pick_height_mm`, `place.height_mm`), and fetch takes `lift` (grasp height) and `to_lift` (release height), both as a share of the way from the table layer to the lifted layer. `pick.LAYER_GAP_MM` (default 40) must be measured on the real grid. `STACK_LIFT` and `on_top` are gone.
- Simulated: a brick onto a plate works. A second brick onto that stack is carried to the right height (29 mm) but knocks the stack on release; not solved. Picking a brick off a stack went to the wrong piece once.
- `sim.py` now starts with a random layout, all nine pieces with their centres on the grid; `--seed N` repeats one, `--fixed` gives the two tidy rows. With nine pieces in a 29 by 11.5 cm grid they sit 0.5 to 3 cm apart, so the open jaws do knock neighbours.

## Lining up when stacking, Sat Nov 14, 12:24 PM

- Eddy saw a brick put onto another land turned and slide off. Fix: the chooser names the piece it goes onto (`place.onto`), `pick.locate` reads that piece's direction from the image, and fetch takes `to_turn` so the wrist is turned to match it at release. On the table it keeps the turn it was picked up with. `pick.locate`'s place is now `(u, v, lift, turn)`.
- This also fixed the second layer: without the turn at release, the second brick knocked the stack every time; with it, blue on purple on the white plate stands (blue resting 28 mm up), both with exact positions and through the camera.
- "Closest" went to the farthest piece once. Each object's distance from the robot is now in the text the chooser gets (`pick.ROBOT_UV`, default u 0.5, v 1.6: measure where the arm's base is relative to the taught grid). Two runs since: both picked the nearer red piece.
- `see.parse_reply` used to return nothing when Claude explained itself with brackets before the JSON, which showed up as "0 match" on some runs. It now tries a fenced block first, then the widest list or object.
- Random layouts, purple onto green: placed and lined up on seeds 3 and 11. On seed 11 the car body was knocked while reaching past it; pieces are close together in random layouts.
- All ten modules in `tests/` print ok. `tests/test_perception_boundaries.py` was edited again for the `onto` field.

## Why stacks fell, and three fixes in fetch, Sat Nov 14, 12:49 PM

Measured in the simulator by logging the gripper and the bricks step by step. Daniel, all three will apply on the real arm, with its own numbers:

- A gripped brick is not where the jaws were centred. Closing the one moving jaw pushes it towards the fixed jaw: 8.4 mm across and 4.1 mm along in the model. Put down without allowing for that, it lands that far off. New knob `HELD_SHIFT_MM` ("across,along", default "0,0" = off): grip a brick, set it down with no turn, measure how far it landed from the aim.
- After letting go, the fixed jaw is still against the brick and drags it as the arm lifts. Fetch now first moves the open jaws to centre on the piece, then lifts.
- A two-brick stack is nearly as tall as the taught lifted layer, and the open jaw swept through its top on the way home. Fetch now rises to `EXIT_LIFT` (default 1.5 times the layer gap, by extending the taught poses upwards) and goes home with the jaws still open.
- Result: blue on purple on the white plate stood at five wrist angles with exact positions (landing within 3 mm), and in 4 of 5 runs through the camera.
- The chooser prompt now lists the measured height of each piece in our set (white 2x4 is a 10 mm plate, bricks 19 mm). Eddy asked for this after it took the plate for a brick. It still said 19 instead of 29 for a brick on the plate once in five runs.
- All ten modules in `tests/` print ok.

## Placement accuracy, Sat Nov 14, 1:01 PM

Eddy: bricks landed a little off and then slid or jumped into place. Measured in the simulator:

- The detector's box centre was 2.8 mm from the piece's true centre on average (3.9 worst). The middle of the piece's outline, moved towards the middle of the picture to allow for the piece's height, is 0.6 mm off (1.1 worst). `pick.py` now uses that for the piece picked up and the piece it goes onto. It needs `CAMERA_HEIGHT_MM` (camera straight above the table; 0 = off). In a crowded layout the outline can swallow a neighbour, so if it strays from the box the box centre is used.
- Claude's place is rounded to 0.01 of the grid (3 mm) and comes from the loose box. When it means the middle of a piece, the code now uses the measured middle; when it means a part of a piece (an end), its offset from the box centre is kept.
- The jumping: a gripped brick hangs about 8 mm lower in the jaws than where it was gripped, so the arm was pressing it into the brick below and it sprang out on release. New knob `pick.HELD_DROP_MM` (0 = off) lets go that much higher.
- Result, two runs of four stacking requests through the camera: bricks landed 1.7 to 5.2 mm from the centre of the piece below, and every stack stood when built. Not better than that yet: the leftover depends on the wrist turn, so `HELD_SHIFT_MM` and `JAW_ARM_MM` are not quite right as fixed numbers.
- New limit found: a stack three bricks high is as tall as the lifted layer, and carrying a brick past an existing two-brick stack knocked it over in both runs. The arm only lifts about 5 cm.

## From the simulator to the real arm, Sat Nov 14, 1:08 PM

The simulator swaps in three things and nothing else: the camera picture (rendered from above), the taught poses (worked out by inverse kinematics), and the arm (`SimArm`). `see.py`, `pick.py`, `skills/fetch.py` and `voice/route.py` are the same code on the real arm. So the real setup needs the same three things, real:

1. A camera fixed above the table, looking straight down, seeing the whole taught grid, with the arm out of its view at `home`. About 50 cm up. It must not move after step 3. It plugs into the machine that runs `voice/route.py` (Windows on the arm laptop; WSL has no camera).
2. A taught grid: `python arm.py teach table 4` (or 5), jaw tips 3 to 6 mm off the table, jaws closing left-right the same way round at every point, plus `python arm.py pose handover`.
3. `python pick.py --corners`: click the grid's four corners in the camera picture.

Then these numbers, each measured once on the real arm (all are environment variables; unset means the feature is off or at its default):

| Setting | What to measure |
|---|---|
| `GRIP_OPEN`, `GRIP_CLOSED` | gripper reading fully open, and squeezing a 2x2 brick |
| `ROLL_SIGN` | turn the wrist for a turned brick; if it turns the wrong way, flip to 1 |
| `ROLL_MIN`, `ROLL_MAX` | the wrist roll joint's range in degrees |
| `GRID_WIDTH_MM`, `GRID_DEPTH_MM` | the taught grid's size with a ruler |
| `GRID_ASPECT` | width divided by depth |
| `JAW_ARM_MM` | turn the wrist a quarter turn; how far the point between the jaws moves, divided by 1.4 |
| `HELD_SHIFT_MM` | grip a brick, set it down with no turn, how far it lands from the aim (across,along) |
| `HELD_DROP_MM` | how much lower a gripped brick hangs than where it was gripped |
| `LAYER_GAP_MM` | height difference between the taught lifted layer and table layer |
| `CAMERA_HEIGHT_MM` | camera lens to table |
| `ROBOT_UV` | where the arm's base is in grid units, e.g. `0.5,1.6` |

What will not carry over: real Duplo studs have to be pressed together and lined up to a millimetre or two, and the simulator has no studs; the real arm repeats to a few millimetres at best; shadows and glare on the grey table can break the outline step (it falls back to the detector's box). Expect pick-up and handover first, putting beside second, resting one brick on another third, pressed-on stacks and the car body last or not at all.

Can be done before the arm is free: mount the camera, photograph the real table from it, run `python see.py --image that.jpg "..."` and `python pick.py --image` on it, and try a spoken request on the Windows side.
