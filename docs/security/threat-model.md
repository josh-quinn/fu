# Threat model and security assessment

Reviewed for every minor release (0.x.0) and whenever a change adds an input, an output or a
program `fu` starts. Last reviewed: 0.1.0, 2026-11-15.

## What fu is

A single-user tool that runs on the user's own machine with the user's own permissions. It
reads and writes local files and starts programs the user already runs (`claude`, `copilot`,
`git`). It has no server, no network code, no accounts and no cryptography.

## Assets

1. **The user's account**: anything `fu` runs, runs as the user.
2. **Board data**: `board.json`, `BOARD.md` and `briefs/`. Ideas and notes, possibly
   sensitive work context.
3. **Agent session transcripts** under `~/.claude` and `~/.copilot`. Read only.
4. **Releases**: the sdist, wheel and Homebrew formula users install.

## Trust boundaries and threats (STRIDE)

| Boundary | Threat | Mitigation |
|---|---|---|
| Board fields → shell (`fu resume`, TUI resume) | **Tampering / elevation**: a crafted session id or folder runs extra commands | Commands are built with `shlex.quote`/`shlex.join`; the board is documented as trusted data ("treat it like a script you wrote") in the README and SECURITY.md |
| Text an agent writes into the board → the brief for a later session | **Tampering**: prompt injection carried from one session to the next | The brief is labelled as background, not instructions, and the user's prompt is sent separately ([session handoff](../design/session-handoff.md)) |
| Config file → fu | **Tampering**: arbitrary object construction from YAML | `yaml.safe_load` only; a file that does not parse is ignored with a message |
| Transcripts → fu | **Information disclosure**: secrets in transcripts copied elsewhere | `fu` stores only paths and short labels, never transcript contents |
| Paths from transcripts → file opener | **Tampering**: argument injection into `open`/`xdg-open` | Paths are passed as a single argument list item, never through a shell |
| Source → release | **Tampering / spoofing**: a modified or impersonated release | Tag-driven builds on GitHub Actions; Sigstore build-provenance attestation, SLSA provenance, SHA-256 checksums and an SBOM; the tap pins the checksum. Verification is in the README |
| Dependencies → release | **Tampering**: a malicious or vulnerable dependency | Few runtime dependencies (Textual and PyYAML); `uv.lock` pinned with hashes; Dependabot with a 7-day cooldown; OSV-Scanner and dependency review block known vulnerabilities on every PR |
| Contributors → `main` | **Tampering**: a malicious change | PRs only, required checks (tests, CodeQL, ruff security rules, gitleaks, zizmor), code-owner merge; fork PRs get a read-only token, and first-time contributors need approval before their CI runs |
| Writes to the data folder | **Denial of service / repudiation**: a crash mid-write corrupts the board | Atomic writes (temporary file, then rename) |

## Accepted risks

- Anyone who can already write to the user's home folder can change `board.json` and so what
  `fu resume` runs. That attacker already controls the account; out of scope.
- One maintainer: no second-person review (see [GOVERNANCE.md](../../GOVERNANCE.md)).
- The SLSA generator is referenced by tag, not commit SHA ([ADR 0006](../adr/0006-reference-the-slsa-generator-by-tag.md)).
