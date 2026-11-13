"""Artifacts: the deliverables a session leaves behind (runbooks, explainers, skills, repos).

Not every file a session wrote counts. Documents do, a skill folder is one entry, and code inside a
git repo collapses to that repo; scratch folders, caches and lockfiles are ignored. Detection reads
what the agent recorded: Claude Code's transcript, Copilot's events and its per-session folders.
"""

import json
import re
from pathlib import Path

from fu import core

DOC_SUFFIXES = {".md", ".markdown", ".html", ".htm", ".pdf", ".docx", ".pptx", ".xlsx", ".ipynb", ".txt", ".rst"}
# path fragments to skip (nothing is read or written there), so the temp-dir lint rule does not apply
SCRATCH = ("/scratchpad/", "/tmp/", "/private/tmp/", "/var/folders/", "/node_modules/", "/.git/")  # noqa: S108
CACHE_PARTS = {"__pycache__", ".venv", "node_modules", ".pytest_cache", ".ruff_cache", ".mypy_cache"}
LOCKFILES = {"uv.lock", "package-lock.json", "yarn.lock", "poetry.lock", "Cargo.lock", "pnpm-lock.yaml"}
SKILL_DIRS = (".claude/skills", ".copilot/skills")
CLAUDE_WRITERS = {"Write": "file_path", "Edit": "file_path", "MultiEdit": "file_path", "NotebookEdit": "notebook_path"}
COPILOT_WRITERS = {"create", "edit", "write_file", "str_replace_editor", "insert", "str_replace"}
PATCH_FILE = re.compile(r"^\*\*\* (?:Add|Update) File: (.+)$", re.MULTILINE)

_cache: dict[tuple, list[str]] = {}


# ----------------------------------------------------------------- reading


def claude_root() -> Path:
    return Path("~/.claude/projects").expanduser()


def claude_transcript(session_id: str) -> Path | None:
    return next(iter(claude_root().glob(f"*/{session_id}.jsonl")), None)


def _written_by_claude(path: Path) -> list[str]:
    out = []
    for line in path.read_text(errors="replace").splitlines():
        if '"tool_use"' not in line:
            continue
        try:
            blocks = (json.loads(line).get("message") or {}).get("content")
        except ValueError:
            continue
        for b in blocks if isinstance(blocks, list) else []:
            key = CLAUDE_WRITERS.get(b.get("name")) if b.get("type") == "tool_use" else None
            if key and isinstance((b.get("input") or {}).get(key), str):
                out.append(b["input"][key])
    return out


def _written_by_copilot(session_dir: Path) -> list[str]:
    out = []
    events = session_dir / "events.jsonl"
    if events.exists():
        for line in events.read_text(errors="replace").splitlines():
            if '"tool.execution_start"' not in line:
                continue
            try:
                data = json.loads(line)["data"]
            except (ValueError, KeyError):
                continue
            args = data.get("arguments")
            if data.get("toolName") == "apply_patch" and isinstance(args, str):
                out += PATCH_FILE.findall(args)
            elif data.get("toolName") in COPILOT_WRITERS and isinstance(args, dict):
                out += [args[k] for k in ("path", "filePath", "file_path") if isinstance(args.get(k), str)]
    # Files the session saved on purpose, in its own folders, are deliverables.
    for sub in ("files", "research"):
        out += [str(p) for p in sorted((session_dir / sub).glob("**/*")) if p.is_file()]
    return out


def written_paths(agent: str | None, session_id: str | None) -> list[str]:
    """Absolute paths the session wrote, first write first, no repeats. Empty when unknowable."""
    if not (agent and session_id):
        return []
    if agent == "claude":
        src = claude_transcript(session_id)
        reader = _written_by_claude
    else:
        src = core.COPILOT_SESSIONS / session_id
        reader = _written_by_copilot
    if not src or not src.exists():
        return []
    stamp = (str(src), src.stat().st_mtime_ns, src.stat().st_size if src.is_file() else 0)
    if stamp not in _cache:
        _cache[stamp] = list(dict.fromkeys(str(Path(p).expanduser()) for p in reader(src)))
    return _cache[stamp]


