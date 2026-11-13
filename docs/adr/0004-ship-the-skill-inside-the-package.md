# 0004. Ship the agent skill inside the package and install it with fu skill install

- **Status**: Accepted
- **Date**: 2026-11-13

## Context

The follow-ups skill must stay in step with the CLI it drives. Skills are loaded from `~/.claude/skills` and `~/.copilot/skills`, which are install locations, not places for source code. Homebrew cannot write into a user's home directory.

## Decision

We will keep the skill at `src/fu/skills/follow-ups/` in this repository and package it as data. `fu skill install` symlinks (or with `--copy` copies) it into the agents' skill folders. Its evals live beside it and are excluded from the wheel.

## Consequences

One repository and one version for tool and skill. Users run one extra command after `brew install`. A symlink target moves when Homebrew upgrades; re-running `fu skill install` repairs it.

## Alternatives considered

- **Skill folder as the repository**: mixes source with an install location and is overwritten by tooling.
- **Separate skill repository**: the skill and CLI would drift apart.
- **Claude Code plugin marketplace**: Claude-only; may be added later alongside this.
