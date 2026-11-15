# RobTop
*because your desk could use an extra arm...*

RobTop (short for Robot Tabletop) is a robot arm that sits on your desk and takes on whatever job you put in front of it. So far that includes drawing, playing tic-tac-toe against you, beating Geometry Dash levels, copying your hand, a few dance moves, and more! Built at HackUMass XIV, November 13 to 15, 2026.

## Inspiration

Robot arms that can do more than one job usually live in labs and cost thousands of dollars. The cheap ones you can print at home tend to do one trick. We wanted to know how many different jobs one cheap arm can do when the software makes up for the hardware. So we 3D printed an open-source arm, assembled it at the event, put it on a table, and started handing it things.

## What it does

Give it a pen and it draws. A webcam above the table photographs the page, compares the ink with the drawing RobTop meant to make, and the arm corrects itself on the next pass. It has drawn a house and a flower. On the house, the ink ended up about a millimetre from the planned shape, and the flower takes 50 seconds.

<img src="docs/drawloop/house_round10.jpg" width="320" alt="A house drawn by the arm, as the webcam scores it: the planned lines in green and the ink in red">

What the webcam sees: the plan in green, RobTop's ink in red.

Draw an X and it plays you. RobTop draws a tic-tac-toe grid and waits. When the webcam sees a new X in a square, the arm thinks through every possible game and draws its O. It has played four full games against us and won all four. The best you can do against it is a draw.

Give it a key to press and it plays a video game. Geometry Dash has one button, and a single press that comes a moment late sends you back to the start. RobTop presses a real key with its claw and plays the level from memory, sending each press about a tenth of a second early to make up for its own reaction time. It cleared Stereo Madness, the game's first level, three times on Saturday night. It also played a 47-second, 67-press recording of a second level, God Yeeter, without dying.

Take the second arm in your hand and it follows you. We built two arms. Move the small one and the big one copies you, joint for joint, with a filter you can switch on to smooth out a shaky hand.

Press a key and it says hi. A three-key pad next to the arm sets off a wave, a nod, a fist bump, a victory pose and a dance.

Or just tell it. Type a sentence like "wave at me" and a language model picks the matching move.

## How we built it

- Hardware: two SO-101 arms (one to do the work, one to hold), 3D printed and assembled at the event, each with six Feetech STS3215 servos. A 1080p USB webcam over the table, a SayoDevice O3C three-key pad, a Sharpie, and a Windows laptop.
- Motion: Python on LeRobot's motor drivers. One program owns the arm and runs one move at a time, and everything else asks it over a local socket.
- Drawing: OpenCV finds the sheet of paper by its corners and flattens the photo to millimetres. We showed the arm where the paper is by hand, measured how much slack the joints have, and start each stroke a few millimetres early to cancel it.
- Tic-tac-toe: the same camera code looks for new ink in each of the nine squares, and a full search of the game picks the reply.
- Geometry Dash: we recorded the key presses for a level, measured how long the arm takes to press and release the key (about 105 and 116 ms), and send every command early by that much.
- Second arm: the two arms were calibrated differently, so we measure a fixed offset per joint and add it. The shake filter is a low-pass filter on the joint angles.
- Language: Claude reads a one-line description of each move and picks one. It only chooses the move. The motion is always one we taught the arm.
- Simulation: a MuJoCo model of the arm, so new moves get tried on a laptop before they touch the real thing.
- Testing: a lot of paper.

## Challenges we ran into

The arm doesn't go where you tell it. Hobby servos have slack in every joint, so the pen lands a few millimetres from where it was sent. Every small circle RobTop drew started with a straight tail and came out looking like a 6. We fixed it by measuring the slack, starting each stroke early, and letting the pen run in along the direction of the stroke before it touches the paper.

A Sharpie is too thin to hold. The claw was plenty strong, but the marker was too thin for it to get a firm hold. The fix was duct tape wrapped around the barrel until it was thick enough. In typical hacker fashion, it stayed that way!

