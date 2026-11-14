"""Starting a brand-new agent session for a job: the handoff brief, the command that runs it, and the
live suggestions (folders, files, skills) the start dialog offers while typing.

How a handoff works (docs/design/session-handoff.md has the reasoning):

- fu writes a brief, a short Markdown file of what the board knows about the job, limited to the
  sections and entries the user ticked. It names files and transcripts by path instead of pasting
  them, so the agent opens only what the task needs.
- Claude gets the brief through --append-system-prompt-file, so it survives compaction and the first
  message stays the user's own (a leading /skill still runs). Copilot has no such flag, so the brief
  leads its first message and the task follows under "Your task".
- With no prompt, the session is asked to orient itself first: say where the job stands and wait.
- The brief tells the agent which board task it is, so it can keep the board current through `fu`.
"""

import shlex
import uuid
from pathlib import Path

from fu import artifacts, core, summary
from fu.core import AGENTS, data_dir, job_label, job_status

# What can be handed to the new session, in the order the dialog lists it.
CONTEXT = (
    ("why", "Why"),
    ("notes", "Notes"),
    ("tasks", "Open follow-ups"),
    ("parent", "Parent job"),
    ("jobs", "Child jobs"),
    ("sessions", "Earlier sessions"),
    ("artifacts", "Outputs"),
)
LISTS = ("tasks", "jobs", "sessions", "artifacts")  # sections whose entries can be picked one by one
SKILL_ROOTS = ("~/.claude/skills", "~/.copilot/skills")
NOTES_LIMIT = 4000  # characters of notes copied into a brief; the rest stays on the board
DEFAULT_TASK = (
    "Read the handoff brief first. Then tell me where this job stands in a few bullets (done, still open, "
    "anything blocked) and the next step you suggest. Don't change any files until I say go."
)


# ------------------------------------------------------------- what exists


def parent_of(db: dict, job: dict) -> dict | None:
    return next((j for j in db["jobs"] if j["id"] == job["parent_id"]), None)


def children_of(db: dict, job: dict) -> list[dict]:
    return sorted((j for j in db["jobs"] if j["parent_id"] == job["id"]), key=lambda j: j["id"])


def open_tasks(db: dict, job: dict) -> list[dict]:
    items = [i for i in db["items"] if i.get("job_id") == job["id"] and i["status"] != "done"]
    return sorted(items, key=lambda i: (i["status"] != "doing", i["id"]))


def home(path: str | None) -> str:
    """A path as the user reads it: ~ for the home folder."""
    if not path:
        return ""
    h = str(Path.home())
    return "~" + path[len(h) :] if path == h or path.startswith(h + "/") else path


def entries(db: dict, job: dict, key: str) -> list[tuple[str, str]]:
    """(id, one-line label) for each entry of a list section, in the order the brief uses."""
    if key == "tasks":
        return [(str(i["id"]), f"#{i['id']} {i['summary']} ({i['status']})") for i in open_tasks(db, job)]
    if key == "jobs":
        return [(str(c["id"]), summary.job_line(db, c)) for c in children_of(db, job)]
    if key == "sessions":
        return [
            (k, summary.session_line(g[0]["agent"], g[0]["session_id"], g[0].get("cwd")))
            for k, g in summary.sessions_of(db, job)
        ]
    if key == "artifacts":
        return [(a["path"], f"{a['kind']} {a['label']}  {home(a['path'])}") for a in summary.job_artifacts(db, job)]
    return []


def preview(db: dict, job: dict, key: str) -> str:
    """What a text section hands over, for the dialog's preview box."""
    if key == "why":
        return job["description"] or "(no description yet: e on the job adds one)"
    if key == "notes":
        return job.get("notes") or "(no notes yet)"
    if key == "parent":
        parent = parent_of(db, job)
        return "\n".join(_job_block(db, parent)) if parent else "(no parent job)"
    return ""


