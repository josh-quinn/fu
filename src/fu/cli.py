"""Command-line interface: argument parsing and the non-interactive commands."""

import argparse
import json
import os
import sys
from importlib.metadata import version
from pathlib import Path

from fu.core import (
    AGENTS,
    CONFIG_FILE,
    DEFAULT_KIND,
    KIND_GLYPH,
    KINDS,
    STATUSES,
    UNSET,
    age,
    by_session,
    check_ext_id,
    clip,
    create_job,
    data_dir,
    detect_agent,
    detect_session,
    find,
    job_by_ref,
    job_label,
    job_name,
    jobs_ordered,
    load_db,
    matches,
    new_item,
    public,
    remove_job,
    resume_cmd,
    save_db,
    session_label,
    set_parent,
    skey,
    sort_items,
    today,
    update,
)

# --------------------------------------------------------------- commands


def cmd_add(a) -> None:
    db = load_db()
    cwd = str(Path(a.cwd).expanduser().resolve()) if a.cwd else os.getcwd()
    agent = a.agent or detect_agent()
    item = new_item(
        db,
        " ".join(a.summary),
        why=a.why or "",
        status=a.status,
        agent=agent,
        session_id=a.session_id or detect_session(agent, cwd),
        cwd=cwd,
        notes=a.note or "",
        job=a.job,
        kind=a.kind,
    )
    save_db(db)
    if a.json:
        print(json.dumps(public(item, db), indent=2))
        return
    job = job_name(db, item)
    print(f"added #{item['id']}: {item['summary']}" + (f"  [job: {job}]" if job else ""))
    print(f"restart: {resume_cmd(item) or '(no session id captured; pass --agent and --session-id)'}")


def filters_from_args(db: dict, a) -> dict:
    f: dict = {"all": a.all, "status": a.status, "agent": a.agent, "text": a.search, "idle": a.idle, "recent": a.recent}
    if a.job:
        if a.job.lower() == "none":
            f["job"] = "none"
        else:
            job = job_by_ref(db, a.job)
            f["job"] = job["id"] if job else sys.exit(f"fu: no job matching '{a.job}'")
    if a.session:
        f["session"] = a.session
    return f


def table(items: list[dict], db: dict) -> None:
    if not items:
        print("nothing on the board")
        return
    colour = {"todo": "33", "doing": "36", "done": "2"}
    tty = sys.stdout.isatty()
    print(f"{'ID':>3}  {'STATUS':<6}  {'JOB':<18}  {'LAST WORKED':<19}  SUMMARY")
    for i in items:
        row = (
            f"{i['id']:>3}  {i['status']:<6}  {clip(job_name(db, i) or '-', 18):<18}  "
            f"{i['last_worked']} {'(' + age(i['last_worked']) + ')':<8}  {i['summary']}"
        )
        print(f"\033[{colour[i['status']]}m{row}\033[0m" if tty else row)


def cmd_ls(a) -> None:
    db = load_db()
    f = filters_from_args(db, a)
    items = sort_items([i for i in db["items"] if matches(i, f)])
    print(json.dumps([public(i, db) for i in items], indent=2)) if a.json else table(items, db)


def cmd_show(a) -> None:
    db = load_db()
    item = public(find(db["items"], a.id), db)
    if a.json:
        print(json.dumps(item, indent=2))
        return
    for key in (
        "id",
        "summary",
        "why",
        "status",
        "job",
        "added",
        "last_worked",
        "agent",
        "session_id",
        "cwd",
        "notes",
        "resume",
    ):
        print(f"{key:<12} {item.get(key) or '-'}")


def cmd_edit(a) -> None:
    fields = {
        "summary": a.summary,
        "why": a.why,
        "status": a.status,
        "agent": a.agent,
        "session_id": a.session_id,
        "cwd": a.cwd,
        "notes": a.note,
    }
    changes = {k: v for k, v in fields.items() if v is not None}
    item = update(a.id, job=UNSET if a.job is None else a.job, kind=a.kind, **changes)
    print(f"updated #{item['id']}")


def cmd_touch(a) -> None:
    update(a.id, last_worked=today())
    print(f"#{a.id} last worked: today")


def cmd_done(a) -> None:
    update(a.id, status="done", last_worked=today())
    print(f"#{a.id} done (kept on the board until you delete it; `fu ls --all` shows it)")


