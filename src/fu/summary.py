"""What the Jobs screen's summary panel shows for one job, as plain data (the TUI only renders it)."""

from pathlib import Path

from fu import artifacts
from fu.core import by_session, glyph, job_label, job_status


def session_line(agent: str | None, sid: str, cwd: str | None) -> str:
    """`<agent> <id> · <title>`; the folder name stands in when the agent never named the session."""
    title = artifacts.session_title(agent, sid) or (Path(cwd).name if cwd else "")
    return f"{agent} {sid[:8]}" + (f" · {title}" if title else "")


def job_line(db: dict, job: dict) -> str:
    return f"{job_label(job)}: {job['kind']} {job['name']} ({job_status(db, job)})"


def job_items(db: dict, job: dict) -> list[dict]:
    """The job's tasks, the most recently worked first."""
    return sorted(
        (i for i in db["items"] if i.get("job_id") == job["id"]),
        key=lambda i: (i["last_worked"], i["id"]),
        reverse=True,
    )


def job_artifacts(db: dict, job: dict) -> list[dict]:
    """Every artifact of the job: the ones added to the job by hand, then each task's (most recent task
    first), each path once, minus the ones hidden on the job."""
    hidden = set(job.get("artifacts_dismissed", []))
    out: dict[str, dict] = {a["path"]: a for a in job.get("artifacts", []) if a["path"] not in hidden}
    for item in job_items(db, job):
        for art in artifacts.item_artifacts(item):
            if art["path"] not in hidden:
                out.setdefault(art["path"], {**art, "item_id": item["id"]})
    return list(out.values())


def remove_job_artifact(db: dict, job: dict, path: str) -> None:
    """Take an output off the job: whether added by hand or detected, it goes, and stays gone."""
    for owner in [job, *job_items(db, job)]:
        artifacts.remove(owner, path)


def sessions_of(db: dict, job: dict) -> list[tuple[str, list[dict]]]:
    """The job's sessions, most recently worked first."""
    items = [i for i in db["items"] if i.get("job_id") == job["id"]]
    return [(k, g) for k, g in by_session(items).items() if k]


def build(db: dict, job: dict) -> list[dict]:
    """Entries: {"key": None | action key, "style": title|meta|head|text|action, "text": str, "enabled": bool}.

    Keys: why, notes, artifacts, session:<agent:id>, job:<id>, item:<id>. The parent comes first so a
    child can climb back to it; Parent, Jobs, Follow-ups and Sessions always get a heading, even for one.
    """
    parent = next((j for j in db["jobs"] if j["id"] == job["parent_id"]), None)
    children = [j for j in db["jobs"] if j["parent_id"] == job["id"]]
    sessions = sessions_of(db, job)
    items = [i for i in db["items"] if i.get("job_id") == job["id"]]
    latest = max(items, key=lambda i: (i["last_worked"], i["id"]), default=None)
    arts = job_artifacts(db, job)

    out: list[dict] = []

    def add(style: str, text: str, key: str | None = None, enabled: bool | None = None) -> None:
        out.append({"key": key, "style": style, "text": text, "enabled": bool(key) if enabled is None else enabled})

    add("title", f"{glyph(job['kind'])} {job['name']}")
    add("meta", f"{job_label(job)} · {job['kind']}" + (f" · under {parent['name']}" if parent else ""))
    add("head", "Why")
    add(
        "action",
        job["description"] or (latest["why"] if latest and latest["why"] else "No description · enter to add one"),
        "why",
    )

    if parent:
        add("head", "Parent")
        add("action", job_line(db, parent), f"job:{parent['id']}")

    if children:
        add("head", "Jobs")
        for child in sorted(children, key=lambda j: j["id"]):
            add("action", job_line(db, child), f"job:{child['id']}")

    open_items = sorted((i for i in items if i["status"] != "done"), key=lambda i: (i["status"] != "doing", i["id"]))
    done = len(items) - len(open_items)
    if items:
        add("head", "Follow-ups" + (f"  ({done} done)" if done else ""))
        for i in open_items:
            add("action", f"#{i['id']} {i['summary']} ({i['status']})", f"item:{i['id']}")

    if sessions:
        add("head", "Sessions")
        for k, group in sessions:
            latest_task = group[0]
            add(
                "action",
                session_line(latest_task["agent"], latest_task["session_id"], latest_task.get("cwd")),
                f"session:{k}",
            )

    add("head", "Outputs")
    add("action", f"{len(arts)} to open" if arts else "none yet · enter to add one", "artifacts")

    add("head", "Notes")
    add("action", job.get("notes") or "Enter to add a note", "notes")
    return out


def build_item(db: dict, item: dict) -> list[dict]:
    """The Follow-ups panel for one follow-up, in the same shape as build(). Keys: why, job:<id>,
    session:<key>, artifacts, notes."""
    from fu.core import age, job_name, skey

    job = next((j for j in db["jobs"] if j["id"] == item.get("job_id")), None)
    arts = artifacts.item_artifacts(item)
    out: list[dict] = []

    def add(style: str, text: str, key: str | None = None) -> None:
        out.append({"key": key, "style": style, "text": text, "enabled": bool(key)})

    add("title", item["summary"])
    add("meta", f"#{item['id']} · {item['status']} · added {item['added']} · worked {age(item['last_worked'])}")
    add("head", "Why")
    add("action", item["why"] or "enter to add why you parked it", "why")
    add("head", "Job")
    if job:
        add("action", job_line(db, job), f"job:{job['id']}")
    else:
        add("text", job_name(db, item) or "none · e to set one")
    add("head", "Session")
    if skey(item):
        add("action", session_line(item["agent"], item["session_id"], item.get("cwd")), f"session:{skey(item)}")
    else:
        add("text", "no session id captured")
    add("head", "Outputs")
    add("action", f"{len(arts)} to open" if arts else "none yet · enter to add one", "artifacts")
    add("head", "Notes")
    add("action", item.get("notes") or "Enter to add a note", "notes")
    return out


def session_target(db: dict, job: dict, key: str) -> dict | None:
    """The most recently worked task of that session within the job: what restarting it resumes."""
    group = dict(sessions_of(db, job)).get(key)
    return max(group, key=lambda i: (i["last_worked"], i["id"])) if group else None
