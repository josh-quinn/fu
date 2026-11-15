"""Storage, jobs, sessions, filtering and rendering for the follow-up board (no UI)."""

import json
import os
import re
import shlex
import sys
import tempfile
from datetime import date, timedelta
from pathlib import Path

from fu import config

STATUSES = ("todo", "doing", "done")
AGENTS = ("claude", "copilot")
# Job types describe work (ADR 0007); config.yaml can replace or extend them, and the TUI's "Other…"
# adds the user's own to the board.
KINDS = ("epic", "story", "bug", "spike", "task")
KIND_GLYPH = {"epic": "◈", "story": "❖", "bug": "✱", "spike": "↯", "task": "▪"}
DEFAULT_KIND = "story"
# Retired kinds: an idea is a follow-up and a cheatsheet or runbook is an output, so old jobs of
# those kinds become plain tasks.
LEGACY_KINDS = {"idea": "task", "btw": "task", "guide": "task", "misc": "task"}
JIRA_KEY = re.compile(r"^([A-Z][A-Z0-9]+)-\d+$")
# Agent session ids are UUID-like. Anything else is refused, because an id ends up in file
# names, glob patterns and the restart command.
SESSION_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
COPILOT_SESSIONS = Path("~/.copilot/session-state").expanduser()
UNSET = object()


def valid_session_id(session_id: str | None) -> bool:
    return bool(session_id) and bool(SESSION_ID.match(session_id)) and ".." not in session_id


# ---------------------------------------------------------------- storage


def data_dir() -> Path:
    override = os.environ.get("FU_DATA_DIR")
    if override:
        return Path(override).expanduser()
    return Path(str(config.load()["data_dir"])).expanduser()


def key_modifier() -> str:
    """The modifier that runs shortcuts while a search is typing (`keys: modifier` in the config)."""
    return config.modifier()


def glyph(kind: str) -> str:
    return KIND_GLYPH.get(kind, "•")


def job_types(db: dict | None = None, project: str | None = None) -> list[str]:
    """The job types on offer: the config's (for this project), then the user's own from the board."""
    jobs = config.for_project(project).get("jobs") or {}
    types = [*(jobs.get("types") or KINDS), *(jobs.get("extra_types") or []), *((db or {}).get("types") or [])]
    return list(dict.fromkeys(str(t) for t in types))


def project_of(job: dict) -> str:
    """The Jira project key in the job's ID (ML in ML-12), else the project set by hand."""
    m = JIRA_KEY.match(job.get("ext_id") or "")
    return m.group(1) if m else job.get("project", "")


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
    """Older boards are upgraded in memory: no 'jobs' list, legacy kinds, no ext_id/parent_id."""
    path = data_dir() / "board.json"
    db = json.loads(path.read_text()) if path.exists() else {}
    db.setdefault("items", [])
    db.setdefault("jobs", [])
    for job in db["jobs"]:
        job["kind"] = LEGACY_KINDS.get(job["kind"], job["kind"])
        job.setdefault("ext_id", "")
        job.setdefault("parent_id", None)
        job.setdefault("notes", "")
        job.setdefault("home", "")
        job.setdefault("project", "")
    db.setdefault("types", [])
    return db


def save_db(db: dict) -> None:
    d = data_dir()
    d.mkdir(parents=True, exist_ok=True)
    # Atomic write: the agent and the TUI may both touch the board.
    fd, tmp = tempfile.mkstemp(dir=d, suffix=".tmp")
    try:
        with os.fdopen(fd, "w") as f:
            json.dump(db, f, indent=2)
        os.replace(tmp, d / "board.json")
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise
    (d / "BOARD.md").write_text(render_markdown(db))


def next_id(rows: list[dict]) -> int:
    return max((r["id"] for r in rows), default=0) + 1


def find(items: list[dict], ident: str) -> dict:
    for i in items:
        if str(i["id"]) == str(ident).lstrip("#"):
            return i
    sys.exit(f"fu: no follow-up with id {ident}")


# -------------------------------------------------------------------- jobs


def job_label(job: dict) -> str:
    """What the user sees as the job's id: their own (e.g. a Jira key) or J<n>."""
    return job.get("ext_id") or f"J{job['id']}"


def job_by_ref(db: dict, ref, fuzzy: bool = True) -> dict | None:
    """A job is addressed by external id, 'J3'/'3', or name (exact, else unique substring)."""
    r = str(ref).strip()
    low = r.lower()
    for job in db["jobs"]:
        if job["ext_id"] and job["ext_id"].lower() == low:
            return job
    num = low[1:].lstrip("-") if low[:1] == "j" else low
    if num.isdigit():
        return next((j for j in db["jobs"] if j["id"] == int(num)), None)
    exact = [j for j in db["jobs"] if j["name"].lower() == low]
    if exact:
        return exact[0]
    if fuzzy:
        part = [j for j in db["jobs"] if low in j["name"].lower()]
        return part[0] if len(part) == 1 else None
    return None


