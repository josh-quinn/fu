# Documentation

## Install, use and use securely

- **Install**: `brew install josh-quinn/tap/fu`, then `fu --install-skill` to give Claude Code
  and Copilot CLI the follow-ups skill. See [Install](../README.md#install).
- **Use**: park ideas from a session, list them with `fu ls`, resume with `fu resume`, or run
  `fu` for the interactive board. See [Use](../README.md#use) and `fu --help`.
- **Use securely**: `fu resume` runs the stored restart command through `/bin/sh`, so treat
  `board.json` like a script you wrote and never copy in one from someone you do not trust.
  Check a release before installing it by hand ([Verify a release](../README.md#verify-a-release)).
  Report vulnerabilities privately as described in [SECURITY.md](../SECURITY.md).

## Design

- [`adr/`](adr): architecture decision records, why fu is built the way it is.
- [`design/session-handoff.md`](design/session-handoff.md): what a new session started from
  the board is told about its job.
- [`reviews/`](reviews): the owner's review notes that drove each round of changes.
