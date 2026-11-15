import json
import sys

import pytest

from fu import cli, core


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


def test_a_type_of_your_own_is_kept_and_offered_next_time(monkeypatch, capsys):
    run(monkeypatch, capsys, "job", "add", "x", "--kind", "chore")
    assert "chore" in core.job_types(core.load_db())


def test_a_job_without_a_jira_key_takes_a_project_by_hand(monkeypatch, capsys):
    run(monkeypatch, capsys, "job", "add", "Dashboards", "--project", "OPS")
    run(monkeypatch, capsys, "job", "add", "Backprop", "--id", "ML-4", "--project", "IGNORED")
    jobs = {j["name"]: j for j in core.load_db()["jobs"]}
    assert core.project_of(jobs["Dashboards"]) == "OPS" and core.project_of(jobs["Backprop"]) == "ML"


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


def make_doc(tmp_path, name="runbook.md") -> str:
    doc = tmp_path / "notes" / name
    doc.parent.mkdir(parents=True, exist_ok=True)
    doc.write_text("# how to")
    return str(doc)


def claude_wrote(tmp_path, sid: str, *paths: str) -> None:
    import json as _json

    calls = [
        {
            "type": "assistant",
            "message": {"content": [{"type": "tool_use", "name": "Write", "input": {"file_path": p}}]},
        }
        for p in paths
    ]
    f = tmp_path / "home" / ".claude" / "projects" / "proj" / f"{sid}.jsonl"
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text("\n".join(_json.dumps(c) for c in calls))


@pytest.fixture
def relaxed_scratch(monkeypatch):
    # pytest's temp folder is under /var/folders, which the detection ignores by design
    from fu import artifacts

    monkeypatch.setattr(artifacts, "SCRATCH", ("/scratchpad/", "/node_modules/", "/.git/"))


def test_add_with_an_artifact_stores_it_with_the_label(monkeypatch, capsys, tmp_path, relaxed_scratch):
    doc = make_doc(tmp_path)
    run(monkeypatch, capsys, "add", "Write the runbook", "--artifact", doc, "--label", "Prod runbook")
    shown = json.loads(run(monkeypatch, capsys, "show", "1", "--json"))
    assert [(a["label"], a["source"]) for a in shown["artifacts"]] == [("Prod runbook", "manual")]


def test_a_label_needs_exactly_one_artifact(monkeypatch, capsys, tmp_path):
    with pytest.raises(SystemExit, match="--label"):
        run(monkeypatch, capsys, "add", "x", "--label", "orphan label")


def test_show_lists_the_artifacts_the_session_left_behind(monkeypatch, capsys, tmp_path, relaxed_scratch):
    doc = make_doc(tmp_path)
    claude_wrote(tmp_path, "sess-9", doc)
    monkeypatch.setenv("CLAUDECODE", "1")
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "sess-9")
    run(monkeypatch, capsys, "add", "Debug the cache")
    out = run(monkeypatch, capsys, "show", "1")
    assert "artifacts" in out and "doc" in out and "runbook.md" in out and doc in out


def test_dismissing_a_wrongly_detected_artifact_hides_it_for_good(monkeypatch, capsys, tmp_path, relaxed_scratch):
    doc = make_doc(tmp_path)
    claude_wrote(tmp_path, "sess-9", doc)
    monkeypatch.setenv("CLAUDECODE", "1")
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "sess-9")
    run(monkeypatch, capsys, "add", "Debug the cache")
    run(monkeypatch, capsys, "edit", "1", "--dismiss-artifact", doc)
    run(monkeypatch, capsys, "touch", "1")  # re-detects; the dismissal must stick
    assert json.loads(run(monkeypatch, capsys, "show", "1", "--json"))["artifacts"] == []


def test_done_snapshots_the_artifacts_so_they_outlive_the_transcript(monkeypatch, capsys, tmp_path, relaxed_scratch):
    doc = make_doc(tmp_path)
    claude_wrote(tmp_path, "sess-9", doc)
    monkeypatch.setenv("CLAUDECODE", "1")
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "sess-9")
    run(monkeypatch, capsys, "add", "Debug the cache")
    run(monkeypatch, capsys, "done", "1")
    (tmp_path / "home" / ".claude" / "projects" / "proj" / "sess-9.jsonl").unlink()
    from fu import artifacts

    artifacts._cache.clear()
    assert [a["path"] for a in json.loads(run(monkeypatch, capsys, "show", "1", "--json"))["artifacts"]] == [doc]