def check_ext_id(db: dict, ext_id: str, own: dict | None = None) -> None:
    clash = next((j for j in db["jobs"] if j is not own and ext_id and j["ext_id"].lower() == ext_id.lower()), None)
    if clash:
        sys.exit(f"fu: id {ext_id} is already used by job '{clash['name']}'")


def descendants(db: dict, job: dict) -> list[dict]:
    out, queue = [], [job]
    while queue:
        cur = queue.pop()
        for child in db["jobs"]:
            if child["parent_id"] == cur["id"] and child not in out:
                out.append(child)
                queue.append(child)
    return out


def set_parent(db: dict, job: dict, ref) -> None:
    """Parent by ref, or None/'none' to clear. A job can't sit under itself or its own children."""
    if ref is None or str(ref).strip().lower() in ("", "none"):
        job["parent_id"] = None
        return
    parent = job_by_ref(db, ref) or sys.exit(f"fu: no job matching '{ref}'")
    if parent is job or parent in descendants(db, job):
        sys.exit(f"fu: '{parent['name']}' can't be the parent of '{job['name']}' (that would make a loop)")
    job["parent_id"] = parent["id"]


def remove_job(db: dict, job: dict) -> int:
    """Delete a job. Its tasks are kept, unassigned; its child jobs move up to its parent."""
    n = 0
    for item in db["items"]:
        if item.get("job_id") == job["id"]:
            item["job_id"] = None
            n += 1
    for child in db["jobs"]:
        if child["parent_id"] == job["id"]:
            child["parent_id"] = job["parent_id"]
    db["jobs"] = [j for j in db["jobs"] if j is not job]
    return n


def create_job(
    db: dict,
    name: str,
    kind: str | None = None,
    ext_id: str = "",
    parent=None,
    desc: str = "",
    home: str = "",
    project: str = "",
) -> dict:
    ext_id = ext_id.strip()
    check_ext_id(db, ext_id)
    job = {
        "id": next_id(db["jobs"]),
        "name": name.strip(),
        "kind": kind or DEFAULT_KIND,
        "ext_id": ext_id,
        "parent_id": None,
        "description": desc,
        "notes": "",
        "home": home_path(home),
        "project": project.strip(),
        "created": today(),
    }
    remember_type(db, job["kind"])
    db["jobs"].append(job)
    if parent:
        set_parent(db, job, parent)
    return job


def remember_type(db: dict, kind: str) -> None:
    """A type the user made up is kept on the board so it is offered next time."""
    if kind and kind not in job_types(db):
        db.setdefault("types", []).append(kind)


def home_path(folder: str) -> str:
    """A job's home folder as stored: absolute, '' for none."""
    return str(Path(folder.strip()).expanduser().resolve()) if folder and folder.strip() else ""


def ensure_job(db: dict, ref: str, kind: str | None = None) -> dict:
    # Exact match only when creating: a new name that happens to be a substring
    # of an old one must not silently attach to it.
    return job_by_ref(db, ref, fuzzy=False) or create_job(db, ref, kind)


def session_job(db: dict, agent: str | None, session_id: str | None, cwd: str | None) -> dict | None:
    """The job a session is working on, so a follow-up parked in it lands there: the job of the
    session's latest task (a session started from fu has one from the start), else the job whose
    home folder holds cwd (the deepest one)."""
    if agent and session_id:
        mine = [i for i in db["items"] if i.get("agent") == agent and i.get("session_id") == session_id]
        latest = max((i for i in mine if i.get("job_id")), key=lambda i: (i["last_worked"], i["id"]), default=None)
        if latest:
            return next((j for j in db["jobs"] if j["id"] == latest["job_id"]), None)
    if cwd:
        here = Path(cwd).resolve()
        homes = [
            j for j in db["jobs"] if j.get("home") and (here == Path(j["home"]) or Path(j["home"]) in here.parents)
        ]
        return max(homes, key=lambda j: len(j["home"]), default=None)
    return None


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


SORT_COLUMNS = ("id", "status", "job", "summary", "added", "last_worked")


def sort_board(db: dict, items: list[dict], column: str = "status", descending: bool = False) -> list[dict]:
    """Order the board by one column. Ties fall back as the user asked:
    job -> status, last worked, added; status -> last worked, added (and so on
    for the other columns). Always ascending or descending, never unsorted.
    """
    names = {j["id"]: j["name"].lower() for j in db["jobs"]}

    def key(i: dict) -> tuple:
        status = STATUSES.index(i["status"])
        # the id is the last tie-break, so equal rows keep a fixed order (and descending is an exact reverse)
        return (
            *{
                "id": (i["id"],),
                "status": (status, i["last_worked"], i["added"]),
                "job": (
                    i.get("job_id") not in names,
                    names.get(i.get("job_id"), ""),
                    status,
                    i["last_worked"],
                    i["added"],
                ),
                "summary": (i["summary"].lower(), status, i["last_worked"], i["added"]),
                "added": (i["added"], status, i["last_worked"]),
                "last_worked": (i["last_worked"], status, i["added"]),
            }[column],
            i["id"],
        )

    return sorted(items, key=key, reverse=descending)


