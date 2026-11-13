# 0002. Package fu as a Python package built with hatchling and managed with uv

- **Status**: Accepted
- **Date**: 2026-11-13

## Context

fu began as one 1,200-line `uv run --script` file. A public tool installed through Homebrew needs reproducible installs, tests that import its modules, and a build that produces a signed sdist and wheel.

## Decision

We will ship `fu` as a normal Python package (`src/fu/`: `core`, `cli`, `tui`) with a `pyproject.toml`, a `fu` console script, hatchling as the build backend (pinned) and `uv` for development, with `uv.lock` committed. Textual is imported lazily so plain CLI calls stay fast.

## Consequences

Installs are hermetic: the Homebrew formula installs pinned dependencies into its own virtualenv instead of fetching Textual on first run. Modules can be unit tested. We must keep `uv.lock` and Dependabot current.

## Alternatives considered

- **Keep the single-file uv script**: simplest, but downloads dependencies at first run and cannot be tested or built reproducibly.
- **Go or Rust rewrite**: faster start-up, but a rewrite for no user-visible gain.
