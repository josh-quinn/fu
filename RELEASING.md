# Releasing

Releases are cut from tags `vX.Y.Z` on `main`. The `release` workflow tests, builds the
sdist and wheel, writes checksums and an SBOM, signs a build-provenance attestation, and
adds SLSA provenance to the GitHub Release.

## One-time setup (owner)

1. Create the public repositories `josh-quinn/fu` and `josh-quinn/homebrew-tap` (done).
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
5. Update the tap. `brew update-python-resources` only works for PyPI packages, so the formula is
   generated from the template and `uv.lock` instead:
   ```sh
   SHA=$(grep fu_board-X.Y.Z.tar.gz SHA256SUMS | cut -d' ' -f1)
   python3 scripts/brew-formula.py X.Y.Z "$SHA" > ../homebrew-tap/Formula/fu.rb
   brew install --build-from-source josh-quinn/tap/fu && brew test josh-quinn/tap/fu \
     && brew audit --strict josh-quinn/tap/fu
   ```
   Then commit and push the tap. To try a formula before tagging, pass
   `--url file:///path/to/dist/fu_board-X.Y.Z.tar.gz` and install it from a local tap
   (`brew tap-new --no-git you/local`).

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
