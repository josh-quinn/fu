# Secrets policy

## What exists

The project holds **no long-lived secrets**. CI uses:

- `GITHUB_TOKEN`: issued per workflow run, expires when the run ends, read-only by default
  (repository setting) and widened per job only where needed, e.g. `contents: write` for the
  release job.
- GitHub OIDC tokens (`id-token: write`) for Sigstore signing and the SLSA generator: short
  lived, bound to the workflow and the tag that triggered it.

No repository or environment secrets are configured, and no cloud credentials are used.

## Rules

- Never commit a secret. gitleaks runs on pre-push (`make hooks`) and over the full history in
  CI; GitHub secret scanning with push protection is on.
- Prefer OIDC federation over stored credentials for any future integration.
- If a secret is ever added (for example a token to update the Homebrew tap automatically):
  store it as a GitHub Actions secret scoped to a protected environment, give it the smallest
  scope and an expiry of 90 days or less, record it in this file, and rotate it on expiry or
  as soon as anyone with access leaves.
- A leaked secret is revoked first, then removed from history, then reported as in
  [SECURITY.md](../../SECURITY.md).