One motor kept overheating. The wrist-roll servo reached 63 C and stopped answering for a few minutes at a time, and because every program checked all six motors, it took everything else down with it. Drawing and tic-tac-toe don't need that joint, so now they switch it off as soon as they connect.

Geometry Dash doesn't forgive a late press. The arm takes about a tenth of a second to press a key, and that delay changes whenever the keypad gets nudged. So we measure it again every time the pad moves.

## What we learned

- Cheap servos have slack, and you can measure it and plan around it.
- A camera looking at the result fixes more than a better model of the arm does.
- Geometry Dash is a very strict timing test.
- Duct tape is a legitimate engineering material.

## What's next for RobTop

The next thing we want is teaching by showing: guide RobTop once with the second arm, and have it repeat the job without you. The recording code is already in the repo. After that:

- Writing any text you type, which already works in our simulator.
- Picking things up off the table by sight.
- Asking for any job out loud, as well as by typing.
- More levels.

## Individual contributions

Daniel owned the real arm: the motion core, the drawing loop, tic-tac-toe, the gestures and the second-arm control.

Jonathan owned Geometry Dash: recording the levels, replaying them, and a simulated keypad to test the timing on.

Eddy built the plain-English control, the drawing generator and the simulators, and made the demo video.

Ben wrote the demo and the pitch, and gave the arm its personality moves.

## Run it

You need Python 3.12 and, for the real arm, [LeRobot](https://github.com/huggingface/lerobot) and a calibrated pair of SO-101 arms. The simulator needs no hardware. The real-arm demo scripts (`demo/`, `teleop_sync.py`) live on the `daniel/arm-core` branch until they are merged.

```bash
uv venv && uv pip install -r requirements.txt
python keypad/geometry_dash/fetch_so101_model.py   # downloads the arm's simulator model, once
python sim_draw.py cat                             # simulator: the arm draws a cat
python -m tests.test_core                          # prints "core ok"

source demo/cmds.sh        # on the arm laptop; change the two paths at the top to yours
ttt                        # tic-tac-toe against a person
flower                     # or: house
dispatcher                 # owns the arm; Geometry Dash and the pad gestures need it
gd                         # Geometry Dash, with `keypad` running in another terminal
python teleop_sync.py      # the big arm copies the small one
```

## Built with

Anthropic API, Feetech STS3215, Hershey Fonts, LeRobot, MuJoCo, NumPy, OpenAI API, OpenCV, Python, SO-101

## What we made, and what we built on

We wrote the project's code during the event, 3D printed the parts, and assembled and calibrated both arms ourselves. We did not design the arm. We wrote the code with a lot of help from AI coding agents, Claude Code among them, and each of us ran an agent that left notes for the others in `notes/`.

- [SO-101](https://github.com/TheRobotStudio/SO-ARM100) by TheRobotStudio: the arm's mechanical design.
- [LeRobot](https://github.com/huggingface/lerobot) by Hugging Face: motor drivers and calibration.
- [MuJoCo](https://mujoco.org) and the SO-101 model from [MuJoCo Menagerie](https://github.com/google-deepmind/mujoco_menagerie): the simulator.
- Hershey Fonts and Google's Quick, Draw! doodles: stroke data for writing and sketches.
- SayoDevice Visualizer (MIT): the keypad's 3D model in the simulator.
- Claude and OpenAI models: picking a move from a sentence, and speech to text.

Geometry Dash is played from key presses we recorded. RobTop doesn't watch the screen.

## Bill of Materials

| Item | Purpose | Quantity |
|:---|:---|:---|
| SO-101 follower arm, 3D printed | The arm that does the work | 1 |
| SO-101 leader arm, 3D printed | The one you hold | 1 |
| Feetech STS3215 servo | Six per arm | 12 |
| USB serial motor adapter | One per arm | 2 |
| USB webcam (1080p) | Eyes above the table | 1 |
| SayoDevice O3C three-key pad | The Geometry Dash key and the gesture buttons | 1 |
| Sharpie | Drawing | 1 |
| Duct tape | Makes the Sharpie thick enough to hold | some |
| A4 paper | Drawings and tic-tac-toe | a lot |
| Windows laptop | Brains | 1 |
