# Instructions for every AI agent working in this repo

Four people built this at HackUMass XIV, each with their own coding agent (Claude Code, Codex, Cursor). Follow this file whichever agent you are.

## What `main` is for

`main` holds the project: the code, `README.md` and the files the code needs. It is what judges read.

Notes, plans, reviews, pitch drafts and status files do not go on `main`. On Sun Nov 15 at 6:00 AM, at Eddy's request, they were moved to the `team-notes` branch: `notes/`, `context/`, `context.md`, `newcontext.md`, `PLAN.md`, `docs/demo.md`, `docs/devpost.md` and `docs/tracks.md`. Nothing was lost.

- Do not add those files, or new ones like them, back to `main`.
- To read a note: `git fetch origin` then `git show origin/team-notes:notes/eddy.md` (or another path).
- To write a note: `git worktree add ../team-notes team-notes`, edit your file there, commit, and `git push origin team-notes`.
- If a pull or a merge stops on a conflict because one of those files was removed from `main`, accept the removal and put your change on `team-notes`.
- `README.md` is the current description of the project. If you think a sentence in it is wrong, tell your person. Do not commit a review of it.

## The protocol

1. Pull before you do anything. At the start of every turn, and again before every push, run `git pull --rebase`.
2. Read what changed. After pulling, run `git log --oneline -15`.
3. Tell your person what is new. If a teammate's commit affects what your person is doing, say so before continuing.
4. Push small and often. Commit each working piece and push it straight away.
5. Only edit the folders your person owns. To change something that belongs to someone else, ask your person to ask them.

## Rules

- Never commit secrets. API keys live in `.env`, which git ignores.
- Never force push, and never rewrite history on `main`.
- If a pull hits a conflict in code, resolve it by keeping both sides' work. Do not discard a teammate's changes.
- Never enable torque or move the arm without your person's go-ahead, and say which arm will move.
- Check the installed LeRobot version before trusting any LeRobot API written in this repo.

## Event facts every agent needs

- Final Devpost submission is due Sun Nov 15, 9:00 AM ET; submit by 8:00. Table judging with a live demo is 12:30 to 3:00 PM.
- The repo must be public before the final submission and stay public afterwards.
- No code written before the start time may be copied in. Open source is disclosed in the README.
