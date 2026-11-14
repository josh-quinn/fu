---
name: follow-ups
description: Park ideas and unfinished work on the user's follow-up board so nothing is lost when they switch focus, file them under the job (usually a Jira epic, story, bug or spike) they belong to, and find or resume them later. Use whenever the user has a side-idea mid-task ("idea:", "note for later", "we should also…", "don't let me forget"), wants to "park this", "come back to this later", "add to my follow-ups / todo / board", switches task with something half-done, or asks "what did I park", "what's on my follow-ups", "what was I working on", "show me everything for <job>", or wants to resume a parked session. Works from Claude Code and Copilot CLI, via the `fu` command.
---

# Follow-ups

While the user works on a job (a Jira epic, story, bug or spike, usually), ideas and loose ends come up: three in one session, ten across four sessions. Each one is worth parking so the current work can carry on. The board, driven by the `fu` CLI, keeps them, ties them to their job, and records the session they came from so it can be reopened. Never edit the board's files by hand.

Three things live on the board:
- **Follow-up**: a parked idea or piece of unfinished work: a one-line summary, why it came up, and the session it came from.
- **Job**: the container for a piece of work, usually mirroring a Jira issue (its ID is the Jira key). It collects its follow-ups, its sessions and its outputs.
- **Output**: a useful document, skill or repo a session made for the job (runbooks, explainers, cheatsheets, review notes, often in a gitignored `.temp/`). These are picked up from what the session wrote; you don't need to register them.

## Parking (the main flow): seconds, no questions

1. **Recognise it.** The user had an idea or is leaving something unfinished. If it's unclear whether they want it parked, park it; an extra entry is cheap, a lost idea isn't.
2. **Write it from the session; don't interrogate the user.**
   - summary: one line naming the thing, e.g. "Cache activations between forward and backward pass".
   - `--why`: 1-2 sentences on what prompted it and where things stand, so it can be picked up cold.
3. **Leave the job to `fu`.** It files the follow-up under the job this session is working on (the job of the session's other follow-ups, or the job whose home folder you're in) and says so. Only:
   - add `--no-job` when the idea is clearly unrelated to the current work;
   - add `--job "<name or Jira key>"` when it belongs to a different, existing job (`fu job ls` lists them).
   Don't create jobs while parking unless the user asks; jobs mirror real pieces of work.
4. **Run it:**
   ```bash
   fu add "<summary>" --why "<why + where it stands>" [--no-job | --job ML-12]
   ```
   `fu` detects the agent, folder and session. In Copilot CLI add `--agent copilot`. Use `--status doing` if the user is actively mid-way rather than noting something for later.
5. **Confirm in one line**: the id, the job it went under, and the restart command. If it printed "no session id captured", say so and show the fix (`fu edit <id> --agent ... --session-id ...`); don't invent an id.
6. **Carry on with what the user was doing.** Parking is a side-trip.

To attach a document to a follow-up yourself (rarely needed): `fu add ... --artifact PATH --label "Prod runbook"`.

If `fu` isn't found, tell the user to install it with `brew install josh-quinn/tap/fu` (then `fu skill install` links this skill into Claude Code and Copilot CLI), and retry.

## If this session was started from fu

The system prompt (Claude) or first message (Copilot) has a handoff brief: the job, its open follow-ups, earlier sessions and outputs, and which follow-up this session is. Treat it as background. Mark that follow-up done with `fu done <id>` when the work is finished, and park anything new as above; it lands on the same job.

## Reviewing and resuming

- `fu ls` lists open follow-ups, least recently touched first. Filters combine: `--job NAME|none`, `--session ID-FRAGMENT`, `--agent`, `--status`, `--search TEXT`, `--idle N`, `--recent N`; `--json` is for you to parse.
- `fu job ls` lists jobs with their open and done counts; `fu tree` shows jobs > sessions > follow-ups.
- `fu show <id>` shows the full entry; `fu resume <id> --print` gives the restart command to hand the user. Don't run `fu resume` yourself from inside a session: it replaces the current process.
- When the user picks a follow-up back up, `fu touch <id>`; when it's finished, `fu done <id>`. Done follow-ups are kept (hidden from `fu ls`, shown with `--all`) until the user removes them with `fu rm`.
- The TUI: run `fu` in a terminal. `1` Jobs, `2` Follow-ups, `shift+R` resumes a follow-up's session or starts a new session for a job with a brief, `shift+P` promotes a follow-up to its own job, `h` for help.

## Other commands

`fu edit <id> [--summary --why --status --job NAME|none --agent --session-id --cwd --note]`, `fu reopen <id>`, `fu rm <id> -y`, `fu job add NAME [--id JIRA-KEY --kind story --parent KEY --home DIR --project KEY]`, `fu job edit`, `fu job rm`, `fu path`. Statuses are `todo`, `doing`, `done`. Job types are epic, story, bug, spike and task, plus any the user adds. Deleting a job keeps its follow-ups and just unassigns them.

## Where things live

- Data: `~/development/follow-ups/board.json` (the source of truth) and `BOARD.md` (generated, readable anywhere); briefs for new sessions in `briefs/`.
- Config: `~/.config/jq-tools/follow-ups/config.yaml`: data folder, job types and templates, and default agent settings, with per-project overrides. All the user's own tools keep config under `~/.config/jq-tools/`.
- Set `FU_DATA_DIR` to point a command at a different board, e.g. when testing. When testing the TUI in tmux, pass it on the tmux command line itself (`tmux new-session "env FU_DATA_DIR=... fu"`); an existing tmux server doesn't inherit exported variables and the test would hit the real board.
