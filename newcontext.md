# Helping Hand: project context

Read this before writing any code or prompting any agent. It replaces the earlier Lego-only plan.

> Updated Sat Nov 14, 12:50 AM by Daniel: names assigned (Ben and Jonathan swapped at 1:00 AM: Jonathan had already built Geometry Dash), and each role now says what already exists so nobody rebuilds it. If you want a different role, say so in your `notes/<name>.md` and swap; do not just start on someone else's folder.

## PIVOT, Sat Nov 14, 8:30 PM: Steady Hand (read this first; it overrides the feature list below)

Agreed by all four of us. Written by Daniel's agent.

**What we are now building.** An assistive arm for people whose hands shake (tremor, Parkinson's). The person moves the small **leader** arm; the **follower** arm copies the movement **with the tremor filtered out**, and holds light things steady for them. A dashboard shows the hand's shake, the arm's shake and how much was removed. The buddy features that already work on the real arm stay as extras: gestures, "hold this / give it back", voice commands, and Geometry Dash as proof of precision.

**Pitch in one line:** *your hand shakes, the arm does not.*

**Why we pivoted.** Everything that worked on the real arm today used positions a person supplied (taught poses, a brick handed to the claw, the Geometry Dash tap). Everything that failed needed the camera to locate an object to within millimetres: four hours of attempts, no brick picked off the table. Steady Hand needs no object finding at all: the person does the aiming.

**How it works.** Deliberate movement is slow (below about 2 Hz). Tremor is fast (about 4 to 12 Hz). A low-pass filter between the two arms passes the first and holds back the second. The follower's speed is capped.

### What exists now

| Piece | Where | State |
|---|---|---|
| Tremor-filtering teleoperation, standalone | `steady.py` on `daniel/arm-core` (`f865171`) | Synthetic tests pass (`tests.test_steady`): a 0.5 Hz reach passes at 94 %, a 6 Hz shake is cut by 90 %, the shake meter reads a 5 mm test shake as 3.54 mm RMS at 6.0 Hz. **Not yet run with a person on the leader.** |
| The same idea as a dispatcher skill | `skills/steady.py` on `jonathan/tremor-assist` (`30c95fd`) | Passes its own self-check on a fake arm and fake leader. **Never run on hardware.** Held by review until a real run. |
| Dashboard | `steady_dashboard.html`, served by `steady.py` at `http://127.0.0.1:8780` | Works against a simulated shaking hand (16 mm hand, 1.9 mm arm, 88 % removed). |
| Plain teleoperation with a per-joint offset and a gliding start | `teleop_sync.py` on `daniel/arm-core` | Ran on both real arms. The two arms' zero points differ, so an offset is measured once with both arms folded against their end stops. |
| Take / hold / give back | `skills/hand.py` on `daniel/arm-core` | Mock-tested. The underlying grasp of a handed brick worked 4 times out of 4 on the real arm (claw reads about 16 holding a brick, about 5 empty). |
| Gestures on the middle key | `skills/gesture.py` on `daniel/arm-core` | Mock-tested only. |
| Offline voice commands | `rubby_listen.ps1` on `daniel/arm-core` | Windows speech recognition with a fixed phrase list, no API key. Started once; phrases not yet tried on the real arm. |
| Geometry Dash | `keypad/geometry_dash/arm_play.py`, `my_macro_full.csv` | One full clear of Stereo Madness in normal mode in 3 counted attempts (the other two reached 95 %). **Not through the 4-of-5 gate.** |

### Facts about the real arm every lane needs

- **The follower's elbow stops at about +65 degrees.** At calibration its elbow was swept through only part of its travel, and LeRobot stores that range as a limit inside the motor. Any pose that asks for more bend silently stops there (measured: 23 degrees short of its command, in free air). This is the cause of the "weak grip", "hovering claw" and wrong-distance reports from today. Fixing it means recalibrating that joint, which rewrites a motor setting and shifts every taught pose; **nobody does that without Daniel's go-ahead.**
- **The arm can feel the table:** motor load jumps at contact (`Present_Load`). Use that instead of trusting a height.
- **Only one program can hold the follower's serial port.** `steady.py`, `teleop_sync.py` and the dispatcher cannot run at the same time. On this laptop the follower is COM3 and the leader COM4, run natively on Windows (not WSL).
- **Light objects only.** Do not test with anything heavier than a marker or a Duplo brick.

### Lanes (from now until the final submission)

| Lane | Owner | Does |
|---|---|---|
| **A. Real-arm bring-up** | Daniel | First real runs of the tremor filter with a person on the leader; the offset line-up; the elbow decision; a counted before/after measurement (shake in mm with steady mode off and on). Publishes the numbers. |
| **B. One implementation** | Jonathan | `skills/steady.py` is the version that lives in the dispatcher. It should take the per-joint offsets (`poses/teleop_offset.json`), and share the filter and the shake meter with `steady.py` instead of having two copies. Daniel's agent is moving that shared maths into `core/tremor.py`. |
| **C. Dashboard and tracking** | Daniel's agents, Ben for look and wording | Session history, a ten-second "hold still" test with a score, a trend chart. |
| **D. Voice and buddy extras** | Eddy | "Steady on / off", "hold this", "let go", gestures. Pointing, drawing and writing stay as extras if they pass on the real arm. |
| **E. Demo, pitch, Devpost** | Ben | Rebuild the script around Steady Hand. Keep the 4-of-5 rule for anything shown live. |
| **QA** | Codex | Reviews every lane's branch as before. |

### What we may and may not claim

- Say: a **prototype** that removes a simulated tremor from a teleoperated arm, with measured numbers.
- Say: tested with **us shaking the leader on purpose**. Not tested with patients.
- Do **not** say it makes anyone stronger: the arm lifts light things only.
- Do **not** say it measures force or torque. We have no force sensor. Grip effort and arm load are the motors' own load readings, and the dashboard labels them as estimates.
- Do **not** say it treats or improves tremor, and do not call the tests "therapy" or "exercises that help". Say "steadiness tests that measure and track".
- Geometry Dash stays "reported, pending the gate" until five counted attempts exist.

---

## Who does what (before the pivot; kept for the record)

| Person | Name | Role | Start here |
|---|---|---|---|
| P1 | **Eddy** | Voice, object finding, fetch by camera | Run `see.py` and the `pick.py` dry run on real photos from the overhead camera, then a live microphone |
| P2 | **Daniel** | Arm core, dispatcher, the real arm, fetch from a taped spot, feed | Wave and single tap on the real arm from the keypad, then publish `daniel/arm-core` |
| P3 | **Jonathan** | Keypad and games: Geometry Dash (his version already works), tap timing, reaction duel | Push the Geometry Dash code, then fit it to `arm.tap()` and the skill interface |
| P4 | **Ben** | Drawing, personality moves, status screen, demo, pitch, Devpost | Demo script and pitch outline tonight; pen holder; personality moves against `MockArm` |

Facts filled in: final submission Sun 9:00 AM (work to 8:00), table judging Sun 12:30 to 3:00 PM, feature freeze Sat 8:50 PM. The SayoDevice is a 3-key pad (USB id `8089:0009`): its keys send X (wave), C (jump, the key the arm taps) and Z (stop). No external camera is connected yet; the only camera on the arm laptop is its built-in webcam, and WSL sees no camera at all.

### What already exists (do not rebuild)

- On `main`, by Eddy, at the repo root: `see.py` (request to pixel, typed or spoken, through Gemini), `pick.py` (pixel to taught grid to grasp), `arm.py` (teach, pose, record, replay), `grid.py`, `draw.py` (doodle, text or generated strokes with a preview). None of the arm paths has run on the real arm.
- On branch `daniel/arm-core`, by Daniel: `core/arm.py` (the section 5 arm API plus `MockArm`, wrapping root `arm.py`), `core/dispatcher.py` (one skill at a time, `run` / `stop` / `home` / `list`, typed or over localhost port 8765), `skills/wave.py`, `skills/gd_tap.py` (a single tap), `keypad/listen.py` (SayoDevice to dispatcher, runs on Windows), `voice/route.py` (a sentence to a skill name through Gemini), `tests/test_core.py`. Tested on the mock arm and with the real keypad; not yet on the real arm.
- There is no `core/skill.py` file. A skill is a module in `skills/` with `NAME`, `DESCRIPTION`, `PARAMS` and `run(arm, params, stop)`, exactly as in section 5.
- Poses `home`, `wave_up` and `tap_up` are taught on the arm laptop.

---

## 1. What we are building

A desk robot buddy. One SO-101 arm with a library of skills: it plays Geometry Dash on a keypad, hands you things, feeds you a snack, writes your name, plays games against you, and has a bit of personality. You trigger skills with keypad buttons or by voice.

Pitch in one line: **a robot arm with many skills that anyone can trigger with one button or one sentence.**

## 2. How we work: hard-code first, smart later

We are building many features in parallel, so every skill ships in a dumb version first.

| Phase | What "done" means | Typical techniques |
|---|---|---|
| **1. Hard-coded** | The skill runs from a keypad key with objects at taped positions. | Scripted joint moves, record and replay, fixed timings. |
| **2. Sensing** | The skill adapts to what the camera or screen shows. | YOLO for objects, MediaPipe for face and mouth, screen capture, voice routing. |
| **3. Learned** | A trained policy does the skill. | Imitation learning (ACT or SmolVLA) from about 50 teleop demos. |

Rules:
- Do not start phase 2 of a skill until its phase 1 works on the real arm.
- A phase 1 skill that works beats a phase 3 skill that almost works.
- Cap: get four skills polished before adding a fifth.

## 3. Feature list

| # | Feature | Owner | Phase 1 (hard-coded) | Later (smart) |
|---|---|---|---|---|
| 1 | Skill dispatcher | P1 | Run one skill at a time by name, with stop | Queue, spoken status |
| 2 | Voice control | P1 | Keyword match on speech-to-text | LLM picks skill and parameters, talks back |
| 3 | Learned skill (VLA) | P1 | None | Record demos, train on cloud GPU, run the policy |
| 4 | Arm core API | P2 | Home, joint moves, gripper, tap | Inverse kinematics to table coordinates |
| 5 | Fetch and hand over | P2 | Pick from a taped spot, hand to a fixed spot | YOLO finds the object anywhere |
| 6 | Feed me | P2 | Snack from a fixed bowl to a fixed stop point | Waits for an open mouth, tracks the face |
| 7 | Duplo (stretch) | P2 | Stack two bricks from taped spots | Colour detection, sort by colour |
| 8 | Keypad input | P3 | Each key runs a skill; one key is emergency stop | Hold a key to record a motion, tap to replay |
| 9 | Tap delay tuning | P3 | Command 20 taps, measure delay and jitter from key events | Automatic on startup |
| 10 | Geometry Dash | P3 | Memorised tap times for one easy level | Read the screen and tap on obstacles |
| 11 | Reaction duel | P3 | Judge and robot each have a key; first to tap after a flash wins | Camera-only "fair mode", handicap dial |
| 12 | Rhythm tapping (stretch) | P3 | Tap at a fixed tempo | Detect the beat of a song |
| 13 | Write and draw | P4 | Write a fixed word in block capitals | Any name or doodle from a voice request |
| 14 | Personality | P4 | Wave, nod, dance, fist bump as recorded moves | Wave when a face appears, celebrate or droop on Geometry Dash results |
| 15 | Tic-tac-toe (stretch) | P4 | Draw a mark in a chosen cell | Camera reads the board, picks the move |
| 16 | Status screen | P4 | Shows current skill and camera feed | Detection boxes, mood face |
| 17 | Demo and pitch | P4 (lead), everyone | Demo script, video, submission | |

## 4. Roles

One folder per person. Stay in your folder unless you have agreed otherwise.

### Person 1: Voice, vision and fetch by camera (Eddy)

**Owns:** `voice/`, `learning/`, and the root files he wrote: `see.py`, `pick.py`, `grid.py`, `draw.py`, `arm.py`.

**Changed from the first draft:** the dispatcher and the first `voice/route.py` are already written on `daniel/arm-core`, so Daniel keeps `core/dispatcher.py` and Eddy takes over `voice/` from there. Eddy's `see.py` and `pick.py` are the camera version of fetch, so that part of fetch is Eddy's. The phase 1 list below is the original; items 1 and 2 are done.

**Next for Eddy**
1. Real photos and the live microphone through `see.py`, then the `pick.py` dry run with the camera mounted.
2. Wrap `pick.py` as a skill (`skills/fetch.py` calling it) so "bring me the X" runs through the dispatcher and the stop key.
3. Make `voice/route.py` speak a short reply and pass parameters (the object name) to skills.
4. Decide with Daniel where the camera runs: WSL has no camera, so the camera side may need to run on Windows.

**Phase 1**
1. Define the skill interface and dispatcher in section 5 and commit them first, because everyone else builds on them.
2. A keyboard test harness: type a skill name, it runs.
3. Speech-to-text with simple keyword matching ("wave", "feed me", "play").

**Later**
- LLM router: turn a free-form sentence into a skill name plus parameters, using each skill's description.
- Text-to-speech replies so the arm talks back.
- The learned-skill track: set up `lerobot-record` with cameras, record about 50 demos of one task (suggested: pick up an object from anywhere), train on the cloud GPU, and run the policy as a normal skill.

**Notes:** use SmolVLA or ACT through LeRobot. OpenVLA is too heavy for this arm and timeline. Learned skills need fixed camera positions, so agree those with Person 2 early.

**Done when:** saying a sentence runs the right skill, and one learned skill can be triggered like any other.

### Person 2: Arm core, dispatcher, the real arm, feed (Daniel)

**Owns:** `core/`, `keypad/listen.py`, `skills/wave.py`, `skills/gd_tap.py`, `skills/feed.py`, `skills/duplo.py`, `poses/`, and the arm laptop.

**Next for Daniel**
1. Wave, single tap and the stop key on the real arm.
2. Push `daniel/arm-core` so everyone can build on `MockArm`, then merge it to `main`.
3. Run the hardware slots: the arm is on Daniel's laptop, so he is at the arm for everyone's real-arm tests.
4. Fetch from a taped spot and the feed motion, as recorded motions.

**Phase 1**
1. The arm API in section 5 on the real follower, plus a `MockArm` with the same methods that only logs. Commit the mock first so nobody is blocked.
2. Fetch: pick an object from a taped spot and hand it to a fixed spot.
3. Feed: snack from a fixed bowl to a fixed stop point, slowly.

**Later**
- Camera-to-table calibration with ArUco markers.
- `vision/` helpers that others can call: `find_objects()` (YOLO) and `find_face()` (MediaPipe, with mouth-open flag).
- Fetch anywhere on the table. Feed that waits for an open mouth.
- Inverse kinematics so skills can ask for a table position in millimetres.
- Duplo stack or colour sort, if time allows.

**Done when:** fetch and feed each succeed 4 times out of 5, and the other three people are using the arm API without asking questions.

### Person 3: Keypad and games (Jonathan)

**Owns:** `skills/geometry_dash.py`, `skills/duel.py`, `skills/rhythm.py`, `skills/replay.py`, and `keypad/` apart from `listen.py`.

**Changed from the first draft:** phase 1 item 1 is done. `keypad/listen.py` already maps the three SayoDevice keys (wave, jump, stop), and `skills/gd_tap.py` does one tap. Jonathan has already built the Geometry Dash part; it is not in the repo yet.

**Next for Jonathan**
1. Push the Geometry Dash code and write `notes/jonathan.md` saying what it does and how it was tested, so the rest of the team can see it.
2. Fit it to the shared pieces: a `skills/geometry_dash.py` with `NAME`, `DESCRIPTION`, `PARAMS` and `run(arm, params, stop)` that presses the key with `arm.tap()`, so it runs from the dispatcher and the stop key works. Test it against `MockArm`.
3. Tap delay: in an arm slot with Daniel, command 20 taps on the jump key, time each key event, save the mean delay and the jitter. Shift the tap times by the mean.
4. Reaction duel, which needs no arm to write: flash, time two keys, show milliseconds.

**Phase 1**
1. Read the SayoDevice keys. Map each key to a skill through the dispatcher. One key is always emergency stop.
2. Tap delay tuning: command a tap, time when the key event arrives, repeat 20 times, save the mean delay and jitter.
3. Geometry Dash: memorised tap times for the start of one easy level, shifted by the measured delay.
4. Reaction duel: flash the screen after a random wait, time both keys, show both times in milliseconds, disqualify early presses.

**Later**
- Geometry Dash that reads the game from the screen and taps on obstacles.
- Record and replay: hold a key to record a motion from the leader arm, tap to play it back.
- Duel fair mode (the robot sees the flash through a camera) and a handicap dial.
- Rhythm tapping to a song.

**Notes:** keep the fingertip hovering a millimetre or two above the key. If the keypad supports it, set a shallow actuation point so light taps register.

**Done when:** every skill can be started and stopped from the keypad, and the arm clears the hard-coded Geometry Dash section most attempts.

### Person 4: Drawing, personality and demo (Ben)

**Owns:** `skills/draw.py`, `skills/personality.py`, `skills/tictactoe.py`, `ui/`, `docs/`.

**Changed from the first draft:** Eddy's root `draw.py` already turns a word or a doodle into pen strokes with a preview, and `skills/wave.py` exists. Ben wraps and extends these and does not rewrite them.

**Next for Ben**
1. Demo script and pitch outline in `docs/`, and settle the track with the team (`PLAN.md` recommends Best Accessibility Hack; this plan dropped that framing).
2. A pen holder that gives a little (spring, foam or rubber band), since the arm cannot feel pressure.
3. `skills/personality.py`: nod, dance, fist bump, celebrate and droop as short joint sequences, tested against `MockArm`, then tried in an arm slot.
4. `skills/draw.py` as a thin skill around root `draw.py`, starting with one fixed word.
5. Devpost draft and the backup demo video.

**Phase 1**
1. Personality moves as short recorded motions: wave, nod, shake head, dance, fist bump, celebrate, droop.
2. Writing: a pen holder, then one fixed word in block capitals 3 to 5 cm tall. Use a single-stroke (Hershey) font so letters are pen paths.
3. Status screen showing the current skill and the camera feed.
4. Demo script and pitch outline.

**Later**
- Write any name and draw simple doodles from a request.
- Paper setup: touch three corners of the page once so the code knows its height and tilt.
- Reactions: wave when a face appears, celebrate or droop on Geometry Dash results.
- Tic-tac-toe against a judge.
- Demo video and submission write-up.

**Notes:** use a felt marker or brush pen, or a springy holder. There is no force sensing, so a hard pen will skip or dig in.

**Done when:** the arm writes a legible name on request and the demo runs start to finish from the script.

## 5. Shared code contracts

Changing anything in this section needs a message to the whole team first.

### Skill interface (`core/skill.py`, Person 1)

Every skill is one file in `skills/`:

```python
NAME = "wave"
DESCRIPTION = "Wave hello to the person in front of the arm"   # the voice router reads this
PARAMS = {}                                                    # e.g. {"text": "str"} for writing

def run(arm, params, stop):
    """arm: the Arm object. params: dict. stop: threading.Event."""
    ...
    return {"ok": True, "reason": ""}
```

Rules for every skill:
- Check `stop.is_set()` between moves and return straight away if it is set.
- Never block for more than half a second without checking `stop`.
- Start from home and finish at home.
- Take the arm as an argument. Never open the serial port yourself.

### Dispatcher (`core/dispatcher.py`, Person 1)

```python
dispatch(skill_name, params=None) -> dict   # runs one skill at a time; refuses if busy
stop_all()                                  # sets the stop event and freezes the arm
list_skills() -> list[dict]                 # name, description, params
```

The keypad, the voice router and the status screen all go through these three functions.

### Arm API (`core/arm.py`, Person 2)

```python
get_arm(mock=False) -> Arm

arm.home()
arm.get_joints() -> list[float]                    # degrees
arm.move_joints(joints_deg, duration_s)
arm.move_to(x_mm, y_mm, z_mm, duration_s)          # phase 2, needs inverse kinematics
arm.gripper(open_fraction)                         # 0 closed, 1 open
arm.tap(depth_mm)                                  # quick down and up, for the keypad
arm.play(trajectory)                               # list of (time_s, joints_deg)
arm.stop()                                         # hold position now
```

`MockArm` has the same methods and only logs. Develop against the mock; test on the real arm in your slot.

### Units and frames
- Millimetres and degrees.
- Table frame: origin at the centre of the follower's base on the table. `+x` forward away from the arm, `+y` to the arm's left, `+z` up.

## 6. Sharing one arm

Four people, one follower arm.
- Write and debug against `MockArm`.
- Book the real arm in 20-minute slots in the team chat. Say when you start and when you finish.
- Only one process may hold the serial port. Close yours when your slot ends.
- Always run `home()` before handing over.
- Mark object positions on the mat with tape and do not move other people's marks.

## 7. Repo layout

```
helping-hand/
  context.md           this file
  core/                dispatcher, skill interface, arm API (P1 and P2)
  skills/              one file per skill
  voice/               P1
  learning/            P1: demo recording, training, policy runner
  vision/              P2: calibration, YOLO, face tracking
  keypad/              P3
  ui/                  P4: status screen
  docs/                P4: demo script, pitch, photos
```

- One branch per person. Merge to `main` often, in small pieces.
- `main` must always run with `MockArm`. If you break it, fix it before anything else.
- Python 3.12, one shared `requirements.txt`. Pin what you add.

## 8. Hardware and setup

**Arms**
- Open-source SO-101 arm kit. We 3D printed the parts and assembled both arms ourselves at the event (corrected by Eddy, Sat Nov 14, 7:30 PM; the earlier "pre-assembled" was wrong).
- Follower: 6 Feetech STS3215 12V motors, 12V power supply.
- Leader: 6 STS3215 7.4V motors, 5V power supply. **Never plug the 12V supply into the leader.**
- Motor IDs 1 to 6, baudrate 1,000,000. Each arm has its own USB serial adapter.
- No tactile sensors. Servo load and position readings are the only force feedback.
- The leader is for teleoperation: recording moves and recording demos for the learned skill.

**Other hardware**
- SayoDevice keypad (model and key count to be filled in). The arm taps one key; people use the others.
- LEGO Duplo brick box, 65 pieces plus 2 figures.
- Cameras: to be filled in. Learned skills want one fixed front camera and ideally one on the wrist.

**The arm machine**
- Windows laptop with WSL2 Ubuntu. LeRobot is installed inside WSL in a conda env named `lerobot`.
- USB devices only appear in WSL after `usbipd attach`.

**Startup (after every replug or reboot)**

1. Windows PowerShell as admin, once per arm:
   ```
   usbipd list
   usbipd bind --busid <BUSID>          # first time only
   usbipd attach --wsl --busid <BUSID>
   ```
2. WSL:
   ```
   conda activate lerobot
   ls /dev/ttyACM*
   sudo chmod 666 /dev/ttyACM*
   ```

**Ports (check each session, they can renumber)**
- Last known: follower `/dev/ttyACM1`, leader `/dev/ttyACM0`. Not yet confirmed.
- If the leader goes stiff and jumps while the follower stays limp, the ports are reversed. Press Ctrl+C and swap them.

**Calibration (already done)**
- Follower id `follower`: `~/.cache/huggingface/lerobot/calibration/robots/so_follower/follower.json`
- Leader id `leader`: `~/.cache/huggingface/lerobot/calibration/teleoperators/so_leader/leader.json`

**Teleoperate**
```
lerobot-teleoperate \
  --robot.type=so101_follower --robot.port=/dev/ttyACM1 --robot.id=follower \
  --teleop.type=so101_leader --teleop.port=/dev/ttyACM0 --teleop.id=leader
```
Hold the leader near the follower's pose before pressing Enter. The follower snaps to match it.

## 9. Safety

- One keypad key is always emergency stop. Test it at the start of every session.
- Feeding: slow speed, soft food or a plastic spoon only, and the arm stops short of the face so the person leans in. No forks or knives.
- Keep hands clear when a skill starts. Say "arm moving" out loud.
- Cap the pen when it is not drawing.
- Speed limit on every move near a person.

## 10. Rules for AI agents

Paste this file into your agent, then tell it which person you are.

- Only edit files in the folders owned by my role. Ask before touching `core/`.
- Follow the contracts in section 5 exactly. Do not change them.
- Use `MockArm` unless I say the real arm is free.
- Build the hard-coded phase 1 version first. Do not add sensing or learning until I say phase 1 works.
- Check `lerobot-<command> --help` and the installed LeRobot source for exact flags and APIs before using them; versions differ.
- Never write motor IDs, baudrate or other EEPROM values without asking.
- Never enable torque or command motion without my go-ahead, and say which arm will move.
- Calibration and teleoperation need a human moving the arms. Do not run them unattended.
- If a command fails, show the full error and your diagnosis before trying a fix.
- If `/dev/ttyACM*` is missing, tell me to re-attach with `usbipd`.

## 11. Open questions

- SayoDevice model and number of keys.
- Which cameras we have and where they mount.
- Submission deadline and judging format.
- Whether the swapped port mapping in section 8 is correct.
- Which skill gets the learned (VLA) version.
