# Helping Hand (working name)

A voice-controlled SO-101 robot arm for people with limited hand use. It fetches objects you name, feeds you from a bowl, and counts the coins on the table. Built at HackUMass XIV, November 13 to 15, 2026.

Status: the object finder works on still images. The arm is not wired in yet. Read [PLAN.md](PLAN.md) for scope, schedule, lanes and the track choice. `context.md` describes an earlier idea (a Duplo builder); its hardware setup section is still correct.

## Try the object finder

```
uv venv && uv pip install -r requirements.txt
echo "GEMINI_API_KEY=your-key" > .env        # key from aistudio.google.com/apikey
.venv/bin/python see.py "pick up the red brick"          # uses the camera
.venv/bin/python see.py                                  # speak the request
.venv/bin/python see.py --image photo.jpg "the mouse"    # test on a photo
```

It prints the pixel to grasp and saves the marked-up frame to `outputs/last.jpg`. Set `CAMERA=1` to use a different camera. On a Mac, the terminal needs camera and microphone permission in System Settings.

## Voice pick up (the priority)

On the laptop with the arm and the overhead camera. Set up once:

```
python arm.py pose home        # arm parked out of the camera's view
python arm.py pose handover    # where the arm holds the object out
python arm.py teach table      # 3 by 3 grid: open gripper on the table, then lifted clear
python arm.py check table      # slow pass through the in-between points; watch for dips
python pick.py --corners       # click the grid's corners: far-left, far-right, near-right, near-left
```

Then:

```
python pick.py "pick up the mouse"        # dry run, marks the target in outputs/last.jpg
python pick.py "pick up the mouse" --go   # moves the arm
python pick.py --go                       # voice loop: Enter, speak, Enter
```

Run the dry run first and check the green outline and red cross in `outputs/last.jpg`. Redo `--corners` if the camera or the arm's base moves. If the gripper opens or closes the wrong amount, set `GRIP_OPEN` and `GRIP_CLOSED` (defaults 60 and 5). The gripper keeps the angle it was taught at, so long objects need to lie the way the gripper closes.

## Drawing

```
.venv/bin/python draw.py cat                # a doodle from the Quick, Draw! database
.venv/bin/python draw.py --text "Eddy"      # write a word
.venv/bin/python draw.py --gen "a rocket"   # Gemini invents the strokes (about 20 seconds)
```

Each run saves a preview to `outputs/draw.png`. Add `--go` to draw it with the arm, after teaching the paper grid.

## Arm commands (on the laptop with the arm; not yet tested on hardware)

```
python arm.py teach paper     # hand-pose the arm over a 3 by 3 grid on the paper, pen down then pen up
python arm.py record wave     # move the leader, the follower copies, the motion is saved
python arm.py replay wave     # the follower repeats it
```

Set `FOLLOWER_PORT` and `LEADER_PORT` if they differ from `/dev/ttyACM1` and `/dev/ttyACM0`. Keep someone on the power switch for first runs.

## Skills, keypad and voice routing (tested on the mock arm only)

```
python -m core.dispatcher --mock          # in WSL; drop --mock for the real follower (motors switch on)
python keypad\listen.py                  # on Windows: F13 wave, F14 gd_tap, F15 stop, any window focused
python voice/route.py "wave at me"        # Gemini picks the skill; no arguments = speak
```

A skill is one file in `skills/` with `NAME`, `DESCRIPTION`, `PARAMS` and `run(arm, params, stop)` (see `newcontext.md` section 5). The arm API is `core/arm.py`; `get_arm(mock=True)` needs no hardware. Before the real arm: `python arm.py pose home` (a resting pose), `pose wave_up`, `pose tap_up`. Check with `python -m tests.test_core`.

## Working in this repo

AI agents: read [AGENTS.md](AGENTS.md) first. It explains how agents pass messages to each other through `notes/` in this repo. People: tell your agent which person you are and have it keep `notes/<your-name>.md` current.

- Commit small and often, straight to `main`. Pull with `git pull --rebase` before you push.
- Never commit API keys. Put them in `.env`, which is ignored.
- If you use Claude Code here, a hook prints the hackathon clock and the current phase rule into each prompt. The dates live in `.hackathon.json`.

## Open source we use

HackUMass allows open source if it is disclosed. Add to this list as you add dependencies.

- [LeRobot](https://github.com/huggingface/lerobot) for SO-101 motor control, calibration and teleoperation
- SO-101 arm design by TheRobotStudio
