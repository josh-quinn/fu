#!/bin/sh
# Check the built wheel before it is released: the skill must ship, its evals must not,
# and a clean install must run.
set -eu

whl=$(ls dist/*.whl)
listing=$(unzip -l "$whl")

printf '%s\n' "$listing" | grep -q 'fu/skills/follow-ups/SKILL.md' || { echo "SKILL.md is missing from $whl" >&2; exit 1; }
if printf '%s\n' "$listing" | grep -q '/evals/'; then echo "skill evals must not ship in $whl" >&2; exit 1; fi

venv=$(mktemp -d)
trap 'rm -rf "$venv"' EXIT
uv venv --quiet "$venv"
uv pip install --quiet --python "$venv/bin/python" "$whl"
"$venv/bin/fu" --version
"$venv/bin/fu" skill path
