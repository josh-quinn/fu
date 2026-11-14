import shlex

import pytest

from fu import core, launch


@pytest.fixture
def db():
    db = core.load_db()
    epic = core.create_job(db, "Backprop", "epic", ext_id="ML-1", desc="Build backprop from scratch")
    epic["notes"] = "use float64"
    core.create_job(db, "Gradient check", "story", ext_id="ML-2", parent="ML-1", desc="Compare to numeric grads")
    core.new_item(db, "grads", job="ML-1", agent="claude", session_id="aaaa1111-x", cwd="/w")
    return db


def test_available_lists_only_what_the_job_has(db):
    epic = core.job_by_ref(db, "ML-1")
    assert launch.available(db, epic) == ["why", "notes", "tasks", "jobs", "sessions"]
    child = core.job_by_ref(db, "ML-2")
    assert launch.available(db, child) == ["why", "parent"]


def test_brief_has_only_the_ticked_sections(db):
    epic = core.job_by_ref(db, "ML-1")
    text = launch.brief(db, epic, ["why", "notes"])
    assert "Why: Build backprop from scratch" in text and "use float64" in text
    assert "## Child jobs" not in text and "## Earlier sessions" not in text and "## Open follow-ups" not in text


def test_brief_includes_the_parent_and_child_jobs_with_their_why(db):
    child = core.job_by_ref(db, "ML-2")
    assert "ML-1 · epic · Backprop" in launch.brief(db, child, ["parent"])
    text = launch.brief(db, core.job_by_ref(db, "ML-1"), ["jobs"])
    assert "## Child jobs" in text and "ML-2 · story · Gradient check" in text and "Compare to numeric grads" in text


def test_brief_lists_open_tasks_and_sessions_with_their_tasks(db):
    text = launch.brief(db, core.job_by_ref(db, "ML-1"), ["tasks", "sessions"])
    assert "#1 [todo] grads" in text
    assert "- claude aaaa1111" in text and "tasks: #1 grads (todo)" in text


def test_brief_keeps_only_the_picked_entries_of_a_section(db):
    epic = core.job_by_ref(db, "ML-1")
    core.create_job(db, "Softmax", "story", parent="ML-1")
    text = launch.brief(db, epic, ["jobs"], {"jobs": [str(core.job_by_ref(db, "Softmax")["id"])]})
    assert "Softmax" in text and "Gradient check" not in text


def test_brief_names_the_task_the_session_is_and_how_to_update_the_board(db):
    text = launch.brief(db, core.job_by_ref(db, "ML-1"), [], task_id=7)
    assert "task #7 of ML-1" in text and "fu add" in text and "--job ML-1" in text


def test_claude_gets_the_brief_as_a_system_prompt_file_and_the_prompt_as_the_first_message():
    cmd = launch.launch_cmd("claude", "u-1", "/my dir", "it's here", "/b/u-1.md", "ML-1 Backprop")
    assert shlex.split(cmd.split("&& ", 1)[1]) == [
        "claude", "--session-id", "u-1", "--name", "ML-1 Backprop",
        "--append-system-prompt-file", "/b/u-1.md", "it's here",
    ]  # fmt: skip
    assert cmd.startswith("cd '/my dir' && ")
    assert launch.first_message("claude", "BRIEF", "/jq-repo-setup go") == "/jq-repo-setup go"  # a skill still runs


def test_copilot_gets_the_brief_then_the_task_in_its_first_message():
    msg = launch.first_message("copilot", "BRIEF\n", "/jq-repo-setup harden it")
    assert msg.startswith("BRIEF") and msg.endswith("## Your task\nUse the jq-repo-setup skill. harden it")
    cmd = launch.launch_cmd("copilot", "u-2", "/w", "hi", "/b.md")
    assert shlex.split(cmd.split("&& ", 1)[1]) == ["copilot", "--session-id", "u-2", "-i", "hi"]


def test_an_empty_prompt_asks_the_session_to_orient_and_wait():
    assert launch.first_message("claude", "B", "  ") == launch.DEFAULT_TASK


