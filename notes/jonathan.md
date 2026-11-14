# Jonathan

Updated Sat Nov 14, 6:15 PM by Jonathan's agent (Claude).

## Working on now

- New skill, `skills/steady.py`, on branch `jonathan/tremor-assist`: a person steers the follower by moving the leader arm, and the shake of a trembling hand is filtered out before the follower moves. Jonathan's idea, for people with a hand tremor. Mock only so far. It needs a first run on the two real arms before the 8:50 PM freeze to be in the demo.
- Geometry Dash: `jonathan/geometry-dash-replay` is fully merged into `main`. The arm-side timing work is Daniel's.

## Done and how it was tested

- `skills/steady.py` has never run on the real leader or the real follower. What it does: reads the leader's six joints each tick, low-pass filters them (two one-pole stages, 1.5 Hz by default), holds the output still inside a 0.3 degree band, limits speed to 120 degrees a second, and sends the result with `arm.move_joints(target, 0)`. It starts from home, glides to wherever the leader is at 40 degrees a second, catches up at that same speed, follows for `seconds`, then goes home. Stop holds the arm and never moves it.
- `python -m skills.steady` prints `steady ok` on a fake arm, a fake leader and a fake clock. It checks: a 5 Hz, 3 degree shake comes out under 0.35 degrees while a slow 20 degree reach keeps over 95% of its size and trails by 0.1 to 0.3 s, at even and uneven time steps; a hand trembling in place leaves the output still; no step is ever larger than the speed limit; the gripper stays 0 to 100; 18 bad settings are refused before the leader is opened or anything moves; a leader that cannot be opened or reads badly at the start moves nothing; a leader that fails part-way, and a stop part-way, send nothing further and do not go home; the leader is disconnected on every path. Each of 13 deliberate faults put into the skill made that check fail.
- Through `python -m core.dispatcher --mock` in real time: listed with the other skills, a bad setting refused, a 6 second run finished at 30 ticks a second with its report, `run wave` during it got "busy", and stop ended an unfiltered run. `tests.test_core`, `tests.test_fetch`, `tests.test_keypad_safety`, `tests.test_arm_boundaries`, `tests.test_dispatcher_exit` and `skills.personality` still pass with the new file present.
- Not known: whether `get_action()` on the installed LeRobot returns the same joint names and units the follower takes (it relies on the same calls as `arm.py record`); the real loop rate with two serial buses; whether the follower can hold anything under teleoperation, given Eddy's 5:04 PM report on grip strength.
- The desktop recording has 74 presses and releases. The simulated O3C reproduced all 148 events within 1.4 ms after timing compensation.
- The browser recording has 73 presses and releases. The simulated O3C reproduced all 146 events within 0.9 ms. One replay reached Level Complete in RobTop's browser demo with a 12 ms offset from the soundtrack cue. The browser tooling cancels failed attempts and resets to the start on retry.
- The standalone Windows CLI was tested with a fake motor bus. The physical follower and desktop game replay still need an in-person test. The standalone CLI needs exclusive access to the follower's Windows COM port. The shared dispatcher has its own replay path on main.

## Needs from others

- Daniel: an arm slot of about 20 minutes for `steady`, with the leader on its 5 V supply and attached to WSL as well as the follower (`LEADER_PORT`, default `/dev/ttyACM0`). Hold the leader up in a clear pose, someone on the stop key, then `run steady {"seconds": 20}`. If that follows smoothly, `run steady {"seconds": 20, "filter": false}` with a deliberately shaky hand shows the difference. Please write down what happened, including whether it can pick up one light object. The trace of each run is saved to `outputs/steady_last.json`.
- Daniel's reviewer: two things to judge against the core contracts. The skill sends one `arm.move_joints(target, 0)` per tick as its streaming write, and it opens the leader itself through root `arm.leader()` (the dispatcher keeps the follower).
- Ben: if it passes on the arm, this is an assistive skill where the person does the aiming, so it does not depend on the camera or the taught grid. Please do not put it in the script or the Devpost text until someone reports a real run.
- Daniel: use the follower hardware slot to teach the released and pressed wrist positions, verify stop, and share the measured press and release delays from the tap test.

## Answers to questions other notes asked you

- Daniel: the recording and the follower-only test are available together on the feature branch. No hardware slot was used for the mock checks.
