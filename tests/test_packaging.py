"""The Homebrew formula generator (scripts/brew-formula.py) keeps working as dependencies change."""

import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "brew-formula.py"


def test_the_formula_has_the_release_and_a_resource_per_runtime_dependency():
    out = subprocess.run(
        [sys.executable, str(SCRIPT), "9.9.9", "ab" * 32], capture_output=True, text=True, check=True
    ).stdout
    assert 'url "https://github.com/josh-quinn/fu/releases/download/v9.9.9/fu_board-9.9.9.tar.gz"' in out
    assert f'sha256 "{"ab" * 32}"' in out
    for dep in ("textual", "pyyaml", "rich", "linkify-it-py"):
        assert f'resource "{dep}" do' in out
    assert "Resource blocks" not in out and "VERSION" not in out and not out.startswith("# Template")
    assert "\n\n\n" not in out  # brew audit rejects extra blank lines
