# Daniel — Claude implementation + Codex review

Updated 2026-11-14 00:38 ET. Snapshot, not a live hardware reservation.

## Working on now

- Daniel's Claude owns the existing arm-core implementation on `daniel/arm-core` (implementation commit `9d5081e`). Codex owns this note and `context/daniel-review.md`, independent mock checks, and integration review. Do not edit Claude's implementation concurrently.
- Latest local Claude commit: `11435b0` saves the key mapping and README update after `e03beaa` added key learning. Remote heads still contain only `main` (`62cfa00` at this check); the feature branch remains unpublished. Ben has now explicitly confirmed that this blocks teammates from using MockArm. Claude: integrate main's notes/protocol and publish your feature branch for mock development, clearly carrying the unresolved hardware blockers.
- Codex is monitoring local commits, main, and team notes continuously until stopped. Only this note and `context/daniel-review.md` are in its edit lane; the implementation checkout and learner remain untouched.
- Read [the review and next checks](../context/daniel-review.md) before connecting the follower. Two reproduced blockers: shutdown clears stop and starts homing; motion inputs accept malformed/non-finite joint vectors.
- No hardware slot is claimed by Codex. No serial connection, torque, calibration, or motion was initiated by this review.

## Done and how it was tested

- Claude implemented `core/arm.py`, `core/dispatcher.py`, `skills/wave.py`, `skills/gd_tap.py`, `keypad/listen.py`, `voice/route.py`, and `tests/test_core.py`. This is implementation, not hardware completion.
- Codex reran `C:\Users\Khang\so101\.venv\Scripts\python.exe -m tests.test_core` on Windows and `/home/trkang/miniforge3/envs/lerobot/bin/python -m tests.test_core` in WSL: both printed `core ok`. Mock only. Independently reproduced both blockers with MockArm/fake objects, without connecting a robot.
- Read the installed WSL LeRobot source and package metadata: version 0.7.0; body joints default to degrees in this local installation; gripper uses 0–100. Follower and leader calibration JSON files exist. Existence does not establish current calibration accuracy.
- `usbipd list`: one connected CH343 adapter at bus 1-2 (COM3), attached to WSL. WSL exposes `/dev/ttyACM1`. COM4 appears only in persisted devices, not connected. Arm identity has not been physically confirmed. USB HID `8089:0009` is present; Sayo model and actual key mapping remain unverified.
- Local untracked `poses/home.json` now exists (237 bytes); `wave_up.json` and `tap_up.json` are absent. This corrects the earlier no-poses snapshot. File presence is not evidence of safe pose teaching or physical validation.
- No real Sayo button, microphone, camera, waveform/tap timing, fetch, drawing, feeding, or physical stop test was performed by Codex. Claude's earlier key-injection/Gemini checks are reported evidence, not repeated here.
- `11435b0` contains `keypad/keys.json`: wave=88 (X), jump=67 (C), stop=90 (Z). This supersedes the earlier missing-mapping snapshot, but no real key events were observed by Codex. The original key still reaches the focused application alongside the synthetic Up arrow. The earlier learner process observation is historical; Codex has not interrupted it or launched another listener.
- At `11435b0`, reran the inspected `tests.test_core` module on Windows with bytecode writes disabled: `core ok`. Fresh fake/mock assertions again confirmed stop-then-close calls home with halt cleared, a one-element joint vector is accepted, and six NaNs are accepted. No real Arm constructor, network listener, serial, or input-hook code ran. These passing reproduction assertions confirm bugs, not fixes.

## Needs from others

- Daniel's Claude: read `context/daniel-review.md`; fix stop/shutdown and boundary validation in your feature branch, leaving small fake/mock regression checks. Acknowledge in this note by replacing this request with your commit and results. Keep the real arm idle until those checks pass and Daniel confirms the setup.
- Eddy: keep ownership of root `see.py`, `pick.py`, `draw.py`, `grid.py`, and `arm.py` for now; Daniel's API wraps `arm.py`. Coordinate changes to that wrapper dependency first. Reuse your grid/vision work; no duplicate YOLO/IK implementation is needed for the first demo.
- Eddy / all agents: do not independently replace `core/dispatcher.py`, `voice/route.py`, or `keypad/listen.py`; Daniel's Claude has already implemented the initial versions. This is a temporary reservation based on existing work, not a reassignment of the human roles.
- Person 3 (name still unassigned): after coordination, own physical Sayo mapping and the 20-tap latency/jitter measurement, then a short Geometry Dash sequence. Reserve a hardware slot before opening any serial port. Do not count injected keyboard events as real keypad evidence.
- Person 4 (name still unassigned): prepare the compliant pen mount, existing drawing previews, and demo script; avoid rebuilding Eddy's drawing pipeline. Integrate one fixed word after the wave/tap hardware checks.
- Daniel: identify/reconnect the missing arm adapter if both arms are needed; confirm which visible port is the follower, the actual Sayo model/key mapping, and the separate key the arm should press. Pose teaching and first motion require you present.
- Everyone: keep your own `notes/<person>.md` current. Pull/read notes at each turn and before pushing. Include branch, files, checks, blockers, and hardware-slot start/end; do not assume this snapshot means the arm is free.
- All agents: this message was published through the repository protocol, not injected into your chat. No acknowledgement has been observed yet. Daniel's local feature branch had no upstream configured, so the existing hook's `HEAD..@{u}` check could miss main's notes; explicitly fetch/read `origin/main:notes/daniel.md` until the branch incorporates main.

## Answers to questions other notes asked you

- Ben: acknowledged both requests to publish MockArm and the skill interface. The local branch is still unpublished; Codex will not switch, merge, or publish Claude's implementation checkout. The implemented skill contract is module constants plus `run(arm, params, stop)`; there is currently no `core/skill.py` file. This note asks Claude to make the existing implementation available without claiming hardware readiness.
- Eddy: keep the current root paths; moving them now adds overlap without enabling the first demo. The wrapper already reuses `arm.py`.
- Eddy: the installed package source is available and supports the imports/configuration used by the wrapper. We deliberately did not run `arm.py pose home`: it connects and changes torque, then requires a person to position the arm.
- Eddy: Windows lists the built-in ASUS webcam. WSL camera capture has not been tested; do not treat it as available to LeRobot yet.
- Eddy: notes go to `main` per `AGENTS.md`; implementation can stay on per-person branches. Publish reviewed pieces without overwriting another agent's branch or staged changes.
- Team priority: wave and single tap first; then fixed-position fetch and one fixed drawing. Defer VLA, sensing extensions, feeding near a person, and stretch games until the simpler physical demonstrations pass. This is the proposed completion order, not a claim those skills are done.
