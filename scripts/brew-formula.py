"""Print Formula/fu.rb for josh-quinn/homebrew-tap: the template with the release filled in and a
`resource` block for every runtime dependency.

`brew update-python-resources` only works for packages on PyPI, and fu isn't there. uv.lock already
pins every dependency's sdist and its sha256 (the exact set CI tested), so the blocks come from it.

    python3 scripts/brew-formula.py 0.1.0 <sha256 of fu_board-0.1.0.tar.gz> > Formula/fu.rb
    python3 scripts/brew-formula.py 0.1.0 <sha256> --url file:///path/to/sdist   # try it locally first
"""

import argparse
import re
import sys
import tomllib
from pathlib import Path

ROOT = "fu-board"
REPO = Path(__file__).resolve().parent.parent
PLACEHOLDER = re.compile(r"  # Resource blocks for .*?\n  #   python3 scripts/brew-formula.py\n", re.S)


def resources() -> str:
    """One resource block per runtime dependency of fu (extras followed), from uv.lock."""
    lock = tomllib.loads((REPO / "uv.lock").read_text())
    packages = {p["name"]: p for p in lock["package"]}
    found: dict[str, None] = {}
    todo: list[tuple[str, list[str]]] = [(ROOT, [])]
    while todo:
        name, extras = todo.pop()
        pkg = packages[name]
        deps = list(pkg.get("dependencies", []))
        for extra in extras:
            deps += pkg.get("optional-dependencies", {}).get(extra, [])
        for dep in deps:
            if "marker" in dep:
                print(f"# check by hand: {name} needs {dep['name']} only when {dep['marker']}", file=sys.stderr)
            if dep["name"] not in found or dep.get("extra"):
                found.setdefault(dep["name"], None)
                todo.append((dep["name"], dep.get("extra", [])))
    blocks = []
    for name in sorted(found):
        pkg = packages[name]
        sdist = pkg.get("sdist")
        if not sdist:
            sys.exit(f"error: {name} {pkg['version']} has no sdist in uv.lock")
        sha = sdist["hash"].removeprefix("sha256:")
        blocks.append(f'  resource "{name}" do\n    url "{sdist["url"]}"\n    sha256 "{sha}"\n  end')
    return "\n\n".join(blocks) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("version")
    ap.add_argument("sha256")
    ap.add_argument("--url", help="the sdist's URL (default: the GitHub Release asset)")
    a = ap.parse_args()
    url = a.url or f"https://github.com/josh-quinn/fu/releases/download/v{a.version}/fu_board-{a.version}.tar.gz"
    text = (REPO / "packaging" / "homebrew" / "fu.rb.template").read_text()
    text = "\n".join(text.splitlines()[1:]) + "\n"  # drop the template's own comment line
    text = text.replace("https://github.com/josh-quinn/fu/releases/download/vVERSION/fu_board-VERSION.tar.gz", url)
    text = text.replace("SHA256_OF_THE_SDIST", a.sha256)
    text, n = PLACEHOLDER.subn(resources(), text)
    if n != 1:
        sys.exit("error: the template's resource placeholder is missing")
    print(text, end="")
    return 0


if __name__ == "__main__":
    sys.exit(main())
