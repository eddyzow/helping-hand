# Helping Hand: project context

Read this before writing any code or prompting any agent. It replaces the earlier Lego-only plan.

> **Fill in:** names for Persons 1, 3 and 4, the submission deadline `____`, the SayoDevice model and key count `____`, and which cameras we have `____`.

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

### Person 1: Voice and VLA (name: ____)

**Owns:** `core/dispatcher.py`, `core/skill.py`, `voice/`, `learning/`.

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

### Person 2: Arm core, fetch and feed (Daniel)

**Owns:** `core/arm.py`, `vision/`, `skills/fetch.py`, `skills/feed.py`, `skills/duplo.py`.

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

### Person 3: Keypad and games (name: ____)

**Owns:** `keypad/`, `skills/geometry_dash.py`, `skills/duel.py`, `skills/rhythm.py`, `skills/replay.py`.

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

### Person 4: Drawing, personality and demo (name: ____)

**Owns:** `skills/draw.py`, `skills/personality.py`, `skills/tictactoe.py`, `ui/`, `docs/`.

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
- Seeed Studio SO-ARM101 Pro kit, pre-assembled.
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