def test_prepare_records_the_task_writes_the_brief_and_returns_the_command(db, tmp_path):
    core.save_db(db)
    epic = core.job_by_ref(db, "ML-1")
    cmd = launch.prepare(
        {"job_id": epic["id"], "agent": "claude", "cwd": str(tmp_path), "include": ["why"], "prompt": "hello"}
    )
    item = core.load_db()["items"][-1]
    assert (item["job_id"], item["agent"], item["status"], item["cwd"]) == (
        epic["id"],
        "claude",
        "doing",
        str(tmp_path),
    )
    assert item["summary"] == "hello"
    brief = launch.brief_path(item["session_id"])
    assert brief.exists() and f"task #{item['id']}" in brief.read_text()
    text = launch.brief(core.load_db(), epic, ["tasks", "sessions"], task_id=item["id"])
    assert "hello" not in text and item["session_id"][:8] not in text  # never lists itself as earlier work
    assert f"--session-id {item['session_id']}" in cmd and str(brief) in cmd and cmd.endswith(" hello")


def test_default_folder_prefers_the_job_home_then_a_parent_home_then_the_last_session(db, tmp_path):
    child = core.job_by_ref(db, "ML-2")
    assert launch.default_folder(db, child) == ""
    (tmp_path / "epic").mkdir()
    core.job_by_ref(db, "ML-1")["home"] = str(tmp_path / "epic")
    assert launch.default_folder(db, child) == str(tmp_path / "epic")
    assert launch.default_folder(db, child, include=[]) == ""  # the parent's home only when it is handed over
    (tmp_path / "own").mkdir()
    child["home"] = str(tmp_path / "own")
    assert launch.default_folder(db, child) == str(tmp_path / "own")


def test_prepare_resume_marks_the_task_doing_and_returns_its_command(db):
    core.save_db(db)
    assert launch.prepare_resume("1") == "cd /w && claude --resume aaaa1111-x"
    assert core.load_db()["items"][0]["status"] == "doing"


def test_no_message_means_no_prompt_argument():
    assert shlex.split(launch.launch_cmd("claude", "u", "/w", "").split("&& ", 1)[1]) == ["claude", "--session-id", "u"]


def test_unknown_agent_is_refused():
    with pytest.raises(ValueError):
        launch.launch_cmd("vim", "u", "/w", "")


def test_folder_suggestions_list_folders_only_hide_dotfolders_and_sort(tmp_path):
    for name in ("beta", "Alpha", ".hidden", "gamma"):
        (tmp_path / name).mkdir()
    (tmp_path / "file.txt").write_text("x")
    root = str(tmp_path) + "/"
    assert launch.folder_suggestions(root) == [root + "Alpha/", root + "beta/", root + "gamma/"]
    assert launch.folder_suggestions(root + ".") == [root + ".hidden/"]
    assert launch.folder_suggestions(root + "BE") == [root + "beta/"]
    assert launch.folder_suggestions(root + "nope") == []


def test_folder_suggestions_keep_the_tilde_as_typed(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    (tmp_path / "work").mkdir()
    assert launch.folder_suggestions("~") == ["~/"]
    assert launch.folder_suggestions("~/") == ["~/work/"]
    assert launch.folder_suggestions("~/w") == ["~/work/"]


def test_skill_suggestions_come_from_both_agents(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    for root, name in ((".claude/skills", "jq-repo-setup"), (".copilot/skills", "follow-ups")):
        d = tmp_path / root / name
        d.mkdir(parents=True)
        (d / "SKILL.md").write_text("x")
    nested = tmp_path / ".claude/skills/synced/bundle-1/skill-creator"
    nested.mkdir(parents=True)
    (nested / "SKILL.md").write_text("x")
    assert launch.skill_suggestions("") == [
        ("/follow-ups", "copilot"),
        ("/jq-repo-setup", "claude"),
        ("/skill-creator", "claude"),
    ]
    assert launch.skill_suggestions("/jq") == [("/jq-repo-setup", "claude")]
    assert launch.skill_suggestions("repo") == [("/jq-repo-setup", "claude")]


def test_path_suggestions_can_include_files_after_folders(tmp_path):
    (tmp_path / "b-dir").mkdir()
    (tmp_path / "a.md").write_text("x")
    root = str(tmp_path) + "/"
    assert launch.path_suggestions(root, files=True) == [(root + "b-dir/", "folder"), (root + "a.md", "file")]
