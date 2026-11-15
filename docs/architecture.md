# Architecture

`fu` is a local command-line tool and terminal UI. It has no server and makes no network
calls of its own. Why it is shaped this way is in the ADRs in [`adr/`](adr); this page is the
map.

## Pieces

| Module | Job |
|---|---|
| `cli.py` | The `fu` command: argument parsing and one function per subcommand. With no arguments it starts the TUI. |
| `core.py` | The board model: follow-ups, jobs, sessions; loading and saving `board.json`; writing `BOARD.md`; detecting the current agent session. |
| `config.py` | Reads `~/.config/jq-tools/follow-ups/config.yaml`, with per-project overrides ([ADR 0008](adr/0008-configure-in-yaml-with-project-overrides.md)). Never rewrites it. |
| `launch.py` | Builds the commands that resume a session or start a new one, and the brief a new session gets ([design/session-handoff.md](design/session-handoff.md)). |
| `artifacts.py` | Finds the outputs a session wrote by reading the agent's session transcript, and opens or reveals them. |
| `summary.py` | The text shown in the TUI's side panel for a job or a follow-up. |
| `tui.py` | The Textual app: the Jobs and Follow-ups tables, forms and dialogs. |
| `skills/follow-ups/` | The agent skill, shipped inside the package and linked into `~/.claude/skills` and `~/.copilot/skills` by `fu --install-skill` ([ADR 0004](adr/0004-ship-the-skill-inside-the-package.md)). |

## Data and trust

```
agent session ──fu add──▶ board.json ──▶ BOARD.md (generated)
                              │
              fu / TUI ◀──────┘──▶ resume: /bin/sh -c "cd <dir> && claude --resume <id>"
```

- `board.json` is the source of truth, written atomically (temporary file, then rename).
- Config is YAML loaded with `yaml.safe_load`.
- Agent transcripts under `~/.claude` and `~/.copilot` are read, never written.
- Resuming runs a shell command built from the board's fields with `shlex` quoting. The board
  is trusted local data; see the [threat model](security/threat-model.md).

## External interfaces

- The `fu` command line, documented by `fu --help` and the [README](../README.md#use).
- The files above: `board.json`, `BOARD.md`, `briefs/`, `config.yaml`.
- The programs it starts: `claude`, `copilot`, `git` (to find ignored outputs), and the
  system's file opener.
