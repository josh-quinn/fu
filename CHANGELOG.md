# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses
[Semantic Versioning](https://semver.org/).

## [Unreleased]

## [0.1.1] - 2026-11-15

### Security
- `--session-id` only accepts letters, digits, `.`, `_` and `-`, and a stored id is never used
  as a glob or a path when it doesn't match, so an id can't reach another session's files.

### Fixed
- `fu add` records the folder the agent session started in, not the shell's current folder, so
  the restart command works when the agent's shell has moved (Claude Code resumes a session
  only from its own folder).
- An agent's own files (memory, rules, transcripts, settings under `~/.claude` and `~/.copilot`)
  are no longer listed as outputs; skills there still are.
- `--help` and the skill use "follow-up" consistently; the skill names `fu --install-skill`,
  `fu sessions` and `job add --desc`.
- A save that fails part way no longer leaves a stray `.tmp` file in the data folder.

### Changed
- Releases are checked to build bit for bit the same in CI; commits need a DCO sign-off.

## [0.1.0] - 2026-11-15

### Added
- Follow-ups: park an idea or unfinished work with `fu add` (summary, why, the session to
  resume); mid-session it lands on the job that session is on, `--no-job` keeps it loose.
- Jobs (epic, story, bug, spike, task, or your own types), usually mirroring a Jira issue, with
  parents, a project from the Jira key, and a home folder: `fu job add|edit|rm|ls`, `fu tree`.
- Outputs: documents, skills and repos detected from what sessions wrote (including documents
  in gitignored folders), added or removed by hand.
- Interactive board: Jobs and Follow-ups screens with sorting, column search, a summary panel,
  promote a follow-up to a job, and help (`h`).
- Sessions run inside the board: resume one, or start a new one with a written brief of the
  job (`docs/design/session-handoff.md`).
- YAML config with per-project overrides for job types, templates and agent settings.
- `fu --install-skill` (or `fu skill install`) links the bundled follow-ups skill into Claude
  Code and Copilot CLI.

[Unreleased]: https://github.com/josh-quinn/fu/compare/v0.1.1...HEAD
[0.1.1]: https://github.com/josh-quinn/fu/compare/v0.1.0...v0.1.1
[0.1.0]: https://github.com/josh-quinn/fu/releases/tag/v0.1.0
