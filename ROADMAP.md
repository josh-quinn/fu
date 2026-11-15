# Roadmap

What `fu` intends to do, and not do, over the next year (to November 2027). It changes as the
maintainer's work changes; each change goes through a pull request. The test for any feature
is the one in [ADR 0007](docs/adr/0007-model-work-as-follow-ups-jobs-and-outputs.md): does it
make parking faster or surer, make what is parked easier to find, or make resuming easier?

## Planned

- **Live end-to-end checks of starting sessions** from the board with Claude Code and Copilot
  CLI, which so far have been tested with a stand-in agent
  ([session handoff limits](docs/design/session-handoff.md#limits)).
- **Better output detection**: fewer missed or spurious documents when finding what a
  session produced.
- **Smoother upgrades**: keep old boards and configs loading across releases, with any
  conversion done once and announced, as the TOML-to-YAML move was.
- **Linux support checked in practice**, not only in CI.
- **Accessibility**: make every TUI action reachable without colour cues and check the board
  with a terminal screen reader.

## Not planned

- A second issue tracker: Jira (or similar) stays the system of record for work; jobs only
  mirror it.
- Syncing boards between machines or people, accounts, or any server component.
- Support for agents other than Claude Code and Copilot CLI unless one is in daily use.
- Translations: the interface stays English-only.
