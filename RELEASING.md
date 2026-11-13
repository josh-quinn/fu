# Releasing

Releases are cut from tags `vX.Y.Z` on `main`. The `release` workflow tests, builds the
sdist and wheel, writes checksums and an SBOM, signs a build-provenance attestation, and
adds SLSA provenance to the GitHub Release.

## One-time setup (owner)

1. Create the public repositories `josh-quinn/fu` and `josh-quinn/homebrew-tap`.
2. In `fu`: apply the branch ruleset for `main` (PR required, required checks, no force
   push), enable private vulnerability reporting, secret scanning with push protection and
   Dependabot alerts. The exact commands were reviewed before being run.
3. Optional: register the project at <https://www.bestpractices.dev> (needs your login).

## Per release

1. Open a `docs(changelog)` PR: move `Unreleased` entries under the new version heading and
   bump `version` in `pyproject.toml` (the workflow refuses a tag that does not match).
2. After it merges: `git switch main && git pull && git tag -s vX.Y.Z -m "vX.Y.Z" && git push origin vX.Y.Z`.
3. Wait for the `release` workflow. Check the Release has `fu_board-X.Y.Z.tar.gz`, the wheel,
   `SHA256SUMS`, the SBOM and `multiple.intoto.jsonl`.
4. Verify it (below).
5. Update the tap: copy `packaging/homebrew/fu.rb.template` to `Formula/fu.rb` in
   `homebrew-tap`, replace `VERSION` and set `sha256` to the sdist's checksum from `SHA256SUMS`,
   run `brew update-python-resources josh-quinn/tap/fu`, then `brew install --build-from-source
   josh-quinn/tap/fu && brew test josh-quinn/tap/fu && brew audit --strict --new josh-quinn/tap/fu`,
   and push.

## Verifying a release

```sh
gh attestation verify fu_board-X.Y.Z.tar.gz --repo josh-quinn/fu
slsa-verifier verify-artifact fu_board-X.Y.Z.tar.gz --provenance-path multiple.intoto.jsonl \
  --source-uri github.com/josh-quinn/fu --source-tag vX.Y.Z
sha256sum --check --ignore-missing SHA256SUMS
```

## When a release breaks

Never move or reuse a published tag. Fix forward with the next patch release. Delete the broken
GitHub Release (keep the tag) so every release on the page is complete and signed.

## Lessons carried over

- Test the formula by installing it (`brew install --build-from-source`) and running `brew test`;
  `brew audit` alone does not catch a broken virtualenv.
- The SLSA generator is referenced by tag on purpose (`docs/adr/0006`).
