# fu

A follow-up board for parked work. When you switch from task A to task B, `fu` keeps task A
from being forgotten: it records what it was, why you started it, when you last touched it,
and the exact command that reopens the Claude Code or Copilot CLI session you were in.

- **Park** a task from the command line, or let your agent do it with the bundled skill.
- **Group** tasks into *jobs* (epic, story, task, bug, spike, idea, misc). One job can span
  several agent sessions, and one session can touch several jobs.
- **Resume** with one key: the board runs the saved `cd <folder> && claude --resume <id>`.
- **Keep** what you finish: done tasks stay on the board until you delete them.

## Install

```sh
brew install josh-quinn/tap/fu
fu skill install        # optional: gives Claude Code and Copilot CLI the follow-ups skill
```

`fu skill install` links the skill into `~/.claude/skills` and `~/.copilot/skills`
(use `--copy` to copy instead, `--target claude|copilot` to pick one).

## Use

```sh
fu add "Fix backprop gradient check" --why "grads disagree at layer 2" --job "Backprop" --kind epic
fu ls                       # open tasks, least recently touched first
fu ls --job backprop --idle 7 --search relu
fu tree                     # jobs > sessions > tasks, and sessions > tasks
fu resume 3                 # restart the saved session (--print just shows the command)
fu done 3                   # kept on the board; `fu ls --all` shows it
fu                          # the interactive board
```

In a Claude Code or Copilot session with the skill installed, just say "park this, I need to
switch to X": the agent runs `fu add` with a summary and a *why* taken from the conversation.

### The board (`fu` with no arguments)

| Key | Action |
|---|---|
| `1` / `2` | Board (everything, filterable) / Jobs (folder tree) |
| `enter` | Resume the highlighted session. On a job or session in the Jobs view: open its tasks in the Board |
| `→` / `←` | Jobs view: open or close a folder, step inside or back out |
| `a` `e` `x` | Add, edit, delete (tasks; jobs in the Jobs view) |
| `s` `d` `t` | Cycle status, mark done, set last worked to today |
| `f` or `/`, `c` | Filter by text, job, status, agent, session, idle days; clear filters |
| `.` | Show or hide done tasks |
| `y` | Copy the restart command |
| `h` | Help for every key |

## Where things live

| What | Where |
|---|---|
| Board data | `~/development/follow-ups/board.json` (plus a generated, readable `BOARD.md`) |
| Config | `~/.config/jq-tools/follow-ups/config.toml` (`data_dir`) |

Set `FU_DATA_DIR` to point any command at a different board.

`fu resume` runs the stored restart command through `/bin/sh`. The command is built from the
agent, session id and folder fields with shell quoting, but treat the board file like a script
you wrote: do not copy in a `board.json` from someone you do not trust.

## Verify a release

Every release archive has a signed build-provenance attestation and an SBOM.

```sh
gh attestation verify fu_board-X.Y.Z.tar.gz --repo josh-quinn/fu
slsa-verifier verify-artifact fu_board-X.Y.Z.tar.gz \
  --provenance-path multiple.intoto.jsonl \
  --source-uri github.com/josh-quinn/fu --source-tag vX.Y.Z
```

## Develop

```sh
git clone https://github.com/josh-quinn/fu && cd fu
make hooks      # Conventional Commits check, secret scan on push (needs gitleaks)
make check      # lint, format check, tests: everything CI runs for code quality
uv run fu       # run from source
```

See [CONTRIBUTING.md](CONTRIBUTING.md), [SECURITY.md](SECURITY.md) and the decisions in
[`docs/adr/`](docs/adr). Licensed under the [MIT License](LICENSE).
