# SO101 coordination and review

Reviewed implementation: `9d5081e` on `daniel/arm-core`, 2026-11-14.
Follow-up: `e03beaa` replaces the original F13/F14/F15 listener with Sayo-specific raw input and key learning. The architecture and findings below describe the initial reviewed commit unless noted. Core files are unchanged by that keypad commit; the two reproduced core blockers remain applicable.
Live ownership and responses: [notes/daniel.md](../notes/daniel.md).
Team protocol: [AGENTS.md](../AGENTS.md). Team contracts: [newcontext.md](../newcontext.md).

Latest review, 2026-11-14 01:05 ET: Geometry Dash integration `2393df7` (now in published `f1553cf`) introduces reproduced CLI cue, stop-key filtering, and negative-schedule issues below. The earlier shutdown cleanup fix `bbdfac5` remains verified; the pre-connection support warning remains open. All Codex execution used mock/fake objects and bytecode writes were disabled. No real Arm constructor, serial access, input listener, or hardware test ran.

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

### Software integration c6a3418, 01:17 ET

Merged Ben's `79ac6aa`, including the reviewed `bbdfac5` core ancestry, to unblock team development against a common mock/dispatcher. Full unmerged ancestry and resulting file set were reviewed; `a908855` is not an ancestor and its blocked press changes are absent. Combined WSL `tests.test_core` and `skills.personality` passed under external timeouts (`core ok`, `personality ok`); staged whitespace check passed. A pre-push rebase preserved Ben's newer demo text and changed no tested source. Physical startup support remains outstanding; software integration is not hardware approval.

### Candidate ad02ccf / 00fe57f: legacy tuning ignored

The new jaw-tap flow changes `set_tap` and skill parameters from elbow degrees (`lift_deg`, `press_deg`) to gripper units (`lift`, `press`), adds approach/retreat helpers, and changes both tap/replay callers. The ignore-file cleanup is part of this same unmerged ancestry; it is not the only delta.

**Must fix before merge:** `gd_tap.run` only reads the new names, so previously valid inputs are silently ignored. With the candidate's actual MockArm and skill, a fake `to_key` logger recorded `(8.0, 0.0)` for both `{"press_deg": -2}` and `{"lift_deg": 0}`. The former operator request for a lighter press now starts motion with the default full taught press. Reject obsolete/unknown tuning keys before any movement and add a no-motion regression. Do not alias values across the changed units. No real connection or motion ran in this reproduction.

The inspected candidate WSL `tests.test_core` suite passed (`core ok`) under the external 60-second timeout, including the mock CLI cue path. It lacks the legacy-input case above. Caller trace: the dispatcher checks only that params is a dictionary and forwards it; voice forwards the selected JSON params; the new skill advertises only `lift` and `press`. Neither upstream path rejects the obsolete keys. README still gives the generic fingertip pose instruction; the new jaw orientation must be taught and verified physically rather than inferred from the old pose file.

### Software integration 183db5e: tap and replay, 01:24 ET

Merged `e8b3da1` and its reviewed unmerged ancestry, including Jonathan's replay assets and the CLI cue/per-device key/negative-time fixes. This makes the dispatcher replay available on main and closes the press-default merge blocker. Defaults now use `set_tap`; `_jump` checks the adjusted six-joint vector before output. `tap_key` replaces `tap_up`: a default press returns to the taught key pose, and release raises the elbow by 3 degrees. No physical force or clearance follows from those commanded offsets.

Combined WSL checks passed under external timeouts with bytecode disabled: `python -B -m tests.test_core` printed `core ok` (including the mock CLI/localhost cue exchange), and `python -B -m skills.personality` printed `personality ok`. A separate fresh-import check exercised actual environment values: PRESS_DEG=nan/inf/50 and LIFT_DEG=nan/0 were rejected by both MockArm and Arm before a stubbed follower connection. A directly corrupted NaN press generated no writes. No real constructor connection, serial, keyboard hook, game, camera, or hardware test ran. Staged whitespace check passed; pre-push rebase changed no source.

Remaining: Eddy's `f652789` fetch branch still needs all planned targets validated before home. The installed connect torque transition still precedes the shared support prompt. Software integration does not approve physical operation.

