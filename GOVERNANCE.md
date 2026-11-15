# Governance

## Roles

| Role | Who | Access |
|---|---|---|
| Maintainer | Josh Quinn ([@josh-quinn](https://github.com/josh-quinn)) | Admin on `josh-quinn/fu` and `josh-quinn/homebrew-tap`; owner of the bestpractices.dev entry |
| Contributor | Anyone | Opens issues and pull requests; no write access |

The maintainer decides what is merged and released. Decisions that are hard to reverse are
recorded as ADRs in [`docs/adr/`](docs/adr). The maintainer's GitHub account uses two-factor
authentication.

## Sensitive resources

- **The repositories**: only the maintainer can push, change settings or rulesets, or merge.
  `main` accepts changes only through pull requests that pass the required checks.
- **Releases**: built and signed by GitHub Actions from a tag on `main`. Signing uses
  short-lived GitHub OIDC credentials (Sigstore); there are no long-lived signing keys. See
  [docs/security/secrets-policy.md](docs/security/secrets-policy.md).
- **The Homebrew tap**: updated by the maintainer after each release.

## Giving someone more access

Nobody else has write access today. Before anyone does:

1. They have a record of merged, reviewed contributions over at least three months.
2. Their GitHub account has two-factor authentication.
3. The repository moves to a GitHub organisation first, so their role can start at Triage or
   Read rather than the write access a personal repository grants, and be raised later.
4. The change is announced in an issue and this file is updated in the same pull request.

Access is removed when someone asks, or after twelve months without activity.

## Reviews

The project has one maintainer, so pull requests are merged by their author once every
required check passes. A second person's approval is not possible yet; it will be required
once there is a second maintainer.