def jobs_ordered(db: dict) -> list[dict]:
    order = job_types(db)
    return sorted(
        db["jobs"],
        key=lambda j: (order.index(j["kind"]) if j["kind"] in order else len(order), j["name"].lower()),
    )


# ------------------------------------------------------------- jobs board

JOB_COLUMNS = ("id", "kind", "parent", "title", "added", "last_worked")
DATE_COLUMNS = ("added", "last_worked")
MONTHS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")


def job_status(db: dict, job: dict) -> str:
    """A job has no status of its own: doing if any task is, done once every task is, else todo."""
    states = [i["status"] for i in db["items"] if i.get("job_id") == job["id"]]
    return "doing" if "doing" in states else "done" if states and all(x == "done" for x in states) else "todo"


def job_last_worked(db: dict, job: dict) -> str:
    return max([i["last_worked"] for i in db["items"] if i.get("job_id") == job["id"]], default=job["created"])


def job_rows(db: dict) -> list[dict]:
    """One row per job with the columns of the Jobs board; newest activity first."""
    by_id = {j["id"]: j for j in db["jobs"]}
    rows = [
        {
            "job": j,
            "id": job_label(j),
            "kind": j["kind"],
            "project": project_of(j),
            "parent": by_id[j["parent_id"]]["name"] if j["parent_id"] in by_id else "",
            "title": j["name"],
            "added": j["created"],
            "last_worked": job_last_worked(db, j),
        }
        for j in db["jobs"]
    ]
    return sorted(rows, key=lambda r: (r["last_worked"], r["job"]["id"]), reverse=True)


def sort_jobs(rows: list[dict], column: str = "last_worked", descending: bool = True) -> list[dict]:
    """Order Jobs rows by one column; ties fall back to last worked, then the job id."""
    rows = sorted(rows, key=lambda r: (r["last_worked"], r["job"]["id"]))
    return sorted(rows, key=lambda r: r[column].lower(), reverse=descending)


def filter_jobs(rows: list[dict], filters: dict) -> list[dict]:
    """filters: column -> {"text": ...} (case-insensitive contains) or {"from": iso, "to": iso}."""

    def ok(row: dict) -> bool:
        for col, f in filters.items():
            if "text" in f and f["text"].lower() not in row[col].lower():
                return False
            if "from" in f and not f["from"] <= row[col] <= f["to"]:
                return False
        return True

    return [r for r in rows if ok(r)]


def suggestions(rows: list[dict], column: str, typed: str = "") -> list[str]:
    """Distinct values of a column that match what has been typed, prefix matches first."""
    values = (
        list(dict.fromkeys([*job_types(), *(r[column] for r in rows)]))
        if column == "kind"
        else sorted({r[column] for r in rows if r[column]}, key=str.lower)
    )
    low = typed.strip().lower()
    hits = [v for v in values if low in v.lower()]
    return sorted(hits, key=lambda v: not v.lower().startswith(low))  # stable: prefix hits first


def fmt_date(d: date) -> str:
    return f"{MONTHS[d.month - 1]} {d.day} {d.year}"


def date_range(unit: str, anchor: date) -> tuple[str, str]:
    """The first and last day (ISO) of the day, Monday-based week, month or year around `anchor`."""
    if unit == "day":
        lo = hi = anchor
    elif unit == "week":
        lo = anchor - timedelta(days=anchor.weekday())
        hi = lo + timedelta(days=6)
    elif unit == "month":
        lo = anchor.replace(day=1)
        hi = lo.replace(year=lo.year + (lo.month == 12), month=lo.month % 12 + 1) - timedelta(days=1)
    else:
        lo, hi = date(anchor.year, 1, 1), date(anchor.year, 12, 31)
    return lo.isoformat(), hi.isoformat()


def range_options(unit: str, today_: date, count: int | None = None) -> list[tuple[str, str, str]]:
    """(label, from, to) for the weeks, months or years leading up to today, newest first."""
    out: list[tuple[str, str, str]] = []
    for n in range(count or {"week": 8, "month": 12, "year": 4}[unit]):
        if unit == "week":
            anchor = today_ - timedelta(weeks=n)
            lo, hi = date_range("week", anchor)
            label = "This week" if n == 0 else "Last week" if n == 1 else f"Week of {fmt_date(date.fromisoformat(lo))}"
        elif unit == "month":
            month0 = today_.year * 12 + today_.month - 1 - n
            anchor = date(month0 // 12, month0 % 12 + 1, 1)
            label = f"{MONTHS[anchor.month - 1]} {anchor.year}"
        else:
            anchor = date(today_.year - n, 1, 1)
            label = str(anchor.year)
        lo, hi = date_range(unit, anchor)
        out.append((label, lo, hi))
    return out


def job_resume_item(db: dict, job: dict) -> dict | None:
    """The most recently worked task of the job that can be restarted: where Enter on a job resumes."""
    items = [i for i in db["items"] if i.get("job_id") == job["id"] and resume_cmd(i)]
    return max(items, key=lambda i: (i["last_worked"], i["id"]), default=None)


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
