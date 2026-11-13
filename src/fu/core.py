"""Storage, jobs, sessions, filtering and rendering for the follow-up board (no UI)."""

import json
import os
import shlex
import sys
import tempfile
import tomllib
from datetime import date
from pathlib import Path

# All jq-tools configs live under ~/.config/jq-tools/<tool>/ (see ~/.claude/rules).
CONFIG_ROOT = Path(os.environ.get("JQ_TOOLS_CONFIG", "~/.config/jq-tools")).expanduser()
CONFIG_FILE = CONFIG_ROOT / "follow-ups" / "config.toml"
DEFAULT_TOML = """\
# follow-ups (fu) config
# Where board.json and BOARD.md live. FU_DATA_DIR overrides this per command.
data_dir = "~/development/follow-ups"
"""
STATUSES = ("todo", "doing", "done")
AGENTS = ("claude", "copilot")
KINDS = ("epic", "story", "task", "bug", "spike", "idea", "misc")
KIND_GLYPH = {"epic": "◈", "story": "❖", "task": "▪", "bug": "✱", "spike": "↯", "idea": "✦", "misc": "·"}
COPILOT_SESSIONS = Path("~/.copilot/session-state").expanduser()
UNSET = object()


# ---------------------------------------------------------------- storage


def data_dir() -> Path:
    override = os.environ.get("FU_DATA_DIR")
    if override:
        return Path(override).expanduser()
    cfg = {"data_dir": "~/development/follow-ups"}
    if CONFIG_FILE.exists():
        cfg.update(tomllib.loads(CONFIG_FILE.read_text()))
    elif "JQ_TOOLS_CONFIG" not in os.environ:
        CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
        CONFIG_FILE.write_text(DEFAULT_TOML)
    return Path(cfg["data_dir"]).expanduser()


def today() -> str:
    return date.today().isoformat()


def idle_days(item: dict) -> int:
    return (date.today() - date.fromisoformat(item["last_worked"])).days


def age(iso: str) -> str:
    n = (date.today() - date.fromisoformat(iso)).days
    return "today" if n == 0 else f"{n}d ago"


def heat(days: int) -> str:
    return "green" if days < 3 else "yellow" if days < 7 else "red"


def resume_cmd(item: dict) -> str | None:
    agent, sid = item.get("agent"), item.get("session_id")
    if agent not in AGENTS or not sid:
        return None
    base = f"claude --resume {shlex.quote(sid)}" if agent == "claude" else f"copilot --resume={shlex.quote(sid)}"
    cwd = item.get("cwd")
    return f"cd {shlex.quote(cwd)} && {base}" if cwd else base


def load_db() -> dict:
    """Boards written before jobs existed have no 'jobs' list; that is fine."""
    path = data_dir() / "board.json"
    db = json.loads(path.read_text()) if path.exists() else {}
    db.setdefault("items", [])
    db.setdefault("jobs", [])
    return db


def save_db(db: dict) -> None:
    d = data_dir()
    d.mkdir(parents=True, exist_ok=True)
    # Atomic write: the agent and the TUI may both touch the board.
    fd, tmp = tempfile.mkstemp(dir=d, suffix=".tmp")
    with os.fdopen(fd, "w") as f:
        json.dump(db, f, indent=2)
    os.replace(tmp, d / "board.json")
    (d / "BOARD.md").write_text(render_markdown(db))


def next_id(rows: list[dict]) -> int:
    return max((r["id"] for r in rows), default=0) + 1


def find(items: list[dict], ident: str) -> dict:
    for i in items:
        if str(i["id"]) == str(ident).lstrip("#"):
            return i
    sys.exit(f"fu: no follow-up with id {ident}")


# -------------------------------------------------------------------- jobs


def job_by_ref(db: dict, ref, fuzzy: bool = True) -> dict | None:
    """A job is addressed by id ('3' or 'J3') or by name (exact, else unique substring)."""
    r = str(ref).strip()
    if r[:1].lower() == "j" and r[1:].isdigit():
        r = r[1:]
    if r.isdigit():
        return next((j for j in db["jobs"] if j["id"] == int(r)), None)
    low = r.lower()
    exact = [j for j in db["jobs"] if j["name"].lower() == low]
    if exact:
        return exact[0]
    if fuzzy:
        part = [j for j in db["jobs"] if low in j["name"].lower()]
        return part[0] if len(part) == 1 else None
    return None


def ensure_job(db: dict, ref: str, kind: str | None = None) -> dict:
    # Exact match only when creating: a new name that happens to be a substring
    # of an old one must not silently attach to it.
    job = job_by_ref(db, ref, fuzzy=False)
    if job:
        return job
    job = {
        "id": next_id(db["jobs"]),
        "name": ref.strip(),
        "kind": kind or "misc",
        "description": "",
        "created": today(),
    }
    db["jobs"].append(job)
    return job


def job_name(db: dict, item: dict) -> str:
    job = next((j for j in db["jobs"] if j["id"] == item.get("job_id")), None)
    return job["name"] if job else ""


def set_job(db: dict, item: dict, ref, kind: str | None = None) -> None:
    ref = (ref or "").strip() if isinstance(ref, str) else ref
    item["job_id"] = None if not ref or str(ref).lower() == "none" else ensure_job(db, str(ref), kind)["id"]


