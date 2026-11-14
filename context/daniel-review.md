# SO101 coordination and review

Reviewed implementation: `9d5081e` on `daniel/arm-core`, 2026-11-14.
Follow-up: `e03beaa` replaces the original F13/F14/F15 listener with Sayo-specific raw input and key learning. The architecture and findings below describe the initial reviewed commit unless noted. Core files are unchanged by that keypad commit; the two reproduced core blockers remain applicable.
Live ownership and responses: [notes/daniel.md](../notes/daniel.md).
Team protocol: [AGENTS.md](../AGENTS.md). Team contracts: [newcontext.md](../newcontext.md).

Latest verification, 2026-11-14 01:01 ET: published fix `bbdfac5` resolves the cancelled-shutdown cleanup path in fake checks using the installed LeRobot methods. The Windows mock suite printed `core ok`. Earlier shutdown and invalid-input reproductions are now resolved in this checked code; the pre-connection support warning remains open. All Codex execution used mock/fake objects and bytecode writes were disabled. No real Arm constructor, serial access, input listener, or hardware test ran.

## Architecture

1. Root `arm.py` owns LeRobot connections, pose teaching, and recorded playback.
2. `grid.py` interpolates taught joint grids.
3. `pick.py` combines object localization and taught pickup positions.
4. `draw.py` produces strokes and uses a taught paper grid.
5. `core/arm.py` wraps the follower and exposes the same interface through MockArm.
6. `core/dispatcher.py` owns one arm and one active skill worker.
7. Skills receive the arm and a stop event; current skills are wave and tap.
8. Windows `keypad/listen.py` learns Sayo keys; wave/stop use localhost TCP, jump injects Up arrow.
9. `voice/route.py` selects registered skills with keywords or Gemini.
10. `tests/test_core.py` checks the mock control path; it is not hardware evidence.

## Findings for Daniel's Claude

### Cleanup fix verified: bbdfac5, 01:01 ET

What this change does: `Arm.close(release=False)` sets LeRobot's disconnect policy before closing the port; cancelled shutdown uses this path. The normal operator-confirmed path retains torque release. All close callers were checked and tests were inspected before execution.

The Windows core suite passed. Independent fake checks using the installed `Robot.__del__` and `SOFollower.disconnect` method bodies passed for both EOF and KeyboardInterrupt: direct close and later cleanup both sent `False` to the fake bus, and a home request during confirmation was rejected as `shutting down`. The installed bus implementation at `motors/motors_bus.py:440` checks this flag before torque disable and always closes its port. No real bus or robot constructor ran.

The lifecycle finding under `5e80dc5` below is resolved by this commit. Its text is retained as reproduction history. The shared pre-connection support-warning finding remains open; physical holding, cutoff, clearance, and timing still need Daniel's validation.

Wave follow-up `40419ff`: published branch repairs merge markers and changes wave to four cycles at +/-45 degrees, 0.35 seconds per sweep. Core suite passed again; a full fake sequence and interruption check passed. Core shutdown code is unchanged, so the lifecycle finding below remains open. The larger/faster commanded motion has no new physical verification from Codex.

### Published fix follow-up: 5e80dc5, 00:51 ET

What this change does: publishes the shared mock/dispatcher API, the three pose files, input validation, explicit home, shutdown command rejection, and regression tests. `core ok` was reproduced on Windows after inspecting the new tests. The tests now use temporary synthetic poses, numeric tolerance, and assert that the spy actually moved before stop. EOF does not directly call close; a new command during shutdown is rejected. These resolve the earlier draft findings at the application-call level.

**Must fix: cancelled shutdown still releases torque through the installed destructor.** In this laptop's LeRobot 0.7.0, `robots/robot.py:88` defines `Robot.__del__`: if connected, call `disconnect()`. `SOFollower.disconnect()` passes `config.disable_torque_on_disconnect` to the bus; its default is True. Returning from `shutdown` on EOF leaves that default unchanged. When the robot object is released, cleanup can disable torque despite the message that motors stay on. Reproduced with `Arm.__new__`, the installed destructor/disconnect method bodies extracted into a fake robot, and a fake bus: shutdown on EOF produced no immediate call, then garbage collection produced `[('bus.disconnect', True)]`. No LeRobot robot constructor or real bus ran. Make cancelled shutdown explicitly close the connection with torque release disabled, and ensure subsequent cleanup preserves that choice; add a fake cleanup regression. Keep physical readiness blocked until this is resolved.

