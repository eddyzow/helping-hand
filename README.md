# Helping Hand (working name)

A voice-commanded vehicle with an SO-101 robot arm on the front. Tell it where to go and what to bring back; it drives there by camera, picks the item up, and returns. Built at HackUMass XIV, November 13 to 15, 2026.

Status: the object finder works on still images. The vehicle and the arm control are not built yet. Read [PLAN.md](PLAN.md) for the current plan. `context.md` describes an earlier idea (a Duplo builder); its hardware setup section is still correct.

## Try the object finder

```
uv venv && uv pip install -r requirements.txt
echo "GEMINI_API_KEY=your-key" > .env        # key from aistudio.google.com/apikey
.venv/bin/python see.py "pick up the red brick"          # uses the camera
.venv/bin/python see.py                                  # speak the request
.venv/bin/python see.py --image photo.jpg "the mouse"    # test on a photo
```

It prints the pixel to grasp and saves the marked-up frame to `outputs/last.jpg`. Set `CAMERA=1` to use a different camera. On a Mac, the terminal needs camera and microphone permission in System Settings.

## Working in this repo

- Commit small and often, straight to `main`. Pull with `git pull --rebase` before you push.
- Never commit API keys. Put them in `.env`, which is ignored.
- If you use Claude Code here, a hook prints the hackathon clock and the current phase rule into each prompt. The dates live in `.hackathon.json`.

## Open source we use

HackUMass allows open source if it is disclosed. Add to this list as you add dependencies.

- [LeRobot](https://github.com/huggingface/lerobot) for SO-101 motor control, calibration and teleoperation
- SO-101 arm design by TheRobotStudio