# ----------------------------------------------------------------- sessions


def skey(item: dict) -> str:
    """Stable key for the agent session an item came from ('' when unknown)."""
    return f"{item['agent']}:{item['session_id']}" if item.get("agent") and item.get("session_id") else ""


def session_label(key: str, items: list[dict]) -> str:
    if not key:
        return "no session"
    agent, sid = key.split(":", 1)
    cwd = next((i["cwd"] for i in items if skey(i) == key and i.get("cwd")), "")
    return f"{agent} {sid[:8]}" + (f" · {Path(cwd).name}" if cwd else "")


def detect_agent() -> str | None:
    return "claude" if os.environ.get("CLAUDECODE") else None


def detect_session(agent: str | None, cwd: str) -> str | None:
    if agent == "claude":
        return os.environ.get("CLAUDE_CODE_SESSION_ID")
    if agent == "copilot" and COPILOT_SESSIONS.exists():
        # Copilot exposes no env var; the live session is the most recently
        # updated one started in this folder.
        best, best_mtime = None, 0.0
        for ws in COPILOT_SESSIONS.glob("*/workspace.yaml"):
            if f"cwd: {cwd}\n" in ws.read_text() and ws.stat().st_mtime > best_mtime:
                best, best_mtime = ws.parent.name, ws.stat().st_mtime
        return best
    return None


# ------------------------------------------------------- filtering/grouping


def matches(item: dict, f: dict) -> bool:
    """Filter keys: status, all, job (id or 'none'), session, agent, text, idle, recent."""
    if f.get("status"):
        if item["status"] != f["status"]:
            return False
    elif not f.get("all") and item["status"] == "done":
        return False  # hidden, never deleted: done items stay on the board until removed
    if f.get("job") is not None:
        wanted, actual = f["job"], item.get("job_id")
        if (actual is not None) if wanted == "none" else (actual != wanted):
            return False
    if f.get("session"):
        key = skey(item)
        if (f["session"] == "none" and key) or (f["session"] != "none" and f["session"] not in key):
            return False
    if f.get("agent") and item.get("agent") != f["agent"]:
        return False
    if f.get("text") and f["text"].lower() not in f"{item['summary']} {item['why']} {item.get('notes', '')}".lower():
        return False
    if f.get("idle") is not None and idle_days(item) < f["idle"]:
        return False
    return not (f.get("recent") is not None and idle_days(item) > f["recent"])


def sort_items(items: list[dict]) -> list[dict]:
    return sorted(items, key=lambda i: (STATUSES.index(i["status"]), i["last_worked"]))


def jobs_ordered(db: dict) -> list[dict]:
    return sorted(db["jobs"], key=lambda j: (KINDS.index(j["kind"]), j["name"].lower()))


def by_session(items: list[dict]) -> dict[str, list[dict]]:
    out: dict[str, list[dict]] = {}
    for i in sort_items(items):
        out.setdefault(skey(i), []).append(i)
    return dict(sorted(out.items(), key=lambda kv: max(i["last_worked"] for i in kv[1]), reverse=True))


def public(item: dict, db: dict) -> dict:
    return {**item, "job": job_name(db, item) or None, "resume": resume_cmd(item)}


def render_markdown(db: dict) -> str:
    out = ["# Follow-ups", "", "_Generated by `fu` - edit with `fu`, not by hand._", ""]
    for status in STATUSES:
        group = [i for i in db["items"] if i["status"] == status]
        if not group:
            continue
        out += [f"## {status.capitalize()}", ""]
        for i in sorted(group, key=lambda i: i["last_worked"]):
            job = job_name(db, i)
            out.append(f"- **#{i['id']} {i['summary']}**" + (f" _[{job}]_" if job else "") + "  ")
            out.append(f"  {i['why']}  ")
            out.append(f"  added {i['added']} · last worked {i['last_worked']} ({age(i['last_worked'])})  ")
            cmd = resume_cmd(i)
            out.append(f"  restart: `{cmd}`" if cmd else "  restart: _(no session id captured)_")
            out.append("")
    return "\n".join(out) + "\n"


# --------------------------------------------------------------- item edits


def new_item(db: dict, summary: str, **kw) -> dict:
    job, kind = kw.pop("job", None), kw.pop("kind", None)
    item = {
        "id": next_id(db["items"]),
        "summary": summary,
        "why": "",
        "status": "todo",
        "added": today(),
        "last_worked": today(),
        "agent": None,
        "session_id": None,
        "cwd": None,
        "notes": "",
        "job_id": None,
        **kw,
    }
    if job:
        set_job(db, item, job, kind)
    db["items"].append(item)
    return item


def update(ident: str, job=UNSET, kind=None, **changes) -> dict:
    """Apply exactly the fields given (None clears a field); `job` is a name, id or 'none'."""
    db = load_db()
    item = find(db["items"], ident)
    item.update(changes)
    if job is not UNSET:
        set_job(db, item, job, kind)
    save_db(db)
    return item


def clip(text: str, n: int) -> str:
    return text if len(text) <= n else text[: n - 1] + "…"
