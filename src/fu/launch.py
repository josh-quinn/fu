"""Starting a brand-new agent session for a job: the context to hand it, the command that runs it,
and the live suggestions (folders, skills) the start dialog offers while typing."""

import shlex
import uuid
from pathlib import Path

from fu import summary
from fu.core import AGENTS, job_label, job_status

# What can be handed to the new session, in the order the dialog lists it.
CONTEXT = (
    ("why", "Why"),
    ("notes", "Notes"),
    ("artifacts", "Artifacts"),
    ("parent", "Parent job"),
    ("jobs", "Child jobs"),
    ("sessions", "Earlier sessions"),
)
SKILL_ROOTS = ("~/.claude/skills", "~/.copilot/skills")


def _describe(db: dict, job: dict) -> list[str]:
    lines = [f"{job_label(job)}: {job['kind']} {job['name']} ({job_status(db, job)})"]
    if job["description"]:
        lines.append(f"  Why: {job['description']}")
    if job.get("notes"):
        lines.append(f"  Notes: {job['notes']}")
    return lines


def available(db: dict, job: dict) -> list[str]:
    """The context keys that have something to say for this job (the dialog ticks those by default)."""
    parent = next((j for j in db["jobs"] if j["id"] == job["parent_id"]), None)
    children = [j for j in db["jobs"] if j["parent_id"] == job["id"]]
    has = {
        "why": bool(job["description"]),
        "notes": bool(job.get("notes")),
        "artifacts": bool(summary.job_artifacts(db, job)),
        "parent": parent is not None,
        "jobs": bool(children),
        "sessions": bool(summary.sessions_of(db, job)),
    }
    return [k for k, _ in CONTEXT if has[k]]


def context_text(db: dict, job: dict, include: list[str]) -> str:
    """Plain text the new session starts from: only the sections asked for, nothing when none are."""
    out: list[str] = []
    if include:
        out.append(f"You are continuing work on {job_label(job)}: {job['kind']} {job['name']}.")
    if "why" in include and job["description"]:
        out.append(f"Why: {job['description']}")
    if "notes" in include and job.get("notes"):
        out.append(f"Notes: {job['notes']}")
    if "parent" in include:
        parent = next((j for j in db["jobs"] if j["id"] == job["parent_id"]), None)
        if parent:
            out += ["Parent job:", *_describe(db, parent)]
    if "jobs" in include:
        children = sorted((j for j in db["jobs"] if j["parent_id"] == job["id"]), key=lambda j: j["id"])
        if children:
            out.append("Child jobs:")
            for child in children:
                out += _describe(db, child)
    if "sessions" in include:
        lines = [
            f"  {summary.session_line(g[0]['agent'], g[0]['session_id'], g[0].get('cwd'))}"
            for _, g in summary.sessions_of(db, job)
        ]
        if lines:
            out += ["Earlier sessions on this job:", *lines]
    if "artifacts" in include:
        arts = summary.job_artifacts(db, job)
        if arts:
            out += ["Artifacts from earlier sessions:", *[f"  {a['label']}: {a['path']}" for a in arts]]
    return "\n".join(out)


def launch_cmd(agent: str, session_id: str, cwd: str, prompt: str) -> str:
    """The shell command that opens a new interactive session with a chosen id and first prompt."""
    if agent not in AGENTS:
        raise ValueError(f"unknown agent {agent!r}")
    base = [agent, "--session-id", session_id]
    if prompt:
        base += ["-i", prompt] if agent == "copilot" else [prompt]
    return f"cd {shlex.quote(cwd)} && " + shlex.join(base)


def new_session_id() -> str:
    return str(uuid.uuid4())


def full_prompt(db: dict, job: dict, include: list[str], prompt: str) -> str:
    return "\n\n".join(p for p in (context_text(db, job, include), prompt.strip()) if p)


# ---------------------------------------------------------------- suggestions


def folder_suggestions(typed: str, limit: int = 200) -> list[str]:
    """Folders that complete what has been typed, as typed (~ stays ~). Hidden folders only appear once
    the part being typed starts with a dot. Sorted, case-insensitive."""
    if typed == "~":
        return ["~/"]
    head, _, tail = typed.rpartition("/")
    base = Path("/" if typed.startswith("/") and not head else head or ".").expanduser()
    try:
        names = [p.name for p in base.iterdir() if p.is_dir()]
    except OSError:
        return []
    names = [n for n in names if n.lower().startswith(tail.lower()) and (tail.startswith(".") or not n.startswith("."))]
    prefix = head + "/" if (head or typed.startswith("/")) else ""
    return [f"{prefix}{n}/" for n in sorted(names, key=str.lower)[:limit]]


def skill_suggestions(typed: str) -> list[str]:
    """Skill names (`/name`) matching the word being typed, from both agents' skill folders."""
    low = typed.lstrip("/").lower()
    names: set[str] = set()
    for root in SKILL_ROOTS:
        path = Path(root).expanduser()
        if path.is_dir():
            names |= {p.name for p in path.iterdir() if (p / "SKILL.md").exists() or (p / "SKILL.md").is_symlink()}
    hits = sorted((n for n in names if low in n.lower()), key=lambda n: (not n.lower().startswith(low), n.lower()))
    return [f"/{n}" for n in hits]