def test_show_prints_the_session_title(monkeypatch, capsys, tmp_path):
    import json as _json

    f = tmp_path / "home" / ".claude" / "projects" / "proj" / "sess-9.jsonl"
    f.parent.mkdir(parents=True)
    f.write_text(_json.dumps({"type": "ai-title", "aiTitle": "Fix the cache bug", "sessionId": "sess-9"}))
    monkeypatch.setenv("CLAUDECODE", "1")
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "sess-9")
    run(monkeypatch, capsys, "add", "Debug the cache")
    assert "Fix the cache bug" in run(monkeypatch, capsys, "show", "1")


def test_job_notes_can_be_set_and_cleared_from_the_cli(monkeypatch, capsys):
    run(monkeypatch, capsys, "job", "add", "Cheatsheet", "--kind", "btw")
    run(monkeypatch, capsys, "job", "edit", "Cheatsheet", "--notes", "add the p99 query")
    assert json.loads(run(monkeypatch, capsys, "job", "ls", "--json"))[0]["notes"] == "add the p99 query"
    run(monkeypatch, capsys, "job", "edit", "Cheatsheet", "--notes", "")
    assert json.loads(run(monkeypatch, capsys, "job", "ls", "--json"))[0]["notes"] == ""


def test_job_add_and_edit_set_the_home_folder(monkeypatch, capsys, tmp_path):
    run(monkeypatch, capsys, "job", "add", "Homed", "--home", str(tmp_path))
    assert core.load_db()["jobs"][0]["home"] == str(tmp_path.resolve())
    run(monkeypatch, capsys, "job", "edit", "Homed", "--home", "")
    assert core.load_db()["jobs"][0]["home"] == ""


def test_a_follow_up_parked_mid_session_lands_on_that_sessions_job(monkeypatch, capsys):
    monkeypatch.setenv("CLAUDECODE", "1")
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "sess-9")
    run(monkeypatch, capsys, "add", "design the loss", "--job", "Backprop")
    out = run(monkeypatch, capsys, "add", "idea: cache activations")
    assert "the job this session is on" in out and "--no-job" in out
    out = run(monkeypatch, capsys, "add", "idea: unrelated tool", "--no-job")
    items = core.load_db()["items"]
    assert [i["job_id"] for i in items] == [1, 1, None]


def test_outside_a_known_session_the_folder_picks_the_job_by_its_home(monkeypatch, capsys, tmp_path):
    (tmp_path / "repo" / "src").mkdir(parents=True)
    run(monkeypatch, capsys, "job", "add", "Backprop", "--home", str(tmp_path / "repo"))
    run(monkeypatch, capsys, "add", "idea", "--cwd", str(tmp_path / "repo" / "src"))
    run(monkeypatch, capsys, "add", "elsewhere", "--cwd", str(tmp_path))
    assert [i["job_id"] for i in core.load_db()["items"]] == [1, None]


def test_install_skill_flag_links_the_skill_for_both_agents(monkeypatch, capsys, isolated):
    out = run(monkeypatch, capsys, "--install-skill")
    for agent in (".claude", ".copilot"):
        link = isolated / "home" / agent / "skills" / "follow-ups"
        assert link.is_symlink() and (link / "SKILL.md").exists()
    assert "claude:" in out and "copilot:" in out


def test_a_homebrew_install_links_the_skill_through_opt_so_upgrades_keep_it(tmp_path):
    cellar = tmp_path / "Cellar" / "fu" / "0.1.0" / "libexec" / "skills"
    opt = tmp_path / "opt" / "fu" / "libexec" / "skills"
    cellar.mkdir(parents=True)
    opt.mkdir(parents=True)
    assert cli.stable_path(cellar) == opt
    assert cli.stable_path(tmp_path / "elsewhere") == tmp_path / "elsewhere"


@pytest.mark.parametrize("bad", ["../../etc", "a b", "$(id)", "x;rm", "*"])
def test_a_session_id_outside_the_allowlist_is_rejected(monkeypatch, capsys, bad):
    with pytest.raises(SystemExit) as exit_:
        run(monkeypatch, capsys, "add", "idea", "--agent", "copilot", "--session-id", bad)
    assert exit_.value.code == 2 and "session id" in capsys.readouterr().err
    run(monkeypatch, capsys, "add", "idea")
    with pytest.raises(SystemExit):
        run(monkeypatch, capsys, "edit", "1", "--session-id", bad)


def test_real_session_ids_are_accepted(monkeypatch, capsys):
    out = run(
        monkeypatch, capsys, "add", "idea", "--agent", "claude", "--session-id", "eb77028c-f64a-44d9-8b7d-1ff00935014c"
    )
    assert "claude --resume eb77028c-f64a-44d9-8b7d-1ff00935014c" in out
