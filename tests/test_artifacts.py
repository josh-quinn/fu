import json
from pathlib import Path

import pytest

from fu import artifacts, core


def touch(path: Path, text: str = "x") -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    return str(path)


def claude_session(home: Path, sid: str, *tool_calls: tuple[str, dict], title: str | None = None) -> None:
    lines = [{"type": "user", "message": {"content": "hi"}}]
    for name, inp in tool_calls:
        lines.append({"type": "assistant", "message": {"content": [{"type": "tool_use", "name": name, "input": inp}]}})
    if title:
        lines.append({"type": "ai-title", "aiTitle": title, "sessionId": sid})
    touch(home / ".claude" / "projects" / "proj" / f"{sid}.jsonl", "\n".join(json.dumps(r) for r in lines))


@pytest.fixture
def home(isolated):
    return isolated / "home"


@pytest.fixture(autouse=True)
def tests_live_in_a_temp_dir(monkeypatch, request):
    """pytest's folders are under /var/folders, which is a scratch location the detection ignores by
    design. Keep that rule off for the tests that are about something else."""
    if "default_scratch_rules" not in request.keywords:
        monkeypatch.setattr(artifacts, "SCRATCH", ("/scratchpad/", "/node_modules/", "/.git/"))


class TestReadingClaude:
    def test_collects_every_writing_tool_once_and_ignores_the_rest(self, home):
        claude_session(
            home,
            "s1",
            ("Write", {"file_path": "/a/runbook.md", "content": "x"}),
            ("Edit", {"file_path": "/a/runbook.md", "old_string": "a", "new_string": "b"}),
            ("NotebookEdit", {"notebook_path": "/a/explain.ipynb"}),
            ("Bash", {"command": "touch /a/not-recorded.md"}),
            ("Read", {"file_path": "/a/only-read.md"}),
        )
        assert artifacts.written_paths("claude", "s1") == ["/a/runbook.md", "/a/explain.ipynb"]

    def test_unknown_session_or_agent_yields_nothing(self, home):
        assert artifacts.written_paths("claude", "nope") == []
        assert artifacts.written_paths(None, "s1") == []
        assert artifacts.written_paths("claude", None) == []

    def test_title_is_the_last_one_the_agent_gave(self, home):
        claude_session(home, "s1", title="Follow-up task board skill")
        assert artifacts.session_title("claude", "s1") == "Follow-up task board skill"
        assert artifacts.session_title("claude", "missing") == ""


class TestReadingCopilot:
    def make(self, isolated, sid="c1", events=(), name=None):
        root = isolated / "copilot-sessions" / sid
        lines = [{"type": "tool.execution_start", "data": {"toolName": t, "arguments": a}} for t, a in events]
        touch(root / "events.jsonl", "\n".join(json.dumps(r) for r in lines))
        if name:
            touch(root / "workspace.yaml", f"id: {sid}\nname: {name}\n")
        return root

    def test_patches_edits_and_the_sessions_own_files_folder(self, isolated):
        root = self.make(
            isolated,
            events=[
                ("apply_patch", "*** Begin Patch\n*** Add File: /d/new.md\n+hi\n*** Update File: /d/old.md\n"),
                ("edit", {"path": "/d/edited.md"}),
                ("bash", {"command": "ls"}),
                ("view", {"path": "/d/only-viewed.md"}),
            ],
        )
        saved = touch(root / "files" / "plan.md")
        touch(root / "research" / "notes" / "a.md")
        got = artifacts.written_paths("copilot", "c1")
        assert got[:3] == ["/d/new.md", "/d/old.md", "/d/edited.md"]
        assert saved in got and str(root / "research" / "notes" / "a.md") in got
        assert "/d/only-viewed.md" not in got

    def test_title_comes_from_the_workspace_name(self, isolated):
        self.make(isolated, name="Split Ghosty Terminal")
        assert artifacts.session_title("copilot", "c1") == "Split Ghosty Terminal"


