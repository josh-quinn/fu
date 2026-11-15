# Security policy

## Supported versions

| Version | Supported |
|---|---|
| latest release | yes |
| older releases | no, please upgrade |

Only the latest release gets fixes. A release reaches end of life, with no further fixes of
any kind, as soon as the next one is published; the CHANGELOG records each release date.

## Reporting a vulnerability

Please **do not open a public issue**. Report privately through GitHub:
**Security** tab, **Report a vulnerability**
(<https://github.com/josh-quinn/fu/security/advisories/new>).

Include what you did, what happened, the `fu --version`, and your OS.

You will get an acknowledgement within 7 days and an assessment within 14 days. Confirmed
issues are fixed as soon as practical (target: critical within 7 days, high within 30), with
credit to you unless you prefer otherwise, and published as a GitHub security advisory.

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
