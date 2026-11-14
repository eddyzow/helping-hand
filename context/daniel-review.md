# SO101 coordination and review

Reviewed implementation: `9d5081e` on `daniel/arm-core`, 2026-11-14.
Live ownership and responses: [notes/daniel.md](../notes/daniel.md).
Team protocol: [AGENTS.md](../AGENTS.md). Team contracts: [newcontext.md](../newcontext.md).

## Architecture

1. Root `arm.py` owns LeRobot connections, pose teaching, and recorded playback.
2. `grid.py` interpolates taught joint grids.
3. `pick.py` combines object localization and taught pickup positions.
4. `draw.py` produces strokes and uses a taught paper grid.
5. `core/arm.py` wraps the follower and exposes the same interface through MockArm.
6. `core/dispatcher.py` owns one arm and one active skill worker.
7. Skills receive the arm and a stop event; current skills are wave and tap.
8. Windows `keypad/listen.py` sends F13/F14/F15 commands over localhost TCP.
9. `voice/route.py` selects registered skills with keywords or Gemini.
10. `tests/test_core.py` checks the mock control path; it is not hardware evidence.

## Findings for Daniel's Claude

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
- No taught poses were present. Teach a supported resting `home`, then safe `wave_up` and `tap_up` poses with Daniel present.
- Inspect installed LeRobot before configuration: this installation is 0.7.0, defaults body joints to degrees, and uses 0–100 for the gripper. Do not assume another laptop has the same defaults.
- A single localhost port prevents a second dispatcher on the same port, but direct `arm.py`, `pick.py`, and `draw.py` commands can still compete for the device. Use one hardware owner and stop all other clients first.
- Voice stop currently goes through Gemini when configured. Keep a tested local stop key and physical power cutoff; voice routing is not an emergency stop.

## Fastest completion sequence

| Work | Owner / boundary | Completion evidence |
|---|---|---|
| Stop/shutdown and input fixes | Daniel's Claude; existing core/skills/tests | Mock/fake regressions pass; code reviewed |
| Coordination and review | Daniel's Codex; this folder and Daniel's note | Notes on main; remote commit verified |
| Hardware identification and poses | Daniel physically present, one agent slot | Port identity and taught poses recorded |
| Keypad wave / single tap | Daniel + Person 3 after claiming lane | Real F13/F14/F15 actions and stop observed |
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
