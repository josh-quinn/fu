# Security policy

## Supported versions

| Version | Supported |
|---|---|
| latest release | yes |
| older releases | no, please upgrade |

## Reporting a vulnerability

Please **do not open a public issue**. Report privately through GitHub:
**Security** tab, **Report a vulnerability**
(<https://github.com/josh-quinn/fu/security/advisories/new>).

Include what you did, what happened, the `fu --version`, and your OS.

You will get an acknowledgement within 7 days and an assessment within 14 days. Confirmed
issues are fixed as soon as practical (target: critical within 7 days, high within 30), with
credit to you unless you prefer otherwise, and published as a GitHub security advisory.

## Scope

In scope: how `fu` reads and writes the board and config files, how it builds and runs the
restart command (`fu resume`), the packaged skill and `fu skill install`, and the release
pipeline (a tampered or unsigned release artifact).

Out of scope: anything that requires an attacker to already control your account or your
`board.json` (it is local, trusted data; see the note in the README), social engineering, and
issues in third-party dependencies that are not reachable through `fu`.

## Verifying releases

See "Verify a release" in the [README](README.md) and [RELEASING.md](RELEASING.md).