**Shared dependency finding for Eddy and Daniel:** `965bcea` correctly asks before the explicit `go_limp` torque disable, but `teach` and `pose` call `follower()` first. Installed `SOFollower.connect()` calls `configure()`, which enters `bus.torque_disabled()`; that context disables then re-enables torque before the new prompt. Move the support warning/acknowledgement before connection, accounting for every caller of shared `follower()`. This is installed-source verification, not a physical observation. Merely constructing the wrapper still requires a supported arm and operator approval.

**965bcea fake checks passed:** prompt precedes the explicit `go_limp` call; EOF does not call that explicit torque disable; `check` visits eight synthetic midpoints in up/down order; pen grip 20 becomes 12 in all fake drawing commands. Actual clearance, grip force, and travel remain unmeasured.

**Integration answers:** the dispatcher line format is `run <skill> <JSON object>\n`, with one JSON response line. `run fetch {"u":0.5,"v":0.5}` is an illustrative future skill payload, not a registered fetch schema today. `_Handler` passes the line to `handle`; dispatch forwards the dictionary to the skill. Installed `use_degrees=True` makes `MAX_STEP=15` a 15-degree measured-position-to-target cap for body joints and 15 points on the gripper's 0-100 scale. It is not a speed limit or a clearance guarantee.

Verdict: mock development is unblocked by the published branch; hardware still needs the cleanup and pre-connection support fixes plus Daniel's physical checks.

### Draft fix follow-up, 00:42 ET

What this change does: the uncommitted fix on rebased local HEAD `313d9cf` removes homing from `Arm.close`, adds an explicit home command, validates motion inputs, and asks for support before disconnect. This is a working-tree review, not a reviewed release commit. Observed blob hashes: arm `9f0e4e5`, dispatcher `52ea01b`, tap `511154e`, tests `f126e1e`; unchanged across the checks below.

**Confirmed improvement:** independent mock assertions now reject short/NaN/infinite/boolean joint vectors and malformed/decreasing-time trajectories without changing mock state. The old automatic-home-on-close path is removed.

**Must fix before hardware:**

1. `core/dispatcher.py:78-89`: shutdown catches EOF/KeyboardInterrupt at the support prompt and proceeds to disconnect. Reproduced using `Arm.__new__`, `MockArm.__init__`, and fake disconnect: a confirmation callback raising EOFError still logged `disconnect`. With stdin already closed, the prompt cannot receive confirmation. Do not treat missing/cancelled confirmation as permission to release torque; define an explicit supported-arm shutdown path with Daniel. Otherwise the arm can drop without the promised acknowledgement.
2. `core/dispatcher.py:48-66,78-89,118-130`: shutdown does not close command admission, while the TCP server continues running during the prompt. Reproduced without a socket: the confirmation callback calls the same `handle("home")` used by the server; it returns success, clears halt, and runs home before disconnect. The fake log is `[("home", False), "disconnect"]`. Mark shutdown under the dispatch lock before stopping/joining and reject new dispatches thereafter; close the server as part of shutdown. Otherwise keypad/voice/network commands can restart motion while the operator supports the arm.

**Test issue:** the inspected updated `tests.test_core` failed at line 35, before its new regression checks. Worker was finished; home differed only by `2.842170943040401e-14` from the local taught pose due to interpolation rounding. Use a small explicit tolerance for numeric equality and deterministic mock poses. The new Spy also inherits `load_pose`'s `type(self) is MockArm` check, so missing `wave_up` can terminate its worker before the intended stop scenario; assert the spy actually began moving. These are test-quality findings, not evidence of dangerous numerical drift.

Verdict: keep hardware blocked on the two shutdown paths. No source edits, serial, real Arm constructor, or hardware checks were performed by Codex.

The numbered findings below describe the original implementation; this follow-up records which parts the draft has addressed.

### 1. Shutdown can move after stop — resolve before physical tests

`core/dispatcher.py:100-105` calls stop, joins for two seconds, then closes the arm. `core/arm.py:114-120` clears the halt flag, homes, and disconnects in `finally`. Thus Ctrl+C/EOF is a motion command even after a stop. If the worker has not exited, clearing its stop event also allows competing control. If homing fails, disconnect still executes; the installed configuration defaults to disabling torque on disconnect.

Reproduced with `Arm.__new__(Arm)`, `MockArm.__init__`, and fake `home`/`disconnect`: stop followed by close produced `[('home', 'halt_set', False), 'disconnect']`. No real Arm constructor or motor call was used.

