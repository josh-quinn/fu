import json
from datetime import date, timedelta

import pytest

from fu import core


def days_ago(n: int) -> str:
    return (date.today() - timedelta(days=n)).isoformat()


class TestStorage:
    def test_missing_board_is_empty(self):
        assert core.load_db() == {"items": [], "jobs": []}

    def test_board_written_before_jobs_existed_still_loads(self):
        core.data_dir().mkdir(parents=True)
        (core.data_dir() / "board.json").write_text(json.dumps({"items": [{"id": 1, "summary": "old"}]}))
        db = core.load_db()
        assert db["jobs"] == []
        assert db["items"][0]["summary"] == "old"

    def test_save_writes_json_and_markdown(self):
        db = core.load_db()
        core.new_item(db, "Fix thing", why="because", agent="claude", session_id="abc", cwd="/w")
        core.save_db(db)
        assert core.load_db()["items"][0]["summary"] == "Fix thing"
        md = (core.data_dir() / "BOARD.md").read_text()
        assert "Fix thing" in md and "claude --resume abc" in md

    def test_done_items_survive_save_and_reload(self):
        db = core.load_db()
        item = core.new_item(db, "Finish me")
        core.save_db(db)
        core.update(str(item["id"]), status="done")
        assert core.load_db()["items"][0]["status"] == "done"


class TestJobs:
    def test_legacy_kinds_and_missing_fields_are_upgraded_on_load(self):
        path = core.data_dir()
        path.mkdir(parents=True)
        legacy = {"items": [], "jobs": [{"id": 1, "name": "a", "kind": "misc"}, {"id": 2, "name": "b", "kind": "task"}]}
        (path / "board.json").write_text(json.dumps(legacy))
        jobs = core.load_db()["jobs"]
        assert [j["kind"] for j in jobs] == ["btw", "story"]
        assert all(j["ext_id"] == "" and j["parent_id"] is None for j in jobs)

    def test_lookup_by_id_prefixed_id_exact_and_unique_substring(self, seeded):
        assert core.job_by_ref(seeded, "1")["name"] == "Backprop from scratch"
        assert core.job_by_ref(seeded, "J2")["name"] == "ReLU derivative bug"
        assert core.job_by_ref(seeded, "relu derivative bug")["id"] == 2
        assert core.job_by_ref(seeded, "backprop")["id"] == 1

    def test_ambiguous_substring_matches_nothing(self, seeded):
        core.ensure_job(seeded, "Backprop tidy-up")
        assert core.job_by_ref(seeded, "backprop") is None

    def test_creating_never_attaches_to_a_similarly_named_job(self, seeded):
        # "ReLU" is a substring of an existing job but is a different piece of work
        job = core.ensure_job(seeded, "ReLU", "spike")
        assert job["id"] == 3 and job["kind"] == "spike"

    def test_exact_name_reuses_the_job(self, seeded):
        assert core.ensure_job(seeded, "Backprop from scratch")["id"] == 1

    def test_set_job_none_unassigns(self, seeded):
        item = seeded["items"][0]
        core.set_job(seeded, item, "none")
        assert item["job_id"] is None


class TestJobHierarchy:
    def test_default_kinds_are_the_agreed_list(self):
        assert core.KINDS == ("epic", "story", "bug", "spike", "idea", "btw", "guide")

    def test_new_job_defaults_to_a_story_with_no_external_id(self):
        db = core.load_db()
        job = core.create_job(db, "Ship fu")
        assert (job["kind"], job["ext_id"], job["parent_id"]) == ("story", "", None)
        assert core.job_label(job) == "J1"

    def test_external_id_is_free_text_and_addresses_the_job(self):
        db = core.load_db()
        job = core.create_job(db, "Cache invalidation", "bug", ext_id="OPS-1234")
        assert core.job_label(job) == "OPS-1234"
        assert core.job_by_ref(db, "ops-1234") is job
        assert core.job_by_ref(db, "J1") is job

    def test_external_ids_are_unique_ignoring_case(self):
        db = core.load_db()
        core.create_job(db, "One", ext_id="OPS-1")
        with pytest.raises(SystemExit):
            core.create_job(db, "Two", ext_id="ops-1")

    def test_a_job_can_sit_under_a_parent(self):
        db = core.load_db()
        epic = core.create_job(db, "Backprop", "epic")
        story = core.create_job(db, "Gradient check", "story", parent="Backprop")
        assert story["parent_id"] == epic["id"]
        assert core.descendants(db, epic) == [story]

    def test_loops_are_refused(self):
        db = core.load_db()
        epic = core.create_job(db, "Backprop", "epic")
        story = core.create_job(db, "Gradient check", parent="Backprop")
        with pytest.raises(SystemExit):
            core.set_parent(db, epic, "Gradient check")
        with pytest.raises(SystemExit):
            core.set_parent(db, story, "Gradient check")

    def test_parent_none_clears_it(self):
        db = core.load_db()
        core.create_job(db, "Backprop", "epic")
        story = core.create_job(db, "Gradient check", parent="Backprop")
        core.set_parent(db, story, "none")
        assert story["parent_id"] is None

    def test_unknown_parent_is_an_error(self):
        db = core.load_db()
        with pytest.raises(SystemExit):
            core.create_job(db, "Orphan", parent="nope")