Interview questions: Why must defaults use the same validation as runtime settings? Why does `python -m` require cue state in a shared module? Why does a taught key pose still need physical force and clearance checks?

### Historical candidate a908855: default press validation (fixed by e8b3da1)

The user authorized Codex to integrate passing branches in the separate worktree, leaving unsafe candidates unmerged. This candidate moves cue state to `core`, tracks held keys per device, and rejects negative compensated schedules. The exact fake callback check now confirms laptop Z does not suppress Sayo Z.

The inspected complete WSL core suite, including its real `python -m core.dispatcher --mock` subprocess/localhost cue test, passed (`core ok`) under an external 60-second timeout. The child stayed in WSL; bytecode writes were disabled. The negative-time regression also passed. This resolves the three earlier replay findings but does not cover the new default-validation case below.

New must-fix before merge: `MockArm.__init__` assigns `self.press_deg = PRESS_DEG`, bypassing `set_press`'s finite/range validation, and `_jump` adds that value then calls `_write` directly. `PRESS_DEG` comes from a float-parsed environment variable. Reproduced by setting the module default to NaN before constructing MockArm: `press()` returns True and joint 3 becomes NaN. Validate defaults through the existing setter and check the final adjusted vector before output; leave a default/environment regression. This reopens the shared-output validation boundary for the new press path, not the already-fixed `move_joints` path.

Related branch check, 01:09 ET: Ben's `79ac6aa` personality self-check printed `personality ok`; Eddy's `f652789` fetch test printed `fetch ok`. Both were inspected first and loaded in memory against the local mock core. A separate fetch check found that NaN table-grid targets are not validated before `arm.home()`: the fake home log was `['home']`, then `move_joints` raised ValueError. Eddy should validate the complete planned joint targets before the first home and add this no-motion failure case. No voice main, speech subprocess, camera, or hardware path ran.

### Geometry Dash integration: 2393df7 / f1553cf, 01:05 ET

What this change does: adds dispatcher cue/ready events, a Geometry Dash skill using Jonathan's CSV and held presses, taught press/release poses, and automatic game-restart logic in the Windows listener. Reproduction file hashes remained unchanged across the checks: skill `3f15242`, listener `4d61012`, dispatcher `ee45427`. These began as a working-tree review and are now committed.

The inspected expanded Windows `tests.test_core` printed `core ok`, including its imported-module replay test. That test does not cover the CLI module identity or keyboard callback cases reproduced separately below.

**Must fix:**

1. **CLI and skill use different cue events.** `python -m core.dispatcher` executes dispatcher state as `__main__`; the new skill imports `cue` and `waiting` from `core.dispatcher`, creating another module/state instance. Reproduced without sockets by executing the CLI module under a separate runpy name, starting the skill on a fake arm, then calling its CLI handlers: the skill's waiting flag is set but CLI `ready` is False; CLI `cue` sets only its own event. Use one shared event instance in both launch modes and leave a CLI-entry regression. Otherwise the advertised launch never receives the skill's ready/start handshake, although import-based tests can pass.
2. **A laptop key can suppress the Sayo stop key.** The new `wndproc` adds every keyboard's VKey to one `held` set before checking device identity. Reproduced with the exact callback AST and fake Windows APIs: laptop Z-down followed by Sayo Z-down produces no `on_key` call; Sayo Z-down alone does. Key repeat tracking must include device identity or filter Sayo events before its held-key bookkeeping. Otherwise the physical stop press is ignored while the same key is held on another keyboard. No actual keyboard API or listener ran in this check.
3. **Timing compensation can create commands before the cue.** With `demo_taps.csv`, `first_taps=1`, and both leads at 1000 ms, the first commands are negative but the skill reaches `home()` instead of rejecting the schedule. A fake home recorded that attempt. Unlike the standalone CLI, the new skill does not reject `commands[0].at < 0`; past-due events will collapse into immediate press/release commands. Reject impossible compensated schedules before motion and add the boundary case.

Verdict: fix these integration cases before relying on the new replay/stop flow. Automatic restart, game focus, raw-input behavior, and physical timing have not been tested by Codex. The per-device suppression finding is a deterministic callback check, not a physical keypad test.

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
