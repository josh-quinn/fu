import json
from pathlib import Path

import pytest

from fu import artifacts, core, summary


@pytest.fixture(autouse=True)
def tests_live_in_a_temp_dir(monkeypatch):
    # pytest's folders are under /var/folders, a scratch location the detection ignores by design
    monkeypatch.setattr(artifacts, "SCRATCH", ("/scratchpad/", "/node_modules/", "/.git/"))


def claude_transcript(home: Path, sid: str, title: str | None, *written: str) -> None:
    lines = [
        {
            "type": "assistant",
            "message": {"content": [{"type": "tool_use", "name": "Write", "input": {"file_path": w}}]},
        }
        for w in written
    ]
    if title:
        lines.append({"type": "ai-title", "aiTitle": title, "sessionId": sid})
    f = home / ".claude" / "projects" / "p" / f"{sid}.jsonl"
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text("\n".join(json.dumps(x) for x in lines))


def texts(entries, style=None):
    return [e["text"] for e in entries if style is None or e["style"] == style]


def keys(entries):
    return [e["key"] for e in entries if e["key"]]


@pytest.fixture
def board(isolated):
    """An epic with two stories, spread over two sessions; one story has no session."""
    db = core.load_db()
    epic = core.create_job(db, "Backprop", "epic", ext_id="ML-1", desc="Build backprop from scratch")
    core.create_job(db, "Gradient check", "story", ext_id="ML-2", parent="ML-1")
    core.create_job(db, "Softmax", "story", ext_id="ML-3", parent="ML-1")
    core.new_item(
        db,
        "grads",
        job="ML-1",
        agent="claude",
        session_id="aaaa1111-x",
        cwd="/w",
        status="doing",
        last_worked="2026-11-10",
    )
    core.new_item(
        db, "softmax", job="ML-1", agent="copilot", session_id="bbbb2222-y", cwd="/d", last_worked="2026-11-12"
    )
    core.new_item(db, "check", job="ML-2", why="layer 2 mismatch", status="done")
    return db, epic


def test_header_lines_name_the_job_its_id_type_and_parent(board):
    db, _ = board
    story = core.job_by_ref(db, "ML-2")
    entries = summary.build(db, story)
    assert texts(entries, "title") == ["❖ Gradient check"]
    assert texts(entries, "meta") == ["ML-2 · story · under Backprop"]


def test_why_is_the_job_description_else_the_latest_tasks_why(board):
    db, epic = board
    assert "Build backprop from scratch" in texts(summary.build(db, epic), "text")
    story = core.job_by_ref(db, "ML-2")
    assert "layer 2 mismatch" in texts(summary.build(db, story), "text")


def test_several_child_jobs_get_a_heading_and_a_line_each(board):
    db, epic = board
    e = summary.build(db, epic)
    assert "Jobs" in texts(e, "head")
    assert texts(e, "action")[:2] == ["ML-2: story Gradient check (done)", "ML-3: story Softmax (todo)"]
    assert keys(e)[:2] == [f"job:{core.job_by_ref(db, r)['id']}" for r in ("ML-2", "ML-3")]


def test_a_lone_child_job_shares_a_line_with_its_label(board):
    db, epic = board
    core.remove_job(db, core.job_by_ref(db, "ML-3"))
    e = summary.build(db, epic)
    assert "Jobs" not in texts(e, "head")
    assert "Job  ML-2: story Gradient check (done)" in texts(e)


def test_several_sessions_get_a_heading_most_recent_first(board, isolated):
    db, epic = board
    claude_transcript(isolated / "home", "aaaa1111-x", "Fix the gradients")
    e = summary.build(db, epic)
    assert "Sessions" in texts(e, "head")
    lines = [t for t in texts(e, "action") if t.startswith(("claude", "copilot"))]
    assert lines == [
        "copilot bbbb2222 · d",
        "claude aaaa1111 · Fix the gradients",
    ]  # folder name stands in for a missing title


def test_a_lone_session_shares_a_line_with_its_label(board):
    db, _ = board
    story = core.job_by_ref(db, "ML-2")
    core.new_item(db, "more", job="ML-2", agent="claude", session_id="cccc3333-z", cwd="/w")
    e = summary.build(db, story)
    assert "Sessions" not in texts(e, "head")
    assert "Session  claude cccc3333 · w" in texts(e)


def test_a_job_without_children_or_sessions_omits_those_sections(isolated):
    db = core.load_db()
    job = core.create_job(db, "Cheatsheet", "btw")
    e = summary.build(db, job)
    assert not {"Jobs", "Sessions"} & set(texts(e, "head"))
    assert keys(e) == ["notes"]  # nothing to restart, nothing to open
    assert "no session id captured" in texts(e) and "none yet" in texts(e)


def test_restart_shows_the_command_for_the_latest_session(board):
    db, epic = board
    e = summary.build(db, epic)
    assert "cd /d && copilot --resume=bbbb2222-y" in texts(e)
    assert "restart" in keys(e)


def test_artifacts_collect_across_every_task_each_path_once(board, isolated):
    db, epic = board
    doc = isolated / "notes" / "runbook.md"
    doc.parent.mkdir(parents=True)
    doc.write_text("x")
    claude_transcript(isolated / "home", "aaaa1111-x", None, str(doc))
    core.new_item(db, "again", job="ML-1", agent="claude", session_id="aaaa1111-x")  # same session, same doc
    arts = summary.job_artifacts(db, epic)
    assert [a["path"] for a in arts] == [str(doc)]
    e = summary.build(db, epic)
    assert "1 to open" in texts(e) and "artifacts" in keys(e)


def test_notes_show_the_text_or_an_invitation(board):
    db, epic = board
    assert "Enter to add a note" in texts(summary.build(db, epic))
    epic["notes"] = "ask about the ReLU edge case"
    assert "ask about the ReLU edge case" in texts(summary.build(db, epic))


def test_session_target_is_that_sessions_latest_task(board):
    db, epic = board
    core.new_item(db, "later", job="ML-1", agent="claude", session_id="aaaa1111-x", last_worked="2026-11-11")
    assert summary.session_target(db, epic, "claude:aaaa1111-x")["summary"] == "later"
    assert summary.session_target(db, epic, "claude:nope") is None


class TestJobStatus:
    def test_doing_if_any_task_is(self, board):
        assert core.job_status(*board) == "doing"

    def test_done_only_when_every_task_is(self, board):
        db, _ = board
        assert core.job_status(db, core.job_by_ref(db, "ML-2")) == "done"

    def test_todo_with_no_tasks(self, board):
        db, _ = board
        assert core.job_status(db, core.job_by_ref(db, "ML-3")) == "todo"


def test_open_path_uses_the_systems_opener(monkeypatch):
    calls = []
    monkeypatch.setattr(artifacts.subprocess, "Popen", lambda cmd, **kw: calls.append(cmd))
    assert artifacts.open_path("/a/runbook.md") is True
    assert calls[0][-1] == "/a/runbook.md" and calls[0][0] in ("open", "xdg-open")


def test_open_path_reports_failure_instead_of_raising(monkeypatch):
    def boom(*a, **k):
        raise OSError("no opener")

    monkeypatch.setattr(artifacts.subprocess, "Popen", boom)
    assert artifacts.open_path("/a/x.md") is False
