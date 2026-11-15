# Assurance case: threat model and security assessment

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
| Transcripts → fu | **Information disclosure**: secrets in transcripts copied elsewhere | `fu` keeps only paths and session titles, never the conversation |
| Paths from transcripts → file opener | **Tampering**: argument injection into `open`/`xdg-open` | Paths are passed as a single argument list item, never through a shell |
| Source → release | **Tampering / spoofing**: a modified or impersonated release | Tag-driven builds on GitHub Actions; Sigstore build-provenance attestation, SLSA provenance, SHA-256 checksums and an SBOM; the tap pins the checksum. Verification is in the README |
| Dependencies → release | **Tampering**: a malicious or vulnerable dependency | Few runtime dependencies (Textual and PyYAML); `uv.lock` pinned with hashes; Dependabot with a 7-day cooldown; OSV-Scanner and dependency review block known vulnerabilities on every PR |
| Contributors → `main` | **Tampering**: a malicious change | PRs only, required checks (tests, CodeQL, ruff security rules, gitleaks, zizmor), code-owner merge; fork PRs get a read-only token, and first-time contributors need approval before their CI runs |
| Writes to the data folder | **Denial of service / repudiation**: a crash mid-write corrupts the board | Atomic writes (temporary file, then rename) |

## Security requirements

What users can and cannot expect is listed in
[SECURITY.md, "What you can expect"](../../SECURITY.md#what-you-can-expect). The rest of this
page argues that those claims hold.

## Secure design principles applied

| Principle (Saltzer and Schroeder) | How fu applies it |
|---|---|
| Economy of mechanism | A small CLI with a JSON file; no server, daemon, database or network code |
| Fail-safe defaults | Unknown config values fall back to defaults; a config that does not parse is ignored; invalid session ids are refused |
| Complete mediation | Every command that starts a program goes through one builder (`launch.py`/`core.resume_cmd`) that quotes each field |
| Open design | Source, threat model and release process are public; nothing relies on secrecy |
| Separation of privilege | Releases need a merged PR with passing checks and a tag; signing uses short-lived OIDC credentials, never a stored key |
| Least privilege | Runs as the user with no elevation; CI tokens are read-only by default and widened per job |
| Least common mechanism | Board, config and agent transcripts are separate files; transcripts are only read |
| Psychological acceptability | Parking an idea asks no questions, so users have no reason to work around the tool |

## Common weaknesses countered

| Weakness | Where it could arise | Countermeasure | Checked by |
|---|---|---|---|
| CWE-78 OS command injection | Resume and start commands | `shlex.quote`/`shlex.join` on every field; programs other than the agent get argument lists, no shell | `test_a_hostile_folder_or_session_stays_one_argument`; ruff `S` rules; CodeQL |
| CWE-22 path traversal, CWE-155 wildcard injection | Session ids used in file names and glob patterns | Allowlist `[A-Za-z0-9._-]`, no `..`; refused ids are never used as paths | `test_a_session_id_is_never_a_glob_or_a_path`, `test_a_session_id_outside_the_allowlist_is_rejected` |
| CWE-502 unsafe deserialization | Config and board | `yaml.safe_load`; `json` only | ruff `S506`; CodeQL |
| CWE-367 / CWE-362 races on write | Saving the board | Write to a temporary file in the same folder, then `os.replace`; the temporary file is removed if the write fails | `test_a_failed_save_leaves_the_old_board_whole_and_no_temp_file` |
| CWE-798 hard-coded credentials, CWE-312 cleartext secrets | Repository and CI | No credentials exist; gitleaks and push protection | CI `secrets` job |
| CWE-1104 unmaintained third-party components | Dependencies | Few dependencies, locked with hashes, Dependabot, OSV-Scanner | CI `dependencies` job; dependency review |
| CWE-494 download without integrity check | Installing releases | Checksums in the formula; signed attestations; reproducible builds | `gh attestation verify`; CI rebuild comparison |
| Memory-safety weaknesses (CWE-119 family) | n/a | Written in Python, a memory-safe language | |

## Accepted risks

- Anyone who can already write to the user's home folder can change `board.json` and so what
  `fu resume` runs. That attacker already controls the account; out of scope.
- One maintainer: no second-person review (see [GOVERNANCE.md](../../GOVERNANCE.md)).
- The SLSA generator is referenced by tag, not commit SHA ([ADR 0006](../adr/0006-reference-the-slsa-generator-by-tag.md)).
