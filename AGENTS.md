# fu: instructions for AI coding agents

The rules for every change:

1. **Small, green, Conventional Commits.** One purpose per commit, `type(scope): subject`,
   tests in the same commit, `make check` passes at every commit.
2. **Test first**, including a regression test for every bug and security fix. TUI behaviour is
   tested headlessly with Textual's pilot (`tests/test_tui.py`).
3. **ADRs** in `docs/adr/` for hard-to-reverse decisions, in the same commit; keep the index
   current; supersede, never rewrite.
4. **No secrets in history.** Run `make hooks` once per clone; never use `--no-verify`.
5. **Scope and dependencies**: `fu` is a small local CLI/TUI. No network access, no telemetry.
   One runtime dependency (Textual); justify any other.
6. **Never touch the real board** while testing: use `FU_DATA_DIR`. In tmux, pass it on the
   tmux command line.
7. Ask the owner before outward-facing actions (releases, tags, repo settings, publishing).

Commands: `make test`, `make check` (everything CI runs for code quality), `make build`,
`make hooks`. Config for the owner's tools lives under `~/.config/jq-tools/<tool>/`.