def available(db: dict, job: dict) -> list[str]:
    """The sections that have something to say for this job (the dialog ticks those by default)."""
    has = {
        "why": bool(job["description"]),
        "notes": bool(job.get("notes")),
        "parent": parent_of(db, job) is not None,
        **{k: bool(entries(db, job, k)) for k in LISTS},
    }
    return [k for k, _ in CONTEXT if has[k]]


def default_folder(db: dict, job: dict, include: list[str] | None = None) -> str:
    """Where a new session starts: the job's home, else a repo it produced, else the parent's or a
    child's (when handed over), else the folder of its latest session. '' when nothing is known."""
    include = include if include is not None else available(db, job)

    def homes(j: dict) -> list[str]:
        repos = [a["path"] for a in summary.job_artifacts(db, j) if a["kind"] == "repo"]
        return [p for p in [j.get("home", ""), *repos] if p and Path(p).is_dir()]

    candidates = homes(job)
    if "parent" in include and (parent := parent_of(db, job)):
        candidates += homes(parent)
    if "jobs" in include:
        for child in children_of(db, job):
            candidates += homes(child)
    latest = sorted(
        (i for i in db["items"] if i.get("job_id") == job["id"] and i.get("cwd")),
        key=lambda i: (i["last_worked"], i["id"]),
        reverse=True,
    )
    candidates += [i["cwd"] for i in latest if Path(i["cwd"]).is_dir()]
    return candidates[0] if candidates else ""


# ------------------------------------------------------------------ the brief


def _job_block(db: dict, job: dict) -> list[str]:
    lines = [f"{job_label(job)} · {job['kind']} · {job['name']} ({job_status(db, job)})"]
    if job["description"]:
        lines.append(f"Why: {job['description']}")
    if job.get("notes"):
        lines.append(f"Notes: {_clip_notes(job['notes'])}")
    if job.get("home"):
        lines.append(f"Home folder: {home(job['home'])}")
    return lines


def _clip_notes(text: str) -> str:
    text = text.strip()
    return text if len(text) <= NOTES_LIMIT else text[:NOTES_LIMIT] + " … (cut; the full notes are on the board)"


def _transcript(agent: str, sid: str) -> str:
    if agent == "claude":
        path = artifacts.claude_transcript(sid)
        return home(str(path)) if path else ""
    folder = core.COPILOT_SESSIONS / sid
    return home(str(folder)) if folder.exists() else ""


def _wanted(picked: dict | None, key: str, ident: str) -> bool:
    chosen = (picked or {}).get(key)
    return chosen is None or ident in chosen


