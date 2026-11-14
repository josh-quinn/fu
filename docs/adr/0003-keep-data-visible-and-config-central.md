# 0003. Keep board data in a visible folder and config under ~/.config/jq-tools

- **Status**: Accepted (config format superseded by [0008](0008-configure-in-yaml-with-project-overrides.md))
- **Date**: 2026-11-13

## Context

The owner wants their own tools' configuration in one findable place, and wants parked work to be readable without the tool.

## Decision

We will store the board in `board.json` (plus a generated `BOARD.md`) under a data folder that defaults to `~/development/follow-ups`, and keep configuration in `~/.config/jq-tools/follow-ups/config.toml`. `FU_DATA_DIR` and `JQ_TOOLS_CONFIG` override both, so tests never touch real data. Writes are atomic (temp file then rename). Done items are never deleted automatically.

## Consequences

The board is human-readable and easy to back up or sync. A plain JSON file is not safe for several simultaneous writers beyond atomic replacement; that is acceptable for one person's board. The data format must stay backwards compatible (boards written before jobs existed still load).

## Alternatives considered

- **SQLite**: safer for concurrent writers, but opaque and harder for agents and humans to read.
- **XDG data directory**: more conventional, but the owner wants the data under `~/development`.
