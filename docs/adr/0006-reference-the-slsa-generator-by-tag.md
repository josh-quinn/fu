# 0006. Reference the SLSA generator by tag, everything else by SHA

- **Status**: Accepted
- **Date**: 2026-11-13

## Context

Our policy pins every third-party GitHub Action to a full commit SHA, because tags can be moved.
The one exception is `slsa-framework/slsa-github-generator`: `slsa-verifier` validates the
builder's identity against its release tag, so a SHA reference makes verification fail.

## Decision

We will reference `generator_generic_slsa3.yml` as `@v2.1.0` in `release.yml` and pin every
other action by SHA. `.github/zizmor.yml` encodes the exception so CI stays green and the
exception stays visible. Dependabot still proposes generator updates.

## Consequences

OpenSSF Scorecard's Pinned-Dependencies check deducts one point for this reference. Users
get verifiable SLSA Level 3 provenance (`slsa-verifier`, documented in the README).
Tags in that repository are protected and the generator is a reusable workflow run by
GitHub, which limits the risk of a moved tag.

## Alternatives considered

- **Pin by SHA**: breaks `slsa-verifier`.
- **Skip SLSA provenance and rely on `actions/attest-build-provenance`**: simpler, but
  Scorecard's Signed-Releases check reads `*.intoto.jsonl` release assets, and SLSA L3
  is the target for release integrity.
