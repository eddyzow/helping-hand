# Instructions for every AI agent working in this repo

Four people are building this at HackUMass XIV, each with their own coding agent (Claude Code, Codex, Cursor). The agents cannot talk to each other directly. This repo is how they communicate. Follow this file whichever agent you are.

## The protocol

1. Pull before you do anything. At the start of every turn, and again before every push, run `git pull --rebase`. Your picture of the repo goes stale within minutes.
2. Read what changed. After pulling, run `git log --oneline -15` and read any file in `notes/` that changed since you last looked. Other agents leave you messages there.
3. Tell your person what is new. If a teammate's note or commit affects what your person is doing, say so before continuing.
4. Write your own note. Keep `notes/<your-person>.md` current (for example `notes/eddy.md`, `notes/daniel.md`). One file per person, so notes never conflict. Rewrite it as things change; it is a status board, not a diary. Use these headings:
   - Working on now
   - Done and how it was tested (say plainly what has never run on the real arm)
   - Needs from others, each line addressed to a person by name
   - Answers to questions other notes asked you
5. Push small and often. Commit each working piece and push it straight away. Notes always go to `main`, so everyone sees them on their next pull.
6. Only edit your own note file and the folders your person owns. To change something that belongs to someone else, ask in your note.

## Rules

- Never commit secrets. API keys live in `.env`, which git ignores.
- Never force push, and never rewrite history on `main`.
- If a pull hits a conflict, resolve it by keeping both sides' work. Do not discard a teammate's changes.
- Never enable torque or move the arm without your person's go-ahead, and say which arm will move.
- Check the installed LeRobot version before trusting any LeRobot API written in this repo.

## Which document is current

- `newcontext.md` is the team plan: what we are building, the four roles, the shared code contracts, safety. Read it first. Written by trkang, Sat 12:06 AM.
- `PLAN.md` has the event facts: deadlines, judging criteria, track choice, rules that can disqualify us. Its feature list is older than `newcontext.md`.
- `context.md` is an earlier Duplo-only plan. Only its hardware section is still useful, and `newcontext.md` section 8 repeats it.
- `notes/` is the live status of each person.

## Event facts every agent needs

- Hacking began Fri Nov 13, 8:30 PM ET. Initial Devpost submission is due Sun 12:00 AM (Saturday midnight). Final is due Sun 9:00 AM (hackumass.com) or 10:00 AM (Devpost); work to 9:00 and submit by 8:00. Table judging with a live demo is Sun 12:30 to 3:00 PM.
- Idea changes and new features stop at about Sat 8:50 PM, two thirds of the way through.
- The repo is private and must be made public before the Devpost submission.
- No code written before the start time may be copied in. Disclose open source in the README.
