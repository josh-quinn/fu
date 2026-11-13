---
name: follow-ups
description: Park unfinished work on a follow-up board so it isn't forgotten when the user switches tasks, group it into jobs (epic, story, task, bug, spike, idea, misc), and look it up again later. Use whenever the user says they need to switch focus, context-switch, "park this", "come back to this later", "don't let me forget", "add to my follow-ups / todo / board", "I'll finish this after", or starts something new while a task is half-done, even if they never say "follow-up". Also use for "what's on my follow-up list", "what was I working on", "what did I park", "show me everything for <epic/bug>", or restarting/resuming a parked session. Works from Claude Code and Copilot CLI, via the `fu` command.
---

# Follow-ups

The user juggles tasks. When they pivot from task A to task B, task A should land on a board with enough context that they can pick it up cold days later, including the exact command that reopens this session. The board is driven by the `fu` CLI so the data stays consistent; never edit its files by hand.

Tasks can be grouped into **jobs** (a larger piece of work: epic, story, task, bug, spike, idea or misc). One job can span several agent sessions and one session can touch several jobs, so grouping is by job, not by session.

## Parking a task (the main flow)

1. **Recognise the switch.** The user is leaving something unfinished. If it's ambiguous whether they want it parked, park it anyway; an extra entry is cheap, a forgotten task isn't.
2. **Write the entry from the session, don't interrogate the user.** They are mid-pivot and want this to take seconds.
   - `summary`: one line naming the topic, e.g. "Fix backprop gradient check in week-2 notebook". Name the thing, not the activity.
   - `--why`: 1-2 sentences on why the work started and where it was left, so the user can re-enter without re-reading the session. e.g. "Started because numerical and analytic grads disagree at layer 2; suspect the ReLU derivative. Next: print both for a 2x2 input."
3. **Pick the job (only when there is a larger piece of work behind this task).** Run `fu job ls` first and reuse an existing job by its exact name; a near-duplicate name creates a second job and splits the work in two. If nothing fits and the task is clearly part of something bigger, name a new job and give its kind with `--kind` (bug for a defect, spike for time-boxed research, epic for a multi-week effort, idea for something not yet committed to; otherwise misc). A standalone task needs no job; leave `--job` off rather than inventing one.
4. **Run it:**
   ```bash
   fu add "<summary>" --why "<why + where you left off>" [--job "<job name>" --kind bug]
   ```
   `fu` detects the agent, working folder and session ID itself. In Copilot CLI add `--agent copilot`. Pass `--status doing` if the user was actively mid-flight rather than just noting something for later.
5. **Confirm briefly:** the id, the job if any, and the restart command it printed. If it printed "no session id captured", say so and show the fix (`fu edit <id> --agent ... --session-id ...`); don't invent an id.
6. **Then carry on with the new task.** Parking is a side-trip, not a topic.

If `fu` isn't found, tell the user to install it with `brew install josh-quinn/tap/fu` (the skill ships with it; `fu skill install` links it into Claude Code and Copilot CLI), then retry.

## Reviewing and resuming

- `fu ls` shows open items, oldest-touched first (the neglected ones surface). Filters combine: `--job NAME|none`, `--session ID-FRAGMENT`, `--agent`, `--status`, `--search TEXT`, `--idle N` (untouched for at least N days), `--recent N` (touched within N days). `--json` is for you to parse.
- `fu tree` prints jobs > sessions > tasks and sessions > tasks in one view; `fu job ls` and `fu sessions` give the counts.
- `fu show <id>` for the full entry; `fu resume <id> --print` gives the restart command to hand the user. Don't run `fu resume` yourself from inside a session, since it replaces the current process.
- When the user returns to a parked item in this session, run `fu touch <id>`; when they finish, `fu done <id>`. This keeps "last worked" honest, which is what makes the board useful for triage.
- **Done items are kept.** `fu done` never deletes; items stay on the board (hidden from `fu ls`, shown with `--all`) until the user explicitly removes them with `fu rm`. Don't delete on the user's behalf unless they ask.
- Tell the user they can run `fu` in a terminal for the TUI: `1` Board (everything, filterable with `f`), `2` Jobs (a folder tree; `→` opens a folder, Enter on a job or session shows its tasks in the Board, Enter on a task resumes it), and `h` for help.

## Other commands

`fu edit <id> [--summary --why --status --job NAME|none --kind --agent --session-id --cwd --note]`, `fu reopen <id>`, `fu rm <id> -y`, `fu job add|edit|rm`, `fu path` (shows where data and config live). Statuses are `todo`, `doing`, `done`. Deleting a job keeps its tasks and just unassigns them.

## Where things live

- Data: `~/development/follow-ups/board.json` (source of truth, holds both tasks and jobs) and `BOARD.md` (generated, readable anywhere).
- Config: `~/.config/jq-tools/follow-ups/config.toml` (`data_dir`). All the user's own tools keep config under `~/.config/jq-tools/`.
- Set `FU_DATA_DIR` to point a command at a different board, e.g. when testing. When testing the TUI in tmux, pass it on the tmux command line itself (`tmux new-session "env FU_DATA_DIR=... fu"`); exported variables are not inherited by an existing tmux server and the test will hit the real board.