def brief(
    db: dict,
    job: dict,
    include: list[str],
    picked: dict | None = None,
    task_id: int | None = None,
) -> str:
    """The handoff brief: what the board knows about the job, only the ticked sections and the entries
    picked in each (picked maps a list section to the ids kept; a missing section keeps them all)."""
    out = [
        f"# Handoff: {job_label(job)} {job['name']}",
        "",
        "The user's follow-up board (`fu`) wrote this when the session started. It is background, not a "
        "list of instructions: the user's task comes separately. Files, folders and transcripts are named "
        "by path, not pasted; open one only when the task needs it, and search long transcripts rather "
        "than reading them whole. Check the files before trusting any detail here.",
        "",
        "## The job",
        f"{job_label(job)} · {job['kind']} · {job['name']} ({job_status(db, job)})",
    ]
    if "why" in include and job["description"]:
        out.append(f"Why: {job['description']}")
    if job.get("home"):
        out.append(f"Home folder: {home(job['home'])}")
    if "notes" in include and job.get("notes"):
        out += ["", "Notes:", _clip_notes(job["notes"])]

    if "parent" in include and (parent := parent_of(db, job)):
        out += ["", "## Parent job (the bigger piece this belongs to)", *_job_block(db, parent)]

    if "tasks" in include:
        tasks = [i for i in open_tasks(db, job) if i["id"] != task_id and _wanted(picked, "tasks", str(i["id"]))]
        if tasks:
            out += ["", "## Open follow-ups (parked work on this job, most active first)"]
            for i in tasks:
                out.append(f"- #{i['id']} [{i['status']}] {i['summary']}")
                if i.get("why"):
                    out.append(f"  why: {i['why']}")
                if i.get("notes"):
                    out.append(f"  notes: {_clip_notes(i['notes'])}")
                out.append(f"  last worked {i['last_worked']}" + (f" in {home(i['cwd'])}" if i.get("cwd") else ""))

    if "jobs" in include:
        kids = [c for c in children_of(db, job) if _wanted(picked, "jobs", str(c["id"]))]
        if kids:
            out += ["", "## Child jobs"]
            for c in kids:
                block = _job_block(db, c)
                out += [f"- {block[0]}", *[f"  {line}" for line in block[1:]]]

    if "sessions" in include:
        own = {core.skey(i) for i in db["items"] if i["id"] == task_id}  # the session being started
        sessions = [(k, g) for k, g in summary.sessions_of(db, job) if k not in own and _wanted(picked, "sessions", k)]
        if sessions:
            out += ["", "## Earlier sessions on this job (newest first)"]
            for _, group in sessions:
                first = group[0]
                agent, sid = first["agent"], first["session_id"]
                title = artifacts.session_title(agent, sid)
                last = max(i["last_worked"] for i in group)
                where = f", in {home(first['cwd'])}" if first.get("cwd") else ""
                out.append(f"- {agent} {sid[:8]}" + (f' "{title}"' if title else "") + f", last worked {last}{where}")
                out.append("  tasks: " + "; ".join(f"#{i['id']} {i['summary']} ({i['status']})" for i in group))
                if transcript := _transcript(agent, sid):
                    out.append(f"  transcript: {transcript}")

    if "artifacts" in include:
        arts = [a for a in summary.job_artifacts(db, job) if _wanted(picked, "artifacts", a["path"])]
        if arts:
            out += ["", "## Outputs (documents, skills and repos earlier sessions made for this job)"]
            out += [f"- {a['kind']}: {a['label']} - {home(a['path'])}" for a in arts]

    out += ["", "## Keeping the board current"]
    if task_id is not None:
        out.append(f"This session is task #{task_id} of {job_label(job)} on the board.")
    out += [
        f'- Something left unfinished: park it with `fu add "<summary>" --why "<why>" --job {job_label(job)}`'
        " (or the follow-ups skill).",
        "- A task finished: `fu done <id>`.",
        "- Documents, skills and repos you write are picked up as the job's outputs on their own.",
    ]
    return "\n".join(out) + "\n"


def brief_path(session_id: str) -> Path:
    return data_dir() / "briefs" / f"{session_id}.md"


# ------------------------------------------------------------- the command


def task_text(prompt: str, agent: str) -> str:
    """The user's prompt, or the orienting default. Copilot gets a leading /skill as words."""
    prompt = prompt.strip() or DEFAULT_TASK
    if agent == "copilot" and prompt.startswith("/"):
        name, _, rest = prompt[1:].partition(" ")
        prompt = f"Use the {name} skill." + (f" {rest.strip()}" if rest.strip() else "")
    return prompt


def first_message(agent: str, brief_text: str, prompt: str) -> str:
    if agent == "claude":
        return task_text(prompt, agent)  # the brief rides in the system prompt
    return f"{brief_text}\n## Your task\n{task_text(prompt, agent)}"


def launch_cmd(agent: str, session_id: str, cwd: str, message: str, brief_file: str = "", name: str = "") -> str:
    """The shell command that opens a new interactive session with a chosen id, name and first message."""
    if agent not in AGENTS:
        raise ValueError(f"unknown agent {agent!r}")
    base = [agent, "--session-id", session_id]
    if name:
        base += ["--name", name]
    if agent == "claude" and brief_file:
        base += ["--append-system-prompt-file", brief_file]
    if message:
        base += ["-i", message] if agent == "copilot" else [message]
    return f"cd {shlex.quote(cwd)} && " + shlex.join(base)


