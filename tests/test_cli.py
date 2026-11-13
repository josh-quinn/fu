import json
import sys

import pytest

from fu import cli


def run(monkeypatch, capsys, *argv) -> str:
    monkeypatch.setattr(sys, "argv", ["fu", *argv])
    monkeypatch.setattr(sys.stdout, "isatty", lambda: False)
    cli.main()
    return capsys.readouterr().out


def test_add_reports_the_restart_command(monkeypatch, capsys):
    monkeypatch.setenv("CLAUDECODE", "1")
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "sess-1")
    out = run(monkeypatch, capsys, "add", "Fix gradient check", "--why", "layer 2 mismatch", "--cwd", "/w")
    assert "added #1" in out and "claude --resume sess-1" in out


def test_add_without_a_session_says_so(monkeypatch, capsys):
    out = run(monkeypatch, capsys, "add", "No session here")
    assert "no session id captured" in out


def test_add_creates_a_job_and_reuses_it_by_exact_name(monkeypatch, capsys):
    run(monkeypatch, capsys, "add", "one", "--job", "Report", "--kind", "epic")
    run(monkeypatch, capsys, "add", "two", "--job", "Report")
    jobs = json.loads(run(monkeypatch, capsys, "job", "ls", "--json"))
    assert len(jobs) == 1 and jobs[0]["kind"] == "epic" and jobs[0]["open"] == 2


def test_done_keeps_the_item_until_it_is_removed(monkeypatch, capsys):
    run(monkeypatch, capsys, "add", "finish me")
    assert "kept on the board" in run(monkeypatch, capsys, "done", "1")
    assert "finish me" not in run(monkeypatch, capsys, "ls")
    assert "finish me" in run(monkeypatch, capsys, "ls", "--all")
    run(monkeypatch, capsys, "rm", "1", "-y")
    assert "finish me" not in run(monkeypatch, capsys, "ls", "--all")


def test_ls_filters_combine(monkeypatch, capsys, seeded):
    out = json.loads(run(monkeypatch, capsys, "ls", "--job", "backprop", "--agent", "copilot", "--json"))
    assert [i["summary"] for i in out] == ["Vectorise softmax"]
    assert out[0]["job"] == "Backprop from scratch"


def test_a_new_job_defaults_to_a_story(monkeypatch, capsys):
    run(monkeypatch, capsys, "add", "one", "--job", "Something")
    assert json.loads(run(monkeypatch, capsys, "job", "ls", "--json"))[0]["kind"] == "story"


def test_old_kinds_are_no_longer_accepted(monkeypatch, capsys):
    with pytest.raises(SystemExit):
        run(monkeypatch, capsys, "job", "add", "x", "--kind", "misc")


def test_job_with_external_id_and_parent(monkeypatch, capsys):
    run(monkeypatch, capsys, "job", "add", "Backprop", "--kind", "epic", "--id", "ML-1")
    out = run(monkeypatch, capsys, "job", "add", "Gradient check", "--id", "ML-2", "--parent", "ML-1")
    assert "added job ML-2" in out
    rows = {r["ext_id"]: r for r in json.loads(run(monkeypatch, capsys, "job", "ls", "--json"))}
    assert rows["ML-2"]["parent_id"] == rows["ML-1"]["id"]
    listing = run(monkeypatch, capsys, "job", "ls")
    assert "ML-2" in listing and "PARENT" in listing


def test_a_task_can_be_filed_under_a_job_by_external_id(monkeypatch, capsys):
    run(monkeypatch, capsys, "job", "add", "Cache bug", "--kind", "bug", "--id", "OPS-9")
    run(monkeypatch, capsys, "add", "Reproduce", "--job", "OPS-9")
    assert json.loads(run(monkeypatch, capsys, "ls", "--job", "OPS-9", "--json"))[0]["job"] == "Cache bug"