def cmd_reopen(a) -> None:
    update(a.id, status="todo")
    print(f"#{a.id} reopened")


def cmd_rm(a) -> None:
    db = load_db()
    item = find(db["items"], a.id)
    if not a.yes and input(f"delete #{item['id']} '{item['summary']}'? [y/N] ").lower() != "y":
        return
    db["items"] = [i for i in db["items"] if i is not item]
    save_db(db)
    print(f"deleted #{item['id']}")


def cmd_resume(a) -> None:
    item = find(load_db()["items"], a.id)
    cmd = resume_cmd(item)
    if not cmd:
        sys.exit("fu: no session id stored for this item; set one with `fu edit ID --agent ... --session-id ...`")
    if a.print:
        print(cmd)
        return
    update(a.id, last_worked=today(), **({"status": "doing"} if item["status"] == "todo" else {}))
    os.execvp("/bin/sh", ["sh", "-c", cmd])


def cmd_skill(a) -> None:
    """Link (or copy) the packaged skill into the agents' skill folders."""
    import shutil
    from importlib.resources import files

    source = Path(str(files("fu") / "skills" / "follow-ups"))
    targets = {"claude": Path("~/.claude/skills").expanduser(), "copilot": Path("~/.copilot/skills").expanduser()}
    if a.action == "path":
        print(source)
        return
    for name, root in targets.items():
        if a.target not in (name, "all"):
            continue
        dest = root / "follow-ups"
        root.mkdir(parents=True, exist_ok=True)
        if dest.is_symlink() or dest.is_file():
            dest.unlink()
        elif dest.exists():
            shutil.rmtree(dest)
        if a.copy:
            shutil.copytree(source, dest)
        else:
            dest.symlink_to(source, target_is_directory=True)
        print(f"{name}: {dest} {'(copy)' if a.copy else '-> ' + str(source)}")


def cmd_path(a) -> None:
    print(f"data    {data_dir()}\nconfig  {CONFIG_FILE}")


def job_stats(db: dict, job: dict) -> dict:
    its = [i for i in db["items"] if i.get("job_id") == job["id"]]
    return {
        "open": sum(i["status"] != "done" for i in its),
        "done": sum(i["status"] == "done" for i in its),
        "sessions": len({skey(i) for i in its if skey(i)}),
        "last_worked": max((i["last_worked"] for i in its), default="-"),
    }


def cmd_job_add(a) -> None:
    db = load_db()
    name = " ".join(a.name)
    if job_by_ref(db, name, fuzzy=False):
        sys.exit(f"fu: job '{name}' already exists")
    job = create_job(db, name, a.kind, ext_id=a.id or "", parent=a.parent, desc=a.desc or "")
    save_db(db)
    print(f"added job {job_label(job)}: {job['name']} ({job['kind']})" + (f" under {a.parent}" if a.parent else ""))


def cmd_job_ls(a) -> None:
    db = load_db()
    rows = [{**j, **job_stats(db, j)} for j in jobs_ordered(db)]
    if a.json:
        print(json.dumps(rows, indent=2))
        return
    if not rows:
        print("no jobs yet: `fu job add NAME --kind epic`")
        return
    print(f"{'ID':<10}  {'KIND':<6}  {'PARENT':<10}  {'OPEN':>4}  {'DONE':>4}  {'SESS':>4}  {'LAST WORKED':<11}  NAME")
    by_id = {j["id"]: j for j in db["jobs"]}
    for r in rows:
        parent = job_label(by_id[r["parent_id"]]) if r["parent_id"] in by_id else "-"
        print(
            f"{job_label(r):<10}  {r['kind']:<6}  {parent:<10}  {r['open']:>4}  {r['done']:>4}  {r['sessions']:>4}  "
            f"{r['last_worked']:<11}  {r['name']}"
        )


def cmd_job_edit(a) -> None:
    db = load_db()
    job = job_by_ref(db, a.ref) or sys.exit(f"fu: no job matching '{a.ref}'")
    for field, value in (("name", a.name), ("kind", a.kind), ("description", a.desc)):
        if value is not None:
            job[field] = value
    if a.id is not None:
        check_ext_id(db, a.id.strip(), job)
        job["ext_id"] = a.id.strip()
    if a.parent is not None:
        set_parent(db, job, a.parent)
    save_db(db)
    print(f"updated {job_label(job)}")


