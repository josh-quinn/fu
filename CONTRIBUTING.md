# Contributing

Security problems: report them privately as described in [SECURITY.md](SECURITY.md).

## Ground rules

- **Test first.** Add a failing test, then the code. Every bug fix gets a regression test.
- **Small, single-purpose commits** written as [Conventional Commits](https://www.conventionalcommits.org/)
  (`feat(tui): ...`, `fix(core): ...`). A `commit-msg` hook and CI enforce this.
- **Decisions** that are hard to reverse get an ADR in [`docs/adr/`](docs/adr) in the same PR.
- **Sign off every commit** (`git commit -s`) to certify the
  [Developer Certificate of Origin](https://developercertificate.org/): you wrote the change or
  have the right to submit it under the project's licence. `make hooks` adds the sign-off for
  you, and CI rejects a pull request with an unsigned-off commit.

## Dependencies

`fu` keeps runtime dependencies few on purpose (Textual for the TUI, PyYAML for the config).

- **Choosing one**: prefer the standard library. A new dependency needs a reason in the PR,
  an OSI-approved licence, an active upstream, and no known vulnerabilities.
- **Tracking**: they are declared in `pyproject.toml` and pinned, with hashes, in `uv.lock`,
  which is committed. Change them only with `uv add` / `uv lock`, never by hand.
- **Updating**: Dependabot proposes updates for Python packages and GitHub Actions weekly,
  after a 7-day cooldown. OSV-Scanner and dependency review fail a PR that brings in a known
  vulnerability; Dependabot alerts cover what is already in `main`.
- GitHub Actions are pinned to full commit SHAs (except the SLSA generator, see ADR 0006).

## Getting started

```sh
brew install uv gitleaks shellcheck
make hooks    # once per clone: commit messages checked, pushes scanned for secrets
make check    # everything CI runs for code quality
```

## Building from source

```sh
git clone https://github.com/josh-quinn/fu && cd fu
uv sync               # create .venv with the locked dependencies
uv run fu --version   # run from source
uv build              # sdist and wheel in dist/
uv tool install dist/fu_board-*.whl   # optional: install the build as `fu`
```

Needs Python 3.11 or newer and [uv](https://docs.astral.sh/uv/). Releases are built the same
way by the `release` workflow ([RELEASING.md](RELEASING.md)).

## Testing

`make test` runs the suite with coverage; CI runs it on every pull request and push to `main`,
on Linux and macOS. New features and bug fixes come with tests (see Ground rules).

Always test against a throwaway board: set `FU_DATA_DIR` to a temp folder (the test suite
does this for you). When driving the TUI in tmux, put the variable on the tmux command line;
an existing tmux server does not inherit exported variables and the test would hit your real board.

## Pull requests

Open a PR against `main`. The project's roles and how access is granted are in
[GOVERNANCE.md](GOVERNANCE.md). It needs every required check to pass and an approving review from
a code owner ([`.github/CODEOWNERS`](.github/CODEOWNERS)). First-time contributors' CI runs
start after a maintainer approves them.

If the pre-push scan blocks you, remove the secret from **history** (amend or rebase) and
rotate the credential. Record genuine false positives by fingerprint in `.gitleaksignore`.