def test_job_edit_sets_and_clears_id_and_parent(monkeypatch, capsys):
    run(monkeypatch, capsys, "job", "add", "Backprop", "--kind", "epic")
    run(monkeypatch, capsys, "job", "add", "Gradient check")
    run(monkeypatch, capsys, "job", "edit", "Gradient", "--id", "ML-2", "--parent", "Backprop")
    row = next(r for r in json.loads(run(monkeypatch, capsys, "job", "ls", "--json")) if r["ext_id"] == "ML-2")
    assert row["parent_id"] == 1
    run(monkeypatch, capsys, "job", "edit", "ML-2", "--id", "", "--parent", "none")
    row = next(r for r in json.loads(run(monkeypatch, capsys, "job", "ls", "--json")) if r["name"] == "Gradient check")
    assert row["ext_id"] == "" and row["parent_id"] is None


def test_a_job_cannot_become_its_own_ancestor(monkeypatch, capsys):
    run(monkeypatch, capsys, "job", "add", "Backprop", "--kind", "epic")
    run(monkeypatch, capsys, "job", "add", "Gradient check", "--parent", "Backprop")
    with pytest.raises(SystemExit, match="loop"):
        run(monkeypatch, capsys, "job", "edit", "Backprop", "--parent", "Gradient check")


def test_edit_job_none_unassigns(monkeypatch, capsys, seeded):
    run(monkeypatch, capsys, "edit", "1", "--job", "none")
    assert json.loads(run(monkeypatch, capsys, "show", "1", "--json"))["job"] is None


def test_deleting_a_job_keeps_its_tasks(monkeypatch, capsys, seeded):
    run(monkeypatch, capsys, "job", "rm", "backprop", "-y")
    out = json.loads(run(monkeypatch, capsys, "ls", "--job", "none", "--json"))
    assert {i["summary"] for i in out} == {"Write gradient check", "Vectorise softmax"}


def test_resume_print_does_not_exec(monkeypatch, capsys, seeded):
    out = run(monkeypatch, capsys, "resume", "1", "--print")
    assert out.strip() == "cd /w && claude --resume aaaa1111-0000-0000-0000-000000000001"


def test_resume_without_session_fails(monkeypatch, capsys, seeded):
    with pytest.raises(SystemExit, match="no session id"):
        run(monkeypatch, capsys, "resume", "4", "--print")


def test_tree_and_sessions_views(monkeypatch, capsys, seeded):
    tree = run(monkeypatch, capsys, "tree")
    assert "Backprop from scratch" in tree and "Sessions" in tree and "Tidy notes" not in tree
    sessions = json.loads(run(monkeypatch, capsys, "sessions", "--json"))
    assert sorted(s["tasks"] for s in sessions) == [1, 2]


def test_unknown_job_filter_is_an_error(monkeypatch, capsys, seeded):
    with pytest.raises(SystemExit, match="no job matching"):
        run(monkeypatch, capsys, "ls", "--job", "nonexistent")


def test_skill_install_links_into_both_agents(monkeypatch, capsys, isolated):
    out = run(monkeypatch, capsys, "skill", "install")
    for agent in (".claude", ".copilot"):
        dest = isolated / "home" / agent / "skills" / "follow-ups"
        assert dest.is_symlink() and (dest / "SKILL.md").exists()
    assert "claude:" in out and "copilot:" in out


def test_skill_install_copy_replaces_a_previous_link(monkeypatch, capsys, isolated):
    run(monkeypatch, capsys, "skill", "install", "--target", "claude")
    run(monkeypatch, capsys, "skill", "install", "--target", "claude", "--copy")
    dest = isolated / "home" / ".claude" / "skills" / "follow-ups"
    assert not dest.is_symlink() and (dest / "SKILL.md").exists()


def test_the_skill_is_packaged_with_the_library():
    from importlib.resources import files

    assert (files("fu") / "skills" / "follow-ups" / "SKILL.md").is_file()
