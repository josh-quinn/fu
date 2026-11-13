# 0005. Distribute through a Homebrew tap built from the release sdist

- **Status**: Accepted
- **Date**: 2026-11-13

## Context

Homebrew-core has notability requirements a new personal tool does not meet. Taps must be separate repositories named `homebrew-<name>`.

## Decision

We will publish a formula `fu` in a public `josh-quinn/homebrew-tap` repository. It installs the signed release sdist into a virtualenv with pinned resources and prints a caveat to run `fu skill install`. The formula is updated by the maintainer after each release.

## Consequences

`brew install josh-quinn/tap/fu` works on macOS and Linux. A second repository must be kept in sync, and the formula's resource list is regenerated each release with `brew update-python-resources`.

## Alternatives considered

- **PyPI only (pipx / uv tool install)**: fine for Python users, but the owner wants a brew install.
- **Standalone binaries (PyInstaller)**: heavier, and macOS needs notarisation to avoid Gatekeeper prompts.