def session_title(agent: str | None, session_id: str | None) -> str:
    """The name the agent gave the session ('' when it has none)."""
    if agent == "claude" and session_id and (src := claude_transcript(session_id)):
        title = ""
        for line in src.read_text(errors="replace").splitlines():
            if '"ai-title"' in line:
                try:
                    title = json.loads(line).get("aiTitle") or title
                except ValueError:
                    continue
        return title
    if agent == "copilot" and session_id:
        ws = core.COPILOT_SESSIONS / session_id / "workspace.yaml"
        m = re.search(r"^name: (.+)$", ws.read_text(errors="replace"), re.MULTILINE) if ws.exists() else None
        return m.group(1).strip().strip("'\"") if m else ""
    return ""


# ------------------------------------------------------------ classifying


def git_root(path: Path) -> Path | None:
    return next((p for p in path.parents if (p / ".git").exists()), None)


def skill_dir(path: Path) -> Path | None:
    parts = path.parts
    for root in SKILL_DIRS:
        want = tuple(root.split("/"))
        for i in range(len(parts) - len(want) - 1):
            if parts[i : i + len(want)] == want:
                return Path(*parts[: i + len(want) + 1])
    return None


def classify(paths: list[str]) -> list[dict]:
    """Collapse written paths into artifacts: {"path", "kind": doc|skill|repo|file, "label"}."""
    found: dict[str, dict] = {}
    for raw in paths:
        p = Path(raw)
        if (
            any(s in str(p) + "/" for s in SCRATCH)
            or CACHE_PARTS & set(p.parts)
            or p.name in LOCKFILES
            or not p.exists()
        ):
            continue
        if skill := skill_dir(p):
            kind, target = "skill", skill
        elif root := git_root(p):
            kind, target = "repo", root
        elif p.suffix.lower() in DOC_SUFFIXES:
            kind, target = "doc", p
        else:
            kind, target = "file", p
        found.setdefault(str(target), {"path": str(target), "kind": kind, "label": target.name})
    return list(found.values())


def detect(agent: str | None, session_id: str | None) -> list[dict]:
    return classify(written_paths(agent, session_id))


# ------------------------------------------------------------ item merging


def item_artifacts(item: dict) -> list[dict]:
    """Detected artifacts (falling back to the saved snapshot when the transcript is gone) plus the
    ones the user added by hand, minus the ones they dismissed. Manual entries win on a clash."""
    dismissed = set(item.get("artifacts_dismissed", []))
    saved = item.get("artifacts", [])
    manual = [a for a in saved if a.get("source") == "manual"]
    live = detect(item.get("agent"), item.get("session_id"))
    auto = live or [a for a in saved if a.get("source") != "manual"]
    out: dict[str, dict] = {}
    for a in auto:
        out[a["path"]] = {**a, "source": "auto"}
    for a in manual:
        out[a["path"]] = a
    return [a for a in out.values() if a["path"] not in dismissed]


def snapshot(item: dict) -> None:
    """Remember what is detected now, so it survives the transcript being cleaned up."""
    manual = [a for a in item.get("artifacts", []) if a.get("source") == "manual"]
    item["artifacts"] = [*manual, *[a for a in item_artifacts(item) if a.get("source") != "manual"]]


def add_manual(item: dict, path: str, label: str | None = None) -> dict:
    p = Path(path).expanduser()
    art = {
        "path": str(p),
        "kind": "repo" if p.is_dir() and (p / ".git").exists() else "doc" if p.is_file() else "file",
        "label": label or p.name or str(p),
        "source": "manual",
    }
    item["artifacts"] = [a for a in item.get("artifacts", []) if a["path"] != art["path"]] + [art]
    item["artifacts_dismissed"] = [d for d in item.get("artifacts_dismissed", []) if d != art["path"]]
    return art


def dismiss(item: dict, path: str) -> None:
    item["artifacts"] = [a for a in item.get("artifacts", []) if a["path"] != path]
    item["artifacts_dismissed"] = sorted({*item.get("artifacts_dismissed", []), path})