def cmd_job_rm(a) -> None:
    db = load_db()
    job = job_by_ref(db, a.ref) or sys.exit(f"fu: no job matching '{a.ref}'")
    n = sum(i.get("job_id") == job["id"] for i in db["items"])
    if (
        not a.yes
        and input(f"delete job '{job['name']}'? its {n} item(s) are kept, just unassigned [y/N] ").lower() != "y"
    ):
        return
    remove_job(db, job)
    save_db(db)
    print(f"deleted job {job_label(job)}; {n} item(s) unassigned")


def cmd_sessions(a) -> None:
    db = load_db()
    rows = []
    for key, its in by_session([i for i in db["items"] if a.all or i["status"] != "done"]).items():
        rows.append(
            {
                "session": key or None,
                "label": session_label(key, its),
                "tasks": len(its),
                "jobs": sorted({job_name(db, i) for i in its if job_name(db, i)}),
                "last_worked": max(i["last_worked"] for i in its),
                "resume": resume_cmd(its[0]),
            }
        )
    if a.json:
        print(json.dumps(rows, indent=2))
        return
    for r in rows:
        print(f"{r['label']:<44} {r['tasks']:>2} task(s)  last {r['last_worked']}  jobs: {', '.join(r['jobs']) or '-'}")


def cmd_tree(a) -> None:
    db = load_db()
    items = [i for i in db["items"] if a.all or i["status"] != "done"]
    print("Jobs")
    for job in [*jobs_ordered(db), None]:
        its = [i for i in items if i.get("job_id") == (job["id"] if job else None)]
        if job is None and not its:
            continue
        print(
            f"  {KIND_GLYPH[job['kind']] if job else ' '} {job['name'] if job else '(no job)'}"
            + (f"  [{job['kind']}]" if job else "")
        )
        groups = by_session(its)
        for key, g in groups.items():
            indent = "    "
            if len(groups) > 1:
                print(f"    {session_label(key, g)}")
                indent = "      "
            for i in g:
                print(f"{indent}#{i['id']} {i['status']:<5} {i['summary']}")
    print("Sessions")
    for key, g in by_session(items).items():
        print(f"  {session_label(key, g)}")
        for i in g:
            print(
                f"    #{i['id']} {i['status']:<5} {i['summary']}"
                + (f"  [{job_name(db, i)}]" if job_name(db, i) else "")
            )


# ------------------------------------------------------------------- main


