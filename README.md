# fu

A follow-up board for the ideas and loose ends that come up while you work with Claude Code or
Copilot CLI. Mid-session you have an idea, or have to switch away from something half-done: `fu`
parks it in seconds, files it under the job you're on, and remembers the session it came from so
you can reopen it exactly where you were.

- **Follow-ups** are parked ideas and unfinished work: a one-line summary, why it came up, and
  the session to resume. Your agent writes them for you with the bundled skill.
- **Jobs** are the pieces of work those ideas belong to, usually a Jira epic, story, bug or
  spike. A job gathers its follow-ups, the sessions that worked on it, and its outputs.
- **Outputs** are the documents, skills and repos a job's sessions produce (runbooks,
  explainers, cheatsheets, even the ones in a gitignored `.temp/`), found from what the
  sessions wrote so they stop getting lost.
- **Resume** a session with one key, or start a new one that gets a brief of the job: its
  open follow-ups, earlier sessions and outputs.

Why it is built this way: [docs/adr/0007](docs/adr/0007-model-work-as-follow-ups-jobs-and-outputs.md).

## Install

```sh
brew install josh-quinn/tap/fu
fu --install-skill      # give Claude Code and Copilot CLI the follow-ups skill
```

`fu --install-skill` (or `fu skill install`) links the skill into `~/.claude/skills` and
`~/.copilot/skills`. Homebrew can't do this step itself: it only writes inside its own prefix.
Run it once; the link follows `brew upgrade`.

## Use

In a Claude Code or Copilot session, just say "idea: … park it" or "park this, I need to
switch to X". The agent runs `fu add` with a summary and a *why* from the conversation, and
`fu` files it under the job that session is on (`--no-job` if it's unrelated).

```sh
fu job add "Backprop from scratch" --id ML-12 --kind epic --home ~/code/backprop
fu add "Cache activations between passes" --why "forward pass recomputes them"
fu ls                       # open follow-ups, least recently touched first
fu ls --job ML-12 --idle 7 --search relu
fu resume 3                 # reopen the session it came from (--print just shows the command)
fu done 3                   # kept on the board; `fu ls --all` shows it
fu                          # the interactive board
```

### The board (`fu` with no arguments)

| Key | Action |
|---|---|
| `1` / `2` | Jobs / Follow-ups |
| `↑` from the first row | Onto the column headers: `enter` sorts, typing searches |
| `enter` on a row | Column mode: `← →` pick a column, `enter` shows every row sharing that value |
| `→` / `←` | Into the panel beside the table, and back |
| `shift+R` | Resume a session, or start a new one for a job with a brief |
| `shift+P` | Promote a follow-up to a job of its own |
| `ctrl+o` | Back to where you jumped from |
| `a` `e` `x` | Add, edit, delete |
| `s` `d` `t` `y` | Cycle status, mark done, worked today, copy the restart command |
| `h` | Help for every key |

## Where things live

| What | Where |
|---|---|
| Board data | `~/development/follow-ups/board.json` (plus a readable `BOARD.md`, and `briefs/` for new sessions) |
| Config | `~/.config/jq-tools/follow-ups/config.yaml`: data folder, job types and templates, default agent settings, per-project overrides |

Set `FU_DATA_DIR` to point any command at a different board.

`fu resume` runs the stored restart command through `/bin/sh`. The command is built from the
agent, session id and folder fields with shell quoting, but treat the board file like a script
you wrote: do not copy in a `board.json` from someone you do not trust.

## Verify a release

Every release archive has a signed build-provenance attestation and an SBOM. The commands
below check both that the file is intact and that it was built by this repository's
`release` workflow from the matching tag, the only identity that signs releases.

```sh
gh attestation verify fu_board-X.Y.Z.tar.gz --repo josh-quinn/fu \
  --signer-workflow josh-quinn/fu/.github/workflows/release.yml
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

See [CONTRIBUTING.md](CONTRIBUTING.md), [SECURITY.md](SECURITY.md),
[GOVERNANCE.md](GOVERNANCE.md), the [architecture](docs/architecture.md) and the decisions in
[`docs/adr/`](docs/adr).

## Repositories

- [josh-quinn/fu](https://github.com/josh-quinn/fu): the source (this repository).
- [josh-quinn/homebrew-tap](https://github.com/josh-quinn/homebrew-tap): the Homebrew formula,
  generated from this repository at each release. Licensed under the [MIT License](LICENSE).
