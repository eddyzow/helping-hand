# Helping Hand (working name)

A voice-controlled SO-101 robot arm for people with limited hand use. It fetches objects you name, feeds you from a bowl, and counts the coins on the table. Built at HackUMass XIV, November 13 to 15, 2026.

Status: planning. Nothing runs yet. Read [PLAN.md](PLAN.md) for scope, schedule, lanes and the track choice.

## Working in this repo

- Commit small and often, straight to `main`. Pull with `git pull --rebase` before you push.
- Never commit API keys. Put them in `.env`, which is ignored.
- If you use Claude Code here, a hook prints the hackathon clock and the current phase rule into each prompt. The dates live in `.hackathon.json`.

## Open source we use

HackUMass allows open source if it is disclosed. Add to this list as you add dependencies.

- [LeRobot](https://github.com/huggingface/lerobot) for SO-101 motor control, calibration and teleoperation
- SO-101 arm design by TheRobotStudio