def main() -> None:
    p = argparse.ArgumentParser(
        prog="fu", description="Follow-up board for parked work. Run with no arguments for the TUI."
    )
    p.add_argument("--version", action="version", version=f"fu {version('fu-board')}")
    sub = p.add_subparsers(dest="cmd")

    def parser(name, fn, help, aliases=(), parent=None):
        sp = (parent or sub).add_parser(name, help=help, aliases=list(aliases))
        sp.set_defaults(fn=fn)
        return sp

    sp = parser("add", cmd_add, "park a task")
    sp.add_argument("summary", nargs="+", help="one-line topic")
    sp.add_argument("--why", help="why you started it / where you left off")
    sp.add_argument("--job", help="job name or id to file it under (a new name creates the job)")
    sp.add_argument("--kind", choices=KINDS, help="kind for a newly created job (default story)")
    sp.add_argument("--agent", choices=AGENTS, help="default: detected from the environment")
    sp.add_argument("--session-id", help="default: detected for the chosen agent")
    sp.add_argument("--cwd", help="default: current folder")
    sp.add_argument("--status", choices=STATUSES, default="todo")
    sp.add_argument("--note")
    sp.add_argument("--json", action="store_true")

    sp = parser("ls", cmd_ls, "list follow-ups", aliases=["list"])
    sp.add_argument("--all", action="store_true", help="include done (they are kept until deleted)")
    sp.add_argument("--status", choices=STATUSES)
    sp.add_argument("--job", help="job name/id, or 'none'")
    sp.add_argument("--session", help="session id fragment, or 'none'")
    sp.add_argument("--agent", choices=AGENTS)
    sp.add_argument("--search", help="text in summary, why or notes")
    sp.add_argument("--idle", type=int, help="not worked on for at least N days")
    sp.add_argument("--recent", type=int, help="worked on within the last N days")
    sp.add_argument("--json", action="store_true")

    sp = parser("show", cmd_show, "show one follow-up")
    sp.add_argument("id")
    sp.add_argument("--json", action="store_true")

    sp = parser("edit", cmd_edit, "change fields")
    sp.add_argument("id")
    sp.add_argument("--summary")
    sp.add_argument("--why")
    sp.add_argument("--status", choices=STATUSES)
    sp.add_argument("--job", help="job name/id to file it under, or 'none'")
    sp.add_argument("--kind", choices=KINDS, help="kind if --job creates a new job")
    sp.add_argument("--agent", choices=AGENTS)
    sp.add_argument("--session-id")
    sp.add_argument("--cwd")
    sp.add_argument("--note")

    for name, fn, h in (
        ("touch", cmd_touch, "set last worked to today"),
        ("done", cmd_done, "mark done"),
        ("reopen", cmd_reopen, "move back to todo"),
    ):
        parser(name, fn, h).add_argument("id")

    sp = parser("rm", cmd_rm, "delete", aliases=["delete"])
    sp.add_argument("id")
    sp.add_argument("-y", "--yes", action="store_true")

    sp = parser("resume", cmd_resume, "restart the saved session")
    sp.add_argument("id")
    sp.add_argument("--print", action="store_true", help="print the command instead of running it")

    jp = sub.add_parser("job", help="manage jobs (" + ", ".join(KINDS) + ")")
    jsub = jp.add_subparsers(dest="jcmd", required=True)
    sp = parser("add", cmd_job_add, "create a job", parent=jsub)
    sp.add_argument("name", nargs="+")
    sp.add_argument("--kind", choices=KINDS, default=DEFAULT_KIND)
    sp.add_argument("--id", help="your own id for it, e.g. a Jira key (optional; ideas and btws rarely have one)")
    sp.add_argument("--parent", help="job this one belongs to, e.g. the epic of a story")
    sp.add_argument("--desc")
    sp = parser("ls", cmd_job_ls, "list jobs with counts", aliases=["list"], parent=jsub)
    sp.add_argument("--json", action="store_true")
    sp = parser("edit", cmd_job_edit, "rename or change a job", parent=jsub)
    sp.add_argument("ref", help="job name or id")
    sp.add_argument("--name")
    sp.add_argument("--kind", choices=KINDS)
    sp.add_argument("--id", help="your own id (pass '' to clear it)")
    sp.add_argument("--parent", help="parent job, or 'none'")
    sp.add_argument("--desc")
    sp = parser("rm", cmd_job_rm, "delete a job (its tasks are kept, unassigned)", aliases=["delete"], parent=jsub)
    sp.add_argument("ref")
    sp.add_argument("-y", "--yes", action="store_true")

    sp = parser("sessions", cmd_sessions, "list agent sessions that have tasks")
    sp.add_argument("--all", action="store_true")
    sp.add_argument("--json", action="store_true")
    sp = parser("tree", cmd_tree, "print jobs > sessions > tasks, and sessions > tasks")
    sp.add_argument("--all", action="store_true")

    sp = parser("skill", cmd_skill, "install the follow-ups skill for Claude Code / Copilot CLI")
    sp.add_argument("action", choices=("install", "path"))
    sp.add_argument("--target", choices=("claude", "copilot", "all"), default="all")
    sp.add_argument("--copy", action="store_true", help="copy the files instead of symlinking them")

    parser("path", cmd_path, "show data and config locations")
    sub.add_parser("tui", help="open the board (default)").set_defaults(fn=None)

    a = p.parse_args()
    if getattr(a, "fn", None):
        a.fn(a)
    elif sys.stdout.isatty():
        from fu.tui import run_tui  # lazy: plain CLI calls should not import Textual

        picked = run_tui()
        if picked:
            cmd_resume(argparse.Namespace(id=picked, print=False))
    else:
        cmd_ls(
            argparse.Namespace(
                all=False,
                status=None,
                job=None,
                session=None,
                agent=None,
                search=None,
                idle=None,
                recent=None,
                json=False,
            )
        )


if __name__ == "__main__":
    main()