Required outcome: stopping/shutting down must not silently resume a skill or initiate recovery motion. Separate operator-approved homing from stopping, ensure the worker has ended before any recovery, and account for an unsupported arm before torque is disabled. Leave a fake-arm regression check for stop then shutdown and failed home. Preserve a clear distinction between software hold and the physical power cutoff.

### 2. Validate inputs before the first motion

`core/arm.py:49-58` zips the current and requested joints without length or finiteness checks. Reproduced: `MockArm().move_joints([1.0], 0)` leaves a one-element state; six NaNs are accepted. Real `_write` also zips, so the same missing validation reaches motor actions. `play()` writes directly as well: cover all callers at the shared boundary rather than adding checks to each skill.

`skills/gd_tap.py:13-17` homes and approaches the key before parsing `times` and `gap_s`. Dispatcher JSON validation checks parsing only, not that params is an object or that values are valid. Invalid input can therefore move the arm before reporting an error. `gap_s` is silently capped to 0.5 seconds, which also changes requested rhythm timing rather than waiting interruptibly.

Required outcome: six finite joint values; finite sensible durations; validated skill parameter types/ranges before any motion; valid trajectory shape/timing. Use small fake/mock checks showing rejected requests produce no movement. Physical travel and tap depth still need calibration; wrist degrees are not measured millimetres.

### 3. First motion also depends on setup, not just passing mocks

- Only `/dev/ttyACM1` was visible; identify it physically before assigning leader/follower roles. Calibration files existing on disk do not prove the attached adapter's identity.
- Latest file check: untracked `poses/home.json` exists; `wave_up.json` and `tap_up.json` are absent. The home file's presence does not validate its physical safety. Teach/verify these poses with Daniel present after resolving the core blockers.
- Inspect installed LeRobot before configuration: this installation is 0.7.0, defaults body joints to degrees, and uses 0–100 for the gripper. Do not assume another laptop has the same defaults.
- A single localhost port prevents a second dispatcher on the same port, but direct `arm.py`, `pick.py`, and `draw.py` commands can still compete for the device. Use one hardware owner and stop all other clients first.
- Voice stop currently goes through Gemini when configured. Keep a tested local stop key and physical power cutoff; voice routing is not an emergency stop.

## Fastest completion sequence

| Work | Owner / boundary | Completion evidence |
|---|---|---|
| Stop/shutdown and input fixes | Daniel's Claude; existing core/skills/tests | Mock/fake regressions pass; code reviewed |
| Coordination and review | Daniel's Codex; this folder and Daniel's note | Notes on main; remote commit verified |
| Hardware identification and poses | Daniel physically present, one agent slot | Port identity and taught poses recorded |
| Keypad wave / single tap | Daniel + Person 3 after claiming lane | Real learned wave/jump/stop keys observed; single tap commanded separately through dispatcher |
| Tap calibration and short game section | Person 3 after assignment | 20 actual key-event timings; raw observations retained |
| Fixed fetch | Eddy + Daniel, coordinate wrapper dependency | Successful/attempted counts; target 4/5 from team plan |
| One written word + demo script | Person 4 after assignment | Real legible output, stop tested, repeatable demo |

Reserve the real arm in explicit slots. Everyone else develops against the mock. Do not start sensing/training merely because the USB cable is plugged in. No feeding toward a person during these initial checks.

## Feedback loop

At each turn: fetch/pull the appropriate branch, read changed notes, acknowledge addressed requests in your own note, and claim files before edits. At each completed slice: record the commit, exact test command/result, remaining hardware gap, and release the hardware slot. Before pushing: refresh upstream and preserve concurrent work. Notes belong on main. A published request is not an acknowledged handoff; require a reply before assuming another agent has taken the lane.

## Verify and explain

In the feature checkout, run `C:\Users\Khang\so101\.venv\Scripts\python.exe -m tests.test_core` for the existing mock check. It printed `core ok` in this review. Run newly added regressions as specified by Claude's fix commit. Inspect `git diff --check` and the notes commit before publishing. No hardware benchmark was run.

Interview questions Daniel should be able to answer:
1. Why can clearing a stop event during shutdown restart motion, and how does the shutdown design prevent that?
2. Where should validation live so voice, keypad, and recorded playback all reject bad motion inputs?
3. What does a passing mock prove, and what must be measured on the physical arm/keypad?
