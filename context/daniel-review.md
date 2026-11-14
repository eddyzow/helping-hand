# SO101 coordination and review

Reviewed implementation: `9d5081e` on `daniel/arm-core`, 2026-11-14.
Follow-up: `e03beaa` replaces the original F13/F14/F15 listener with Sayo-specific raw input and key learning. The architecture and findings below describe the initial reviewed commit unless noted. Core files are unchanged by that keypad commit; the two reproduced core blockers remain applicable.
Live ownership and responses: [notes/daniel.md](../notes/daniel.md).
Team protocol: [AGENTS.md](../AGENTS.md). Team contracts: [newcontext.md](../newcontext.md).

Current review status: see [Daniel's current notes](../notes/daniel.md). The dated findings below preserve their original evidence; later fix sections supersede earlier open findings. All Codex execution used mock/fake objects; no physical validation is claimed.

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

### Fetch 46186b4: destination modifier narrows the wrong object
Four basic pure narrow cases passed (closest/right/farthest/no modifier). Exact new function given two red candidates and "put the red brick next to the right blue brick" chooses the right red candidate because it searches the entire sentence for right. That modifier identifies the blue destination, not the red source. Retain source ambiguity unless the positional modifier unambiguously applies to it; do not silently choose a source from destination language. Test this placement sentence as a regression. Only extracted pure code ran.
### Fetch a11b515: placement integration findings
Read all six changed files and searched every locate/find_all/choose caller. The inspected branch fetch suite was loaded in memory with current integrated core and temporary poses; it printed `fetch ok`, including placement and invalid destination checks. No real pose file, API, camera or simulation was used.
Exact voice.locate with fake frame/pick results for one source and one destination adds `beside` to params. Actual main dispatcher with the candidate fetch schema rejects the command: fetch has no option ['beside']; allowed options are object/to_u/to_v/u/v. Keep display metadata out of command params, or otherwise reconcile the explicit skill contract and test the full voice-to-dispatcher path. Do not weaken unknown-option validation.
A second fake with one source and two matching destinations returns only object/u/v. Current voice main sends that ordinary handover command, silently losing the requested placement; sim.request has the same len(near)==1-only condition. Refuse/clarify an ambiguous destination before dispatch instead of changing the requested action. Existing grip/dwell configuration and teach-size blockers remain unchanged. Owner priority requested: close these integration blockers before more features.
1055870 notification caller scan confirms only key down/key up use notify; these map to Event.set/clear and are idempotent state notifications. Run/home/stop use send. Keep bounded reconnect checks scoped to those state updates; do not auto-retry ambiguous motion requests.
### New arm delta 1055870 held: direct-write limit and notify EOF
Read both changed files and the installed WSL LeRobot send_action/sync_write implementation without constructing a robot. Prior send_action reads Present_Position and caps goals using max_relative_target; Feetech sync_write defaults to normalized calibrated units but has no equivalent measured-step cap. Exact candidate Arm methods with a fake bus, fake config limit15, zero tap pose and accepted lift40 send wrist0 then wrist-40 directly. This disproves the comment that every accepted tap is necessarily a small already-checked move. Preserve the measured-position safety boundary in the optimized path, or reject/fall back where it cannot be established; include a fake oversized/misaligned tap regression. No physical action occurred.
Exact new notify function with a fake existing socket whose sendall succeeds and recv returns b"" returns normally and retains that socket. EOF means the peer closed; treat it as disconnect instead of discarding it like a normal reply, and test bounded reconnection. No actual socket was opened. The combined keypad regression will also need its fake notification dependency updated when this source is integrated; no native listener should be loaded in tests.
These findings apply only to the new unmerged delta. Published 6d8fba2 and its recorded passing checks remain separate.
### Published arm integration 6d8fba2
Merged all reviewed arm ancestry through 583bd86 into current main with no conflicts. This delivers calibration bounds/verification/cache, job-correlated client results with missing-result termination, tap-delay measurement including command time, enter-mode replay, macro data/recording, matching input releases across focus changes, and STOP before fallible recording saves. Added one standalone stdlib regression file, tests/test_keypad_safety.py, which extracts only the callback and supplies fake input/file/transport APIs; it never loads the native listener.
Combined candidate checks: WSL `python -B -m tests.test_core` printed `core ok` under a 120-second external timeout; Windows `python -B -m tests.test_keypad_safety`, `python -B -m skills.draw`, and `python -B -m skills.personality` printed their success sentinels. Whitespace checks passed. Normal push published 6d8fba2 after refreshing upstream. No real hardware, hook, browser replay, microphone/camera, API or MuJoCo run occurred.
Independent short-tap checks at 85e3c73 verified the added key-registration wait is bounded to 0.2 seconds and STOP during that wait issues no later release/home. It is a bounded best effort, not measured physical timing. New car mesh at 363d379 has 34,088 triangles, exact expected binary length, and finite values; sim.py and its mesh-generator source compile, but neither rendering nor simulation was run.
To verify: run the four module commands above in their stated environments. Interview questions: Why must release remember how press was injected? Why must STOP precede recording persistence? What does a mocked timing/calibration pass establish, and what remains to measure physically?
### Macro d601a25 and fetch simulation be3a517 review

The new macro CSV passes independent standard-library parsing: 128 events / 64 alternating down/up pairs, finite strictly increasing timestamps from 2727.573 to 85889.522 ms. This verifies data structure, not gameplay success. No replay or input injection ran. Fetch simulator deltas through be3a517 (live request loop, scene shapes and photo-informed remodels) were read; simulation was not executed. Existing fetch config/teaching-size and arm input/stop blockers remain. Requested owner priority is closing these blockers before more feature additions.

### Macro recording 4bdb75f: save failure suppresses stop
Read the complete new recording delta. Stop-key handling writes the CSV before calling send(stop). Exact extracted on_key with a completed fake recording and fake Path.write_text raising OSError("fake disk full") raised that error with zero dispatcher calls. This is an independently reproduced stop-path regression; no real file, socket, or input event was used. Send stop before fallible recording persistence, handle the save failure visibly without losing the recorded events, and leave one fake regression. The commit adds no tests. The previously reported focus-change input pairing is still unchanged and also affects which recording edges are retained.
### Tap-delay timing fix ae796f9 verified

Exact committed source now starts timing before each command. The same deterministic fake that advances 20 ms during press and 30 ms during release now reports press_ms=20/release_ms=30. A blocking-write regression is committed too. This closes the timing-underestimate finding; input press/release pairing and a combined candidate suite remain before integration.

### Isolated 4203bf2 suite passes; new input-release finding
Created a separate detached worktree at C:\Users\Khang\pw\helping-hand-qa pinned to 4203bf2. Reviewed all three changed files before execution. Complete WSL `python -B -m tests.test_core` printed `core ok` under the external 120-second limit; worktree remained clean. This includes enter-mode, calibration, tap-delay's existing asynchronous-key test, job result handling and mock CLI cue. No native input listener ran.
The prior replay timing failure was from owner HEAD 4474fd5 while send/tests were changing; the changed portion did not alter the failing replay assertion. Both test and replay use time.perf_counter, and the expected CSV schedule/tolerance is unchanged. The later isolated run passes that assertion. Four equal late timestamps are consistent with execution resuming after all deadlines and issuing overdue commands together, but scheduling load versus another cause was not measured; do not claim a proven root cause or loosen the tolerance.
New 4203bf2 keypad logic selects mouse versus Up arrow independently for down and up using the current foreground title. Exact extracted on_key callback with fake user32 methods reproduced both cases: game->editor sends mouse-down then key-up; editor->game sends key-down then mouse-up. Neither releases the pressed input. Preserve the chosen injection type for the held key through release and test both focus changes. No actual Windows hooks, input injection, sockets, or hardware were used.
### Follow-up fixes verified: drawing 8ea9509 and client e847c57
Drawing now calls `_checked` on interpolated taught joints before applying squeeze/clamp. Fresh Windows self-check printed `draw ok`. The independent synthetic all-NaN grip grid that previously issued 47 fake moves now returns a plan error and issues zero. This closes the dispatcher drawing finding; root draw.py retains its separate clamp and was not executed.
Client e847c57 tracks idle polls and exits visibly instead of waiting forever. Exact committed source with fake transport was tested against both an empty last result and an older job 2 while waiting for job 5: each returned exit 1 after eleven idle polls with the missing-result message. No socket/wall wait was used. The tap_delay timestamp issue and fresh combined committed-candidate verification still block arm integration.
### Arm 4474fd5: tap_delay excludes command execution time
Read the new skill, its tests, press/release/_jump/_write and replay scheduling. Independently executed the exact new skill with fake time/key/stop/arm: press advances time 20 ms and sets key down before returning; release advances 30 ms and clears it before returning. Three cycles return success with press_ms=0 and release_ms=0. `until` initializes its clock only after each command returns. Timestamp immediately before the command so the lead measures invocation-to-observation, as the replay requires; add a deterministic blocking-command regression. No actual timing or keyboard events were generated.
The expanded WSL suite was run with an external 120-second limit. It failed the existing replay timing assertion: observed four events at 1.09 seconds rather than 0.30/0.38/0.68/0.76, exceeding the 0.06-second tolerance. This does not establish the cause of lateness. Claude was editing core/send.py and tests/test_core.py during the run, and those files were dirty afterward; no exact committed-candidate pass is claimed. Draft missing-result code now fails after eleven idle polls, but it awaits committed review/checks.
Backup detector f0dd8c7: four pure fake-provider cases passed (primary success, primary failure to backup, malformed backup box rejection, and no-key failure propagation). Synthetic environment values and provider stubs only; no API call, real key read, or frame capture. sim.py compiled; no MuJoCo execution.
### Fetch f0dd8c7: new teach-size CLI can replace a grid with unusable data
Reviewed the complete delta from 752882b, including simulation, backup detection, teaching, pick defaults, requirements and README. Existing fetch grip/dwell config validation remains absent. Exact `teach` function extracted from f0dd8c7 was executed only with fake follower/limp/input/read functions and temporary grids: n=0 and -1 each called connect/limp/disconnect and replaced the prior grid with empty layers; n=1 saved one point per layer, insufficient for bilinear interpolation. Require integer n>=2 inside teach before follower or filesystem changes, with a fake regression proving no connect/limp and unchanged prior file. README's environment paragraph still says GRIP_OPEN defaults to 60; both code paths now default to 100.
New simulation was read, not executed. Its reported grasp outcomes, grid errors, and detector timings are Eddy's observations, not independently measured here. No provider calls or physical setup were used.
### Drawing 66e5de9: taught NaN gripper survives clamp, 02:35 ET
The Windows drawing self-check completed with exit 0 after the new finite 0..30 PEN_SQUEEZE guard. Independently ran actual `skills.draw.run` with valid squeeze 8, a temporary synthetic 3x3 paper grid whose gripper values were NaN, a fake home loader, and a fake movement recorder. Writing I returned `ok: True` and issued 47 fake targets, all with gripper 0. `max(0.0, NaN)` returns 0 before `_checked` sees the value. Validate the interpolated taught joints before squeezing/clamping and leave a no-motion regression. The same clamp exists at root `draw.py:127`; that standalone path was inspected but not executed. No real pose file, arm, input hook, or API was used.
Arm branch delta `b15d0e6` changes calibration CLEAR from 0.5 to 2.5 and adjusts its regression expectation from lift 1.15 to 3.15. The missing-result client loop is unchanged, so integration remains held; increased physical clearance is not independently measured here.
### Software integration c6a3418, 01:17 ET

Merged Ben's `79ac6aa`, including the reviewed `bbdfac5` core ancestry, to unblock team development against a common mock/dispatcher. Full unmerged ancestry and resulting file set were reviewed; `a908855` is not an ancestor and its blocked press changes are absent. Combined WSL `tests.test_core` and `skills.personality` passed under external timeouts (`core ok`, `personality ok`); staged whitespace check passed. A pre-push rebase preserved Ben's newer demo text and changed no tested source. Physical startup support remains outstanding; software integration is not hardware approval.

### Drawing fix c9b01c7 verified

The complete plan now checks finite positive durations up to 30 seconds before returning; zero-speed division is caught during planning. Fresh Windows `python -m skills.draw` printed `draw ok`. An independent synthetic-stroke/temp-grid run through actual MockArm methods rejected six speeds (-0.15, NaN, 0.0001, 0, +inf, -inf) with zero `_write` calls. This closes the finding below. Ben also updated the demo to carry Eddy's corrected photo evidence. WSL dependency availability is still a separate environment gap; physical drawing remains untested.

### Historical draw skill 56a5f0f: duration preflight (fixed by c9b01c7)

Reviewed the complete new skill and the called root text/resample path. The inspected Windows fake self-check printed `draw ok`; WSL could not complete it because `HersheyFonts` is absent. Root camera, API, standalone drawing, and hardware paths were not invoked.

**Must fix:** the plan checks every joint target but does not validate every duration before movement. With an injected two-point stroke, a synthetic table grid in a temporary directory, and actual `MockArm.move_joints` with instant fake waits, PEN_SPEED=-0.15, NaN, and 0.0001 each caused 102 `_write` calls before duration rejection at the first drawing segment. The first home, lifted approach, and pen-lowering moves had already happened in mock. Resulting rejected durations were -0.13333333333333333, NaN, and 200 seconds. Ben should check the entire plan against the arm's finite 0-to-30-second duration contract before any motion, with a no-motion regression for these settings. The whole-plan guarantee must cover times as well as joint values.

Validate PEN_SPEED as finite and supported as well. Until this is fixed, drawing remains mock-only in demo claims; it is not ready for physical operation. WSL's missing dependency is an environment gap, while the Windows `draw ok` result is a completed check.

### Arm candidate ddb5101: combined mock checks passed, missing result still held

The inspected expanded WSL suite printed `core ok` under an external 120-second timeout, including calibration regressions, same-invocation waiting, and the mock CLI cue/status path. Source HEAD stayed `ddb5101`; only `poses/tap_key.json` became locally modified during the run, so this does not validate a particular committed or physical pose. No hardware connection occurred.

Because the suite explicitly tests elbow calibration, a separate fake check exercised the default wrist: press/release changed the wrist target as expected, mutating a returned pose did not alter the cache, and successful calibration refreshed the cached tap pose before the departure helper. That check used a temporary pose directory and a simulated key state. Current `core.send` still lacks the idle/missing-result exit documented below, so the candidate remains held.

Additional isolated voice check for `73710c0`: the extracted router main with fake list/locate/send/speak boundaries sends no run command for zero or multiple matches, asks which one for multiple matches, and dispatches for one match. No provider, microphone, camera, speech process, or socket ran.

### Fetch 752882b: target preflight fixed, config range/dwell unchecked

Loaded the exact candidate skill/test source in memory against the integration worktree's mock core. The inspected suite printed `fetch ok`, including its malformed-grid regression. A separate fake check confirms NaN grip is rejected without home or movement, closing the original target-finiteness gap.

Remaining configuration boundary: with a valid synthetic grid and fake arm/wait, GRIP_OPEN=101, GRIP_CLOSED=-1, HOLD_SECONDS=-1, and HOLD_SECONDS=NaN each enter home and return success. These constants are populated from environment settings. The gripper's documented domain is 0..100; a negative/NaN dwell must not silently remove the handover wait. Check finite grip values in range and finite nonnegative hold time before any movement, leaving a no-motion regression. No real wait, API, camera, or arm action occurred. The fetch branch remains unmerged until this is addressed.

### Vision and shared startup 27dc2d9 verified

Ran the embedded pure vision assertions by extracting the main guard's assertions and excluding its live `main()` call. They passed. Independent mocked-provider calls through actual `choose`/`detect` reject boolean IDs, reversed boxes, nonnumeric coordinates and infinity; a valid integer match is preserved. No API/key/camera access occurred.

The actual extracted follower body with stub LeRobot classes also passed: unset, empty, `0`, and `false` prompt before construction/connect; only exact `1` bypasses. EOF and Ctrl+C connect nothing. This closes both the vision-schema and shared startup-bypass findings below. Physical operation remains untested, and the standalone controller remains a separate path.

### Shared startup 2b0312c: default fixed, bypass value too broad (fixed by 27dc2d9)

Extracted the actual shared `follower` body and supplied stub LeRobot classes plus fake input/environment. With the flag unset, the order is prompt, config, constructor, connect; EOF and KeyboardInterrupt stop at prompt with no construction/connection. Caller scan includes root teach/pose/check/record/replay, root pick/draw, and the core wrapper. This closes the original default-order finding.

The newly introduced `if not os.environ.get("ARM_NO_PROMPT")` bypasses for every nonempty value. Independent fake cases show `0` and `false` connect without acknowledgement just like documented `1`. Require exact `1` for the opt-out, and leave unset/0/false/1 fake regressions. This review does not cover Jonathan's separate standalone motor-bus startup, nor establish physical readiness. No actual LeRobot class, serial connection, or torque action ran.

### Main vision 029a874: model-response validation

Reviewed the two-stage finder, changed `pick.locate` return contract and callers, and Eddy's `73710c0` voice update. Voice now returns without dispatching fetch when multiple candidates match. The original fetch target-preflight code is unchanged, so the fetch candidate remains held.

Independent checks used a synthetic 100x100 frame, an empty fake provider environment, and replaced `_gemini`; no request, key access, camera, or hardware call occurred. Reproduced: `{"matches":[true]}` selects zero-based box 0 because Python treats bool as int; `[900,900,100,100]` produces a reversed pixel box (90,90)-(10,10); a string coordinate raises TypeError rather than dropping the malformed entry as documented. Validate the reply container and match IDs as non-bool integers, and each box as four finite numeric non-bool values with ordered bounds within the stated 0-to-1000 range before emitting targets. Leave a small malformed-response regression. This is already-main vision code, separate from held fetch/calibration candidates.

### Browser tooling integration b4ecf89

Merged Jonathan's isolated `0386284`: browser-local recorder/replay, a separate soundtrack-aligned CSV, Playwright requirement, and documentation. Its prior ancestry was already on main. This supports the browser demo without altering the held physical arm-core candidate. The requirements conflict retained both upstream Anthropic and branch Playwright entries. A rebase preserved Ben's concurrent demo update; only documentation changed after the combined check.

Verification: both new scripts compiled; the CSV parsed as 146 events / 73 presses with timing compensation accepted. The extracted replay function passed five fake page/clock checks: normal completion of the event stream, key release on crash, retry restarting the stream, timeout without a cue, and release when timing out while a key is held. Combined WSL `tests.test_core` printed `core ok` under a 60-second external timeout. Whitespace checks passed. No live browser/recorder, native keyboard, MuJoCo, model API, or hardware run occurred; dependency installation was not repeated. A zero replay exit asks the operator to inspect the end screenshot; it is not an automated Level Complete assertion. Jonathan's reported level clear and simulation error remain attributed to him.

Interview questions: Why does this recording use the soundtrack epoch rather than the desktop restart key? How do crash and timeout paths release a held key? What does a passing fake replay prove, and what still requires the live browser or hardware?

### Waiting-client draft 555ce756: replacement fixed, missing result loops

The job-number change independently rejects an overwritten result even when both completed skills have the same name. Actual dispatcher/client logic with fake transport returned exit 1 for the first failed invocation after a later same-name success.

Residual on `core/send.py` SHA-256 `555ce756fbbd9b2ff8a3d3cced742a44e07e5be628bf320ae5f9cce5ff661d8a`: a fake accepted reply with job=5 followed by `status={"ok":true,"busy":false,"last":{}}` causes continued polling. The bounded fake stopped after the second poll; the real loop has no exit for this state. An idle dispatcher with no expected result, such as after restart, should fail visibly rather than wait indefinitely. Add that case alongside the replacement regression. No real socket/service was involved.

### Candidate 485ab71: waiting client reports another job's result

The new `core.send` accepts a start reply, polls global `status.busy`, then returns the global last result without correlating it to the accepted invocation. A deterministic fake-transport check used actual `dispatcher.handle` and `send.main`: first job returns failure, then another client starts/completes a second successful job before the first status poll. The waiting client prints the second job's result and exits 0. No socket or real dispatcher was contacted.

Correlate the accepted invocation to its result, including same-skill consecutive runs. If that result is no longer available, fail clearly instead of returning another invocation's success; no result-history feature is needed to avoid false success. Leave this interleaving as a small regression. The candidate remains unmerged.

### Calibration latest draft 94439328: residual cases verified fixed

Snapshot `9443932844b5dc020b14cd44d46b84ccc5accafecdaf3165aff054c5991b023c` passed independent fake checks: final saved/test endpoint stays at 8 for contact at max_travel=8, the approach-end stop emits zero creep writes, and a sticky key rejects after one verification press while preserving both previous valid calibration JSON files and the previous runtime settings. All files were confined to a temporary directory. Full candidate suite remains pending; the current sticky-key regression hardcodes lift=3 even though a prior calibration changes lift to about 1.15, so it should assert restoration to a captured pre-test value.

### Calibration 52392f2: partial fixes verified, sticky-key false success

The inspected expanded WSL mock suite passed `core ok` under an external 120-second timeout, with bytecode disabled. It exercises rejection of obsolete/unknown options, bounded creep, zero writes after an approach-end stop, and preservation on invalid measured lift. The separate-instance test setup is corrected in this commit.

**New fake-only reproduction, same calibration source `78b337af8b9142fe3ee6e9a7146456c06724388c7c60cd9871ba437725dfb4d1`:** the initial contact/release measurement succeeds, then the fake key stays held after the first verification press. Calibration returns `ok=True`, "3 of 3 test taps registered", although only one distinct verification down transition occurred. The loop counts `key_down.is_set()` without confirming release between taps. Observe a bounded release before each next press and after the last press; do not report success for sticky/missing-release feedback. Preserve the previous calibration if verification fails, and leave a regression. This check used only a fake arm and a temporary pose directory.

The final PAST-adjusted target finding below remains unchanged in `52392f2`, so this candidate is not merged.

### Calibration follow-up draft: final target still exceeds travel cap

Snapshot `78b337af8b9142fe3ee6e9a7146456c06724388c7c60cd9871ba437725dfb4d1` fixes the independently repeated creep-cap and approach-end stop cases: max_travel=8 commands no creep target above rough+8, and the stopped approach emits zero creep writes. Validation now precedes file saving, and the dispatcher draft rejects unknown parameter names.

**Residual reproduced with a temporary pose directory and fake key transitions:** when the key first registers at rough+8 and releases at +7.9, calibration returns success but saves and commands 8.15 in its test taps. `pressed_at + PAST` bypasses the travel cap applied to creep. Bound/reject the final calibrated target before saving or testing it; include exact-endpoint contact in the regression.

Test setup issue: `cal.run(StopAtKey(), {}, StopAtKey().halt)` uses separate arm and stop instances, so the arm sets an event that the creep does not observe and populates `creep_writes` before the next zero-write assertion. Remove that extra call or use one shared instance/event. No full-suite pass is claimed for this draft.

### Draft tap_calibrate: travel bound and stop output

Uncommitted source snapshot SHA-256 `5dc1d3520f00a61e0855b9b4889a00ddf3882b60cf385561aa5a42b75aa76e99` was compiled in memory with an injected fake arm and instant fake waits. No real constructor, connection, or physical calibration ran.

- With rough joint=0, lift=3, max_travel=8 and no key event, the largest commanded joint was 11.099999999999978. The loop measures distance from rough but passes `max_travel + lift`, and checks the current value before incrementing. Bound the next target in the intended direction, with the lowering endpoint no farther than rough + max_travel; account for the hover start separately.
- With stop set just as the fake approach completes, `creep` writes one new target before `stop.wait` notices the stop. Check stop before each direct `_write`, including the first creep step. Add a regression where stop arrives between approach and creep.
- Persistence failure independently reproduced with fake key transitions and a temporary POSES directory: a measured stroke over 40 was rejected by `set_tap`, but both previous calibration files had already been overwritten. Both `tap_key.json` and `tap_tune.json` are written before measured-result validation. Validate before persistence and leave a regression preserving previous valid calibration on rejection. No repository pose file was changed by the check.

The draft changes back from jaw-only tapping to configurable TAP_JOINT (elbow by default), adds shared key state, and forwards keypad jump down/up to the dispatcher. The legacy tuning-key finding below remains in the current draft. Physical key delivery, travel direction, contact force, latency, and collision clearance are not validated by these fake checks.

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
