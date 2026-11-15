# Security policy

## Supported versions

| Version | Supported |
|---|---|
| latest release | yes |
| older releases | no, please upgrade |

Only the latest release gets fixes. A release reaches end of life, with no further fixes of
any kind, as soon as the next one is published; the CHANGELOG records each release date.

## What you can expect

`fu` is a local, single-user tool. It is built to meet these security requirements:

- It makes **no network connections** and runs no server; your board never leaves your machine
  unless you copy it.
- It **starts an agent only when you ask** (`fu resume`, or resume or start in the board), with
  the command built from the board's fields with shell quoting. The only other programs it
  runs are `git` (to tell which files are ignored) and your system's file opener when you open
  an output, with arguments passed directly, never through a shell.
- It **reads but never writes** agent transcripts, and keeps only their paths and session
  titles, never the conversation.
- It **never rewrites your config file**; config is parsed with a safe YAML loader.
- Writes to the board are **atomic**, so a crash cannot leave a half-written `board.json`.
- **Releases are signed and reproducible**: you can check who built a release and rebuild it
  bit-for-bit (see the README).

What it does **not** protect against:

- Someone who can already write to your home folder. The board is trusted data: anyone who
  can edit `board.json` can change what `fu resume` runs. Don't import a board from someone
  you don't trust.
- Secrets you put in follow-ups or notes: `board.json` and `BOARD.md` are plain text, readable
  by anything running as you.
- Instructions planted in text that later reaches an agent through a session brief. The brief
  is marked as background, not instructions, but agents can still be misled.

The full argument is in the [assurance case](docs/security/threat-model.md).

## Reporting a vulnerability

Please **do not open a public issue**. Report privately through GitHub:
**Security** tab, **Report a vulnerability**
(<https://github.com/josh-quinn/fu/security/advisories/new>).

Include what you did, what happened, the `fu --version`, and your OS.

## How we respond

1. **Acknowledge** the report within 7 days.
2. **Assess** within 14 days: reproduce it, decide whether it is a vulnerability, rate its
   severity (CVSS), and tell you the outcome.
3. **Fix** confirmed issues in a private fork of the advisory (target: critical within 7
   days, high within 30), with a regression test.
4. **Release** the fix, then **publish** the GitHub Security Advisory with a CVE, crediting
   you by name in the advisory and the CHANGELOG unless you ask to stay anonymous.

## Publishing vulnerabilities

Confirmed vulnerabilities are published as GitHub Security Advisories on this repository
(<https://github.com/josh-quinn/fu/security/advisories>), with a CVE requested through GitHub,
and noted in the CHANGELOG entry of the release that fixes them.

When a scanner reports a vulnerability in a dependency that does not affect `fu` (for
example, the vulnerable function is never called), we publish an OpenVEX statement saying so
in [`docs/security/vex/`](docs/security/vex) instead of shipping an unneeded upgrade, and
record why. None have been needed so far.

## Scope

In scope: how `fu` reads and writes the board and config files, how it builds and runs the
restart command (`fu resume`), the packaged skill and `fu skill install`, and the release
pipeline (a tampered or unsigned release artifact).

Out of scope: anything that requires an attacker to already control your account or your
`board.json` (it is local, trusted data; see the note in the README), social engineering, and
issues in third-party dependencies that are not reachable through `fu`.

## More

- [Threat model and security assessment](docs/security/threat-model.md), reviewed each minor release.
- [Secrets policy](docs/security/secrets-policy.md).

## Verifying releases

See "Verify a release" in the [README](README.md) and [RELEASING.md](RELEASING.md).
