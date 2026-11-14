# Jonathan

Updated Sat Nov 14, 6:50 PM by Jonathan's agent (Claude).

## Working on now

- Lane B of the Steady Hand pivot (`newcontext.md`): `skills/steady.py` on `jonathan/tremor-assist` is the dispatcher version. A person steers the follower with the leader and the shake of a trembling hand is filtered out before the follower moves. Mock and simulation only; never run on the real arms.
- Next for lane B: share the filter and the shake meter with `core/tremor.py` (today only on `daniel/arm-core`, so this waits for it to reach `main` or for a go-ahead to build on that branch), and bring over the two real-arm guards from Daniel's standalone `steady.py`: the follower's elbow limit and the cap on how hard the claw squeezes.
- Geometry Dash: `jonathan/geometry-dash-replay` is fully merged into `main`. The arm-side timing work is Daniel's.

## Done and how it was tested

- `skills/steady.py` has never run on the real leader or the real follower. What it does: reads the leader's six joints each tick, adds the per-joint offset from `poses/teleop_offset.json` (the same file Daniel's `steady.py --measure` writes; on the real arm the skill refuses to start without it), low-pass filters them (two one-pole stages, 1.5 Hz by default), holds the output still inside a 0.3 degree band, limits the speed asked for to 120 degrees a second, and sends the result with `arm.move_joints(target, 0)`. Before following it goes home and glides out to the leader, and afterwards it goes home again; each of those moves is asked for at 40 degrees a second or `max_dps`, whichever is lower. Stop holds the arm and never moves it.
- `python -m skills.steady` prints `steady ok` on a fake arm, a fake leader, a fake clock and a temporary poses folder. It checks: a 5 Hz, 3 degree shake comes out under 0.35 degrees while a slow 20 degree reach keeps over 95% of its size and trails by 0.1 to 0.3 s, at even and uneven time steps; a hand trembling in place leaves the output still; no step of any move, following or not, is larger than its speed allows, including with `max_dps` 10 and an arm that starts away from home; a move too long to make that gently is refused before anything moves; the gripper stays 0 to 100; the offset is added to every reading and six kinds of bad offset file are refused; 18 bad settings are refused before the leader is opened or anything moves; on a real arm, a missing offset file or a leader on the follower's port opens nothing and moves nothing; a leader that cannot be opened or reads badly at the start moves nothing; a leader that fails part-way, and a stop part-way, send nothing further and do not go home, and the failed run's own trace is saved; the leader is disconnected on every path. Each of 20 deliberate faults put into the skill made that check fail.
- Through `python -m core.dispatcher --mock` in real time: listed with the other skills, a bad setting refused, a 6 second run finished at 30 ticks a second with its report, `run wave` during it got "busy", and stop ended an unfiltered run. `tests.test_core`, `tests.test_fetch`, `tests.test_keypad_safety` and `tests.test_dispatcher_exit` still pass with the new file present.
- Simulation, re-run 6:45 PM after the fixes below: `python sim_steady.py --compare` (new file on the same branch) runs the unchanged skill on two SO-101 arms in MuJoCo. A scripted hand moves the leader through a pick-up of a 2x2 brick with a 5 Hz tremor added; the follower, its jaws and the brick are physics. Six pick-ups per row, each starting at a different moment of the tremor:

  | Tremor at the wrist | Hand tip shake | Filter off: placed, follower tip shake | Filter on: placed, follower tip shake |
  |---|---|---|---|
  | none | 0.4 mm | 6 of 6, 0.8 mm | 6 of 6, 0.7 mm |
  | 1.5 degrees | 4.6 mm | 6 of 6, 4.4 mm | 6 of 6, 0.7 mm |
  | 3 degrees | 9.2 mm | 1 of 6, 9.1 mm | 6 of 6, 0.9 mm |
  | 4.5 degrees | 13.8 mm | 0 of 6, 13.7 mm | 6 of 6, 1.1 mm |

  With the filter the follower trailed the hand by 0.23 s, against 0.03 s without. The same held at 8 Hz and with the trigger finger's tremor taken out. This is a simulation: the scripted hand does not wait for the follower as a person would, the model's servos are stronger and more exact than the real ones, and both simulated arms are the follower model. It says nothing about the real arm's grip.
- Not known: the real loop rate with two serial buses, and how long a blocked leader read delays a stop (the reviewer notes both); whether the saved offset is right for the arms as they are mounted now; anything about the real follower's motion. The skill does not yet know the follower's elbow limit or cap the claw's squeeze.
- The desktop recording has 74 presses and releases. The simulated O3C reproduced all 148 events within 1.4 ms after timing compensation.
- The browser recording has 73 presses and releases. The simulated O3C reproduced all 146 events within 0.9 ms. One replay reached Level Complete in RobTop's browser demo with a 12 ms offset from the soundtrack cue. The browser tooling cancels failed attempts and resets to the start on retry.
- The standalone Windows CLI was tested with a fake motor bus. The physical follower and desktop game replay still need an in-person test. The standalone CLI needs exclusive access to the follower's Windows COM port. The shared dispatcher has its own replay path on main.

## Needs from others

- Daniel: which way should lane B converge? `core/tremor.py` is only on `daniel/arm-core`. Either it reaches `main` and I build on that, or say so and this branch is rebuilt on top of `daniel/arm-core`. Until then the skill keeps its own filter (two one-pole stages at 1.5 Hz; yours is 2.0 Hz with a faster claw) and its own swing counter.
- Daniel: the skill reads `FOLLOWER_PORT` and `LEADER_PORT` through root `arm.py`, whose defaults are `/dev/ttyACM1` and `/dev/ttyACM0`. Your note says the arms now run natively on Windows as COM3 and COM4, so both variables must be set before the dispatcher starts. A first real run of the skill is yours to schedule once the reviewer lifts the hold; nothing here asks for one now.
- Ben: please keep `skills/steady.py` out of the script and the Devpost text as anything but "mock and simulation only" until a real run is reported. The simulation table above may be quoted as a simulation.
- Daniel: use the follower hardware slot to teach the released and pressed wrist positions, verify stop, and share the measured press and release delays from the tap test.

## Answers to questions other notes asked you

- Daniel's reviewer, three findings on `30c95fd` (QA `44be992`), all addressed on the branch:
  - Startup speed: the trip home, the glide out to the leader and the trip back are now each timed from the distance at `min(40, max_dps)` degrees a second, rounded up to whole ticks, with no 4 second cap. Your two cases (a 200 degree glide, and a 40 degree glide with `max_dps` 10) are in the self-check as a 150 degree glide at both speeds, from an arm that does not start at home. A move that would need more than the arm API's 30 seconds is refused before anything moves. The description no longer claims one speed limit for everything, and calls these commanded speeds.
  - Port ownership: `LEADER_PORT` equal to `FOLLOWER_PORT` (same text ignoring case and spaces, or the same resolved path) is refused before `arm.leader()` is called. Checked with a fake root `arm` module: the leader factory is never reached.
  - Trace: a leader failure part-way now saves that run's trace before returning.
  - Not changed: the follower's own measured-position step cap, and stop behaviour. A blocked leader read can still delay the next stop check, as you say; the mocks do not measure that.
- Daniel: the recording and the follower-only test are available together on the feature branch. No hardware slot was used for the mock checks.
