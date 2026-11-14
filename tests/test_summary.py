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
    e = summary.build(db, epic)
    assert "Build backprop from scratch" in texts(e, "action") and keys(e)[0] == "why"  # enter edits it
    story = core.job_by_ref(db, "ML-2")
    assert "layer 2 mismatch" in texts(summary.build(db, story), "action")


def test_several_child_jobs_get_a_heading_and_a_line_each(board):
    db, epic = board
    e = summary.build(db, epic)
    assert "Jobs" in texts(e, "head")
    assert texts(e, "action")[1:3] == ["ML-2: story Gradient check (done)", "ML-3: story Softmax (todo)"]
    assert keys(e)[1:3] == [f"job:{core.job_by_ref(db, r)['id']}" for r in ("ML-2", "ML-3")]


def test_a_lone_child_job_still_sits_under_the_jobs_heading(board):
    db, epic = board
    core.remove_job(db, core.job_by_ref(db, "ML-3"))
    e = summary.build(db, epic)
    assert "Jobs" in texts(e, "head")
    assert "ML-2: story Gradient check (done)" in texts(e)


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


def test_a_lone_session_still_sits_under_the_sessions_heading(board):
    db, _ = board
    story = core.job_by_ref(db, "ML-2")
    core.new_item(db, "more", job="ML-2", agent="claude", session_id="cccc3333-z", cwd="/w")
    e = summary.build(db, story)
    assert "Sessions" in texts(e, "head")
    assert "claude cccc3333 · w" in texts(e)


def test_a_job_without_children_or_sessions_omits_those_sections(isolated):
    db = core.load_db()
    job = core.create_job(db, "Cheatsheet", "btw")
    e = summary.build(db, job)
    assert not {"Jobs", "Sessions"} & set(texts(e, "head"))
    assert keys(e) == ["why", "artifacts", "notes"]  # nothing to jump to; outputs can still be added
    assert "none yet · enter to add one" in texts(e)


def test_there_is_no_restart_entry_since_the_sessions_list_covers_it(board):
    db, epic = board
    e = summary.build(db, epic)
    assert "restart" not in keys(e) and "Restart" not in texts(e, "head")


def test_a_child_lists_its_parent_first_so_climbing_back_is_one_step(board):
    db, epic = board
    story = core.job_by_ref(db, "ML-2")
    e = summary.build(db, story)
    assert texts(e, "head")[:2] == ["Why", "Parent"]
    assert keys(e)[1] == f"job:{epic['id']}"
    assert texts(e, "action")[1] == f"{core.job_label(epic)}: epic Backprop (doing)"


def test_a_job_without_a_parent_has_no_parent_heading(board):
    db, epic = board
    assert "Parent" not in texts(summary.build(db, epic), "head")


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


def test_a_removed_output_goes_and_stays_gone_until_added_again(board, isolated):
    db, epic = board
    note = isolated / "runbook.md"
    note.write_text("x")
    artifacts.add_manual(next(i for i in db["items"] if i["summary"] == "grads"), str(note))
    path = str(note)
    summary.remove_job_artifact(db, epic, path)
    assert path not in [a["path"] for a in summary.job_artifacts(db, epic)]
    artifacts.add_manual(epic, path)
    assert path in [a["path"] for a in summary.job_artifacts(db, epic)]


def test_artifacts_added_to_a_job_by_hand_are_listed_and_can_be_taken_back(isolated):
    note = isolated / "cheats.md"
    note.write_text("x")
    db = core.load_db()
    job = core.create_job(db, "Cheatsheet", "btw")
    artifacts.add_manual(job, str(note))
    assert [a["path"] for a in summary.job_artifacts(db, job)] == [str(note)]
    artifacts.remove(job, str(note))
    assert summary.job_artifacts(db, job) == []


def test_the_board_panel_for_a_task_links_its_job_session_artifacts_and_notes(board):
    db, epic = board
    item = next(i for i in db["items"] if i.get("session_id"))
    e = summary.build_item(db, item)
    assert keys(e)[0] == "why" and keys(e)[1].startswith("job:") and keys(e)[2].startswith("session:")
    assert keys(e)[-2:] == ["artifacts", "notes"]
    assert "Session" in texts(e, "head") and not any("--resume" in t for t in texts(e))  # no command, just the line


def test_a_jobs_panel_lists_its_open_follow_ups_and_counts_the_done_ones(board):
    db, epic = board
    e = summary.build(db, epic)
    assert "Follow-ups" in texts(e, "head")
    assert [k for k in keys(e) if k.startswith("item:")] == ["item:1", "item:2"]
    child = core.job_by_ref(db, "ML-2")
    assert "Follow-ups  (1 done)" in texts(summary.build(db, child), "head")
