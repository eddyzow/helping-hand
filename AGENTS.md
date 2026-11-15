# Instructions for coding agents in this repo

## What goes on `main`

`main` holds the project: the code, `README.md` and the files the code needs.

Working notes, plans, drafts and status files live on the `team-notes` branch. That covers `notes/`, `context/`, planning documents and any Markdown under `docs/`.

- To read a note: `git fetch origin` then `git show origin/team-notes:notes/eddy.md` (or another path).
- To write a note: `git worktree add ../team-notes team-notes`, edit your file there, commit, and `git push origin team-notes`.
- If a pull or a merge would bring one of those files onto `main`, leave it off `main` and commit it to `team-notes`.
- `README.md` describes the project. Changes to it go through Eddy.

## The protocol

1. Pull before you do anything. At the start of every turn, and again before every push, run `git pull --rebase`.
2. Read what changed. After pulling, run `git log --oneline -15`.
3. Tell your person what is new. If a teammate's commit affects what your person is doing, say so before continuing.
4. Push small and often. Commit each working piece and push it straight away.
5. Only edit the folders your person owns. To change something that belongs to someone else, ask your person to ask them.

## Rules

- Never commit secrets. API keys live in `.env`, which git ignores.
- Never force push, and never rewrite history on `main`.
- If a pull hits a conflict in code, resolve it by keeping both sides' work.
- Never enable torque or move the arm without your person's go-ahead, and say which arm will move.
- Check the installed LeRobot version before trusting any LeRobot API written in this repo.

## Event facts

- Final Devpost submission is due Sun Nov 15, 9:00 AM ET; submit by 8:00. Table judging with a live demo is 12:30 to 3:00 PM.
- Our [HACKUMASS] category is [HARDWARE] Best Mechanical Hack.
- The repo is public from the final submission onward.