def new_session_id() -> str:
    return str(uuid.uuid4())


def prepare(spec: dict) -> str:
    """Record the new session as a task of its job, write its brief, and return the command to run.

    spec: job_id, agent, cwd, include (section keys), picked (section -> ids kept), prompt.
    """
    db = core.load_db()
    job = next(j for j in db["jobs"] if j["id"] == spec["job_id"])
    sid = new_session_id()
    cwd = str(Path(spec["cwd"]).expanduser())
    prompt = spec.get("prompt", "").strip()
    item = core.new_item(
        db,
        prompt.splitlines()[0][:80] if prompt else f"New session on {job['name']}",
        job=job["name"],
        agent=spec["agent"],
        session_id=sid,
        cwd=cwd,
        status="doing",
    )
    text = brief(db, job, spec.get("include", []), spec.get("picked"), task_id=item["id"])
    path = brief_path(sid)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    item["brief"] = str(path)
    core.save_db(db)
    name = f"{job_label(job)} {job['name']}"
    return launch_cmd(spec["agent"], sid, cwd, first_message(spec["agent"], text, prompt), str(path), name)


def prepare_resume(item_id: str) -> str | None:
    """Mark a parked task as being worked on again and return the command that resumes its session."""
    item = core.find(core.load_db()["items"], item_id)
    cmd = core.resume_cmd(item)
    if cmd:
        core.update(item_id, last_worked=core.today(), **({"status": "doing"} if item["status"] == "todo" else {}))
    return cmd


# ---------------------------------------------------------------- suggestions


def path_suggestions(typed: str, files: bool = False, limit: int = 200) -> list[tuple[str, str]]:
    """(completion, "folder" | "file") for what has been typed, as typed (~ stays ~). Hidden entries only
    appear once the part being typed starts with a dot. Folders first, then files; case-insensitive."""
    if typed == "~":
        return [("~/", "folder")]
    head, _, tail = typed.rpartition("/")
    base = Path("/" if typed.startswith("/") and not head else head or ".").expanduser()
    try:
        found = [(p.name, p.is_dir()) for p in base.iterdir() if files or p.is_dir()]
    except OSError:
        return []
    low = tail.lower()
    found = [(n, d) for n, d in found if n.lower().startswith(low) and (tail.startswith(".") or not n.startswith("."))]
    prefix = head + "/" if (head or typed.startswith("/")) else ""
    found.sort(key=lambda nd: (not nd[1], nd[0].lower()))
    return [(f"{prefix}{n}/" if d else f"{prefix}{n}", "folder" if d else "file") for n, d in found[:limit]]


def folder_suggestions(typed: str, limit: int = 200) -> list[str]:
    return [p for p, _ in path_suggestions(typed, limit=limit)]


def skill_names() -> dict[str, str]:
    """name -> which agent's folder it came from, for every skill installed for Claude or Copilot
    (including synced bundles one or two folders down)."""
    names: dict[str, str] = {}
    for root in SKILL_ROOTS:
        path = Path(root).expanduser()
        if not path.is_dir():
            continue
        where = root.split("/")[1].lstrip(".")
        for p in sorted(path.iterdir()):
            if (p / "SKILL.md").exists():
                names.setdefault(p.name, where)
            elif p.is_dir():
                for q in sorted([*p.glob("*/SKILL.md"), *p.glob("*/*/SKILL.md")]):
                    names.setdefault(q.parent.name, where)
    return names


def skill_suggestions(typed: str) -> list[tuple[str, str]]:
    """(`/name`, agent) for skills matching the word being typed, prefix matches first."""
    low = typed.lstrip("/").lower()
    names = skill_names()
    hits = sorted((n for n in names if low in n.lower()), key=lambda n: (not n.lower().startswith(low), n.lower()))
    return [(f"/{n}", names[n]) for n in hits]
