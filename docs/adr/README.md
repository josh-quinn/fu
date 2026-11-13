# Architecture decision records

One file per decision, `NNNN-short-title-in-the-imperative.md`, from [template.md](template.md).
Accepted ADRs are never rewritten: a new ADR supersedes them, and the old one's status
becomes "Superseded by NNNN".

| ADR | Decision | Status |
|---|---|---|
| [0001](0001-record-architecture-decisions.md) | Record architecture decisions | Accepted |
| [0002](0002-package-fu-with-hatchling-and-uv.md) | Package fu as a Python package built with hatchling and managed with uv | Accepted |
| [0003](0003-keep-data-visible-and-config-central.md) | Keep board data in a visible folder and config under ~/.config/jq-tools | Accepted |
| [0004](0004-ship-the-skill-inside-the-package.md) | Ship the agent skill inside the package and install it with fu skill install | Accepted |
| [0005](0005-distribute-through-a-homebrew-tap.md) | Distribute through a Homebrew tap built from the release sdist | Accepted |
| [0006](0006-reference-the-slsa-generator-by-tag.md) | Reference the SLSA generator by tag, everything else by SHA | Accepted |
