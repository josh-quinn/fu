"""What the Jobs screen's summary panel shows for one job, as plain data (the TUI only renders it)."""

from pathlib import Path

from fu import artifacts
from fu.core import KIND_GLYPH, by_session, job_label, job_resume_item, job_status, resume_cmd


def session_line(agent: str | None, sid: str, cwd: str | None) -> str:
    """`<agent> <id> · <title>`; the folder name stands in when the agent never named the session."""
    title = artifacts.session_title(agent, sid) or (Path(cwd).name if cwd else "")
    return f"{agent} {sid[:8]}" + (f" · {title}" if title else "")


def job_line(db: dict, job: dict) -> str:
    return f"{job_label(job)}: {job['kind']} {job['name']} ({job_status(db, job)})"


def job_artifacts(db: dict, job: dict) -> list[dict]:
    """Every artifact of the job's tasks, each path once (the most recent task first)."""
    out: dict[str, dict] = {}
    for item in sorted(
        (i for i in db["items"] if i.get("job_id") == job["id"]),
        key=lambda i: (i["last_worked"], i["id"]),
        reverse=True,
    ):
        for art in artifacts.item_artifacts(item):
            out.setdefault(art["path"], {**art, "item_id": item["id"]})
    return list(out.values())


def sessions_of(db: dict, job: dict) -> list[tuple[str, list[dict]]]:
    """The job's sessions, most recently worked first."""
    items = [i for i in db["items"] if i.get("job_id") == job["id"]]
    return [(k, g) for k, g in by_session(items).items() if k]


def build(db: dict, job: dict) -> list[dict]:
    """Entries: {"key": None | action key, "style": title|meta|head|text|action, "text": str, "enabled": bool}.

    Keys: restart, notes, artifacts, session:<agent:id>, job:<id>. A lone session or child job shares
    one line with its label; several get a heading and a line each.
    """
    parent = next((j for j in db["jobs"] if j["id"] == job["parent_id"]), None)
    children = [j for j in db["jobs"] if j["parent_id"] == job["id"]]
    sessions = sessions_of(db, job)
    resume = job_resume_item(db, job)
    items = [i for i in db["items"] if i.get("job_id") == job["id"]]
    latest = max(items, key=lambda i: (i["last_worked"], i["id"]), default=None)
    arts = job_artifacts(db, job)

    out: list[dict] = []

    def add(style: str, text: str, key: str | None = None, enabled: bool | None = None) -> None:
        out.append({"key": key, "style": style, "text": text, "enabled": bool(key) if enabled is None else enabled})

    add("title", f"{KIND_GLYPH[job['kind']]} {job['name']}")
    add("meta", f"{job_label(job)} · {job['kind']}" + (f" · under {parent['name']}" if parent else ""))
    add("head", "Why")
    add(
        "text",
        job["description"] or (latest["why"] if latest and latest["why"] else "No description. Press e to add one."),
    )

    if len(children) == 1:
        add("action", "Job  " + job_line(db, children[0]), f"job:{children[0]['id']}")
    elif children:
        add("head", "Jobs")
        for child in sorted(children, key=lambda j: j["id"]):
            add("action", job_line(db, child), f"job:{child['id']}")

    def first(group):
        return group[0]

    if len(sessions) == 1:
        k, group = sessions[0]
        add(
            "action",
            "Session  " + session_line(first(group)["agent"], first(group)["session_id"], first(group).get("cwd")),
            f"session:{k}",
        )
    elif sessions:
        add("head", "Sessions")
        for k, group in sessions:
            add(
                "action",
                session_line(first(group)["agent"], first(group)["session_id"], first(group).get("cwd")),
                f"session:{k}",
            )

    add("head", "Restart")
    cmd = resume_cmd(resume) if resume else None
    add("action" if cmd else "text", cmd or "no session id captured", "restart" if cmd else None)

    add("head", "Artifacts")
    add("action" if arts else "text", f"{len(arts)} to open" if arts else "none yet", "artifacts" if arts else None)

    add("head", "Notes")
    add("action", job.get("notes") or "Enter to add a note", "notes")
    return out


def session_target(db: dict, job: dict, key: str) -> dict | None:
    """The most recently worked task of that session within the job: what restarting it resumes."""
    group = dict(sessions_of(db, job)).get(key)
    return max(group, key=lambda i: (i["last_worked"], i["id"])) if group else None