class TestResumeCommand:
    def test_claude(self):
        item = {"agent": "claude", "session_id": "abc", "cwd": "/w"}
        assert core.resume_cmd(item) == "cd /w && claude --resume abc"

    def test_copilot(self):
        item = {"agent": "copilot", "session_id": "abc", "cwd": "/w"}
        assert core.resume_cmd(item) == "cd /w && copilot --resume=abc"

    def test_none_without_a_session_id(self):
        assert core.resume_cmd({"agent": "claude", "session_id": None}) is None

    def test_paths_with_spaces_are_quoted(self):
        item = {"agent": "claude", "session_id": "abc", "cwd": "/my project"}
        assert core.resume_cmd(item) == "cd '/my project' && claude --resume abc"


class TestFilters:
    def test_done_hidden_unless_asked_for(self, seeded):
        shown = [i["summary"] for i in seeded["items"] if core.matches(i, {})]
        assert "Tidy notes" not in shown and len(shown) == 3
        assert any(i["summary"] == "Tidy notes" for i in seeded["items"] if core.matches(i, {"all": True}))

    def test_explicit_done_status_shows_done(self, seeded):
        assert [i["summary"] for i in seeded["items"] if core.matches(i, {"status": "done"})] == ["Tidy notes"]

    def test_by_job_id_and_none(self, seeded):
        by_job = [i["summary"] for i in seeded["items"] if core.matches(i, {"job": 1})]
        assert by_job == ["Write gradient check", "Vectorise softmax"]
        assert [i["summary"] for i in seeded["items"] if core.matches(i, {"job": "none", "all": True})] == [
            "Tidy notes"
        ]

    def test_by_session_fragment(self, seeded):
        got = [i["summary"] for i in seeded["items"] if core.matches(i, {"session": "bbbb2222"})]
        assert got == ["Vectorise softmax"]

    def test_idle_and_recent(self, seeded):
        seeded["items"][0]["last_worked"] = days_ago(10)
        idle = [i["summary"] for i in seeded["items"] if core.matches(i, {"idle": 7})]
        recent = [i["summary"] for i in seeded["items"] if core.matches(i, {"recent": 7})]
        assert idle == ["Write gradient check"]
        assert "Write gradient check" not in recent and len(recent) == 2

    def test_text_search_covers_summary_and_why(self, seeded):
        seeded["items"][1]["why"] = "needs numpy broadcasting"
        assert [i["summary"] for i in seeded["items"] if core.matches(i, {"text": "BROADCAST"})] == [
            "Vectorise softmax"
        ]


class TestSessions:
    def test_claude_session_comes_from_the_environment(self, monkeypatch):
        monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "sess-1")
        assert core.detect_session("claude", "/w") == "sess-1"

    def test_copilot_session_is_the_newest_started_in_this_folder(self, isolated):
        root = isolated / "copilot-sessions"
        for sid, cwd in (("old", "/w"), ("other", "/elsewhere"), ("new", "/w")):
            (root / sid).mkdir(parents=True)
            (root / sid / "workspace.yaml").write_text(f"id: {sid}\ncwd: {cwd}\n")
        import os

        os.utime(root / "old" / "workspace.yaml", (1, 1))
        assert core.detect_session("copilot", "/w") == "new"

    def test_grouping_and_labels(self, seeded):
        groups = core.by_session([i for i in seeded["items"] if i["status"] != "done"])
        assert sorted(len(g) for g in groups.values()) == [1, 2]
        key = "claude:aaaa1111-0000-0000-0000-000000000001"
        assert core.session_label(key, groups[key]) == "claude aaaa1111 · w"
        assert core.session_label("", []) == "no session"
