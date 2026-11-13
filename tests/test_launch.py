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
    assert launch.available(db, epic) == ["why", "notes", "jobs", "sessions"]
    child = core.job_by_ref(db, "ML-2")
    assert launch.available(db, child) == ["why", "parent"]


def test_context_has_only_the_ticked_sections(db):
    epic = core.job_by_ref(db, "ML-1")
    text = launch.context_text(db, epic, ["why", "notes"])
    assert "Why: Build backprop from scratch" in text and "Notes: use float64" in text
    assert "Child jobs" not in text and "Earlier sessions" not in text


def test_context_includes_the_parent_and_child_jobs_with_their_why(db):
    child = core.job_by_ref(db, "ML-2")
    assert "ML-1: epic Backprop" in launch.context_text(db, child, ["parent"])
    epic = core.job_by_ref(db, "ML-1")
    text = launch.context_text(db, epic, ["jobs"])
    assert "ML-2: story Gradient check" in text and "Compare to numeric grads" in text


def test_nothing_ticked_means_no_context(db):
    assert launch.context_text(db, core.job_by_ref(db, "ML-1"), []) == ""
    assert launch.full_prompt(db, core.job_by_ref(db, "ML-1"), [], "  just do it ") == "just do it"


def test_full_prompt_puts_context_before_the_users_prompt(db):
    out = launch.full_prompt(db, core.job_by_ref(db, "ML-1"), ["why"], "start with the loss")
    assert out.index("Why:") < out.index("start with the loss")


def test_claude_launch_command_sets_the_session_id_and_passes_the_prompt(db):
    cmd = launch.launch_cmd("claude", "u-1", "/my dir", "it's here")
    assert shlex.split(cmd.split("&& ", 1)[1]) == ["claude", "--session-id", "u-1", "it's here"]
    assert cmd.startswith("cd '/my dir' && ")


def test_copilot_launch_command_uses_interactive_prompt_flag():
    cmd = launch.launch_cmd("copilot", "u-2", "/w", "hi")
    assert shlex.split(cmd.split("&& ", 1)[1]) == ["copilot", "--session-id", "u-2", "-i", "hi"]


def test_no_prompt_means_no_prompt_argument():
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
    assert launch.skill_suggestions("") == ["/follow-ups", "/jq-repo-setup"]
    assert launch.skill_suggestions("/jq") == ["/jq-repo-setup"]
    assert launch.skill_suggestions("repo") == ["/jq-repo-setup"]
