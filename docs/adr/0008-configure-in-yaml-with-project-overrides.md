# 0008. Configure fu in YAML, with project and type overrides

- **Status**: Accepted
- **Date**: 2026-11-14
- **Spec**: docs/reviews/review-3.txt

## Context

ADR 0003 put the config at `~/.config/jq-tools/follow-ups/config.toml` with one setting
(`data_dir`, later `[keys] modifier`). Review 3 asks for much more: job types the user can
extend or replace, a default home folder for jobs, description templates per type, and default
agent settings (agent, model, skills, instructions, MCP servers, extra folders), all set
system-wide and overridable per project (ADR 0007). The owner chose YAML for it.

## Decision

We will read `~/.config/jq-tools/follow-ups/config.yaml` (still under `JQ_TOOLS_CONFIG`).
A `config.toml` from before is converted once to `config.yaml` and kept as
`config.toml.migrated`, and fu says so. The file has system-wide settings at the top and a
`projects:` map keyed by project (the Jira key, e.g. `ML`) whose entries override them:

- `jobs.types` replaces the type list; `jobs.extra_types` adds to it; `jobs.home` is the default
  home folder; `jobs.templates` maps a type to the description a new job starts with.
- `ai.agent` and `ai.model` pick the default agent and model; `ai.skills` and `ai.instructions`
  go into the brief a new session gets; `ai.mcp_config`, `ai.add_dirs` and `ai.allowed_tools`
  become each agent's own flags; `ai.claude.args` and `ai.copilot.args` pass anything else.

Types created in the TUI with "Other…" are saved with the board data, not written into the
config file, so fu never rewrites a file the user edits by hand.

## Consequences

The owner can tailor fu per project without touching code. YAML needs a parser (PyYAML), one
more dependency in the package and in the Homebrew formula's resources. Agent settings differ
between Claude Code and Copilot CLI; fu maps the shared ones and passes the rest through
`args`. Status of ADR 0003: still accepted for where data and config live; its config format
is superseded by this ADR.

## Alternatives considered

- **Keep TOML**: no new dependency, but the owner prefers YAML for nested per-project settings.
- **Per-project config inside each repo**: closer to the code, but splits config across many
  places, against the owner's rule that their tools' config lives in one folder.
