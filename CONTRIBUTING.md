# Contributing

Security problems: report them privately as described in [SECURITY.md](SECURITY.md).

## Ground rules

- **Test first.** Add a failing test, then the code. Every bug fix gets a regression test.
- **Small, single-purpose commits** written as [Conventional Commits](https://www.conventionalcommits.org/)
  (`feat(tui): ...`, `fix(core): ...`). A `commit-msg` hook and CI enforce this.
- **Decisions** that are hard to reverse get an ADR in [`docs/adr/`](docs/adr) in the same PR.
- **Dependencies**: justify new ones in the PR; prefer the standard library. `fu` has one
  runtime dependency (Textual) on purpose. `uv.lock` is committed and Dependabot keeps it current.

## Getting started

```sh
brew install uv gitleaks shellcheck
make hooks    # once per clone: commit messages checked, pushes scanned for secrets
make check    # everything CI runs for code quality
```

Always test against a throwaway board: set `FU_DATA_DIR` to a temp folder (the test suite
does this for you). When driving the TUI in tmux, put the variable on the tmux command line;
an existing tmux server does not inherit exported variables and the test would hit your real board.

## Pull requests

Open a PR against `main`. It needs every required check to pass and an approving review from
a code owner ([`.github/CODEOWNERS`](.github/CODEOWNERS)). First-time contributors' CI runs
start after a maintainer approves them.

If the pre-push scan blocks you, remove the secret from **history** (amend or rebase) and
rotate the credential. Record genuine false positives by fingerprint in `.gitleaksignore`.