class TestClassify:
    def test_documents_outside_a_repo_are_listed_one_by_one(self, isolated):
        a = touch(isolated / "notes" / "runbook.md")
        b = touch(isolated / "notes" / "review.html")
        out = artifacts.classify([a, b])
        assert [(x["kind"], x["label"]) for x in out] == [("doc", "runbook.md"), ("doc", "review.html")]

    def test_building_a_tool_in_a_repo_lists_the_repo_once_not_every_file(self, isolated):
        repo = isolated / "repos" / "fu"
        (repo / ".git").mkdir(parents=True)
        files = [touch(repo / "src" / f"m{n}.py") for n in range(12)] + [touch(repo / "README.md")]
        out = artifacts.classify(files)
        assert out == [{"path": str(repo), "kind": "repo", "label": "fu"}]

    def test_a_skill_is_one_entry_whatever_files_inside_it_were_written(self, isolated):
        base = isolated / "home" / ".claude" / "skills" / "follow-ups"
        out = artifacts.classify([touch(base / "SKILL.md"), touch(base / "evals" / "a" / "case.yaml")])
        assert out == [{"path": str(base), "kind": "skill", "label": "follow-ups"}]

    def test_copilot_skills_count_too(self, isolated):
        base = isolated / "home" / ".copilot" / "skills" / "debug"
        assert artifacts.classify([touch(base / "SKILL.md")])[0]["kind"] == "skill"

    def test_scratch_caches_lockfiles_and_vanished_files_are_ignored(self, isolated):
        keep = touch(isolated / "notes" / "keep.md")
        junk = [
            touch(isolated / "x" / "scratchpad" / "tmp.md"),
            touch(isolated / "p" / "__pycache__" / "m.pyc"),
            touch(isolated / "p" / "node_modules" / "pkg" / "readme.md"),
            touch(isolated / "p" / "uv.lock"),
            str(isolated / "deleted.md"),
        ]
        assert [a["path"] for a in artifacts.classify([*junk, keep])] == [keep]

    @pytest.mark.default_scratch_rules
    def test_files_in_the_systems_temp_folders_are_ignored(self, isolated):
        # the real default rules: pytest's own folder is under /var/folders, a temp location
        assert artifacts.classify([touch(isolated / "notes" / "scratch.md")]) == []

    def test_a_loose_script_outside_any_repo_is_a_file(self, isolated):
        out = artifacts.classify([touch(isolated / "bin" / "tool.sh")])
        assert out[0]["kind"] == "file"


class TestItems:
    def item(self, home, written=("/a",)):
        claude_session(home, "s1", *[("Write", {"file_path": w}) for w in written])
        return {"agent": "claude", "session_id": "s1"}

    def test_detected_artifacts_come_from_the_session(self, home, isolated):
        doc = touch(isolated / "notes" / "runbook.md")
        item = self.item(home, [doc])
        assert [a["path"] for a in artifacts.item_artifacts(item)] == [doc]

    def test_manual_artifacts_are_added_and_win_over_detected_ones(self, home, isolated):
        doc = touch(isolated / "notes" / "runbook.md")
        item = self.item(home, [doc])
        artifacts.add_manual(item, doc, "Prod runbook")
        out = artifacts.item_artifacts(item)
        assert len(out) == 1 and out[0]["label"] == "Prod runbook" and out[0]["source"] == "manual"

    def test_dismissed_artifacts_stay_hidden_and_adding_them_back_restores_them(self, home, isolated):
        doc = touch(isolated / "notes" / "runbook.md")
        item = self.item(home, [doc])
        artifacts.dismiss(item, doc)
        assert artifacts.item_artifacts(item) == []
        artifacts.add_manual(item, doc)
        assert [a["path"] for a in artifacts.item_artifacts(item)] == [doc]

    def test_the_snapshot_survives_the_transcript_being_deleted(self, home, isolated):
        doc = touch(isolated / "notes" / "runbook.md")
        item = self.item(home, [doc])
        artifacts.snapshot(item)
        (home / ".claude" / "projects" / "proj" / "s1.jsonl").unlink()
        artifacts._cache.clear()
        assert [a["path"] for a in artifacts.item_artifacts(item)] == [doc]

    def test_a_manual_directory_that_is_a_repo_is_labelled_a_repo(self, isolated):
        repo = isolated / "repos" / "tool"
        (repo / ".git").mkdir(parents=True)
        item: dict = {}
        assert artifacts.add_manual(item, str(repo))["kind"] == "repo"

    def test_an_item_with_no_session_still_has_its_manual_ones(self, isolated):
        item: dict = {"agent": None, "session_id": None}
        artifacts.add_manual(item, str(touch(isolated / "x.md")))
        assert len(artifacts.item_artifacts(item)) == 1


def test_core_items_start_without_artifacts():
    db = core.load_db()
    item = core.new_item(db, "x")
    assert artifacts.item_artifacts(item) == []
