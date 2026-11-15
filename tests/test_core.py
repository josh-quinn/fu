import json
from datetime import date, timedelta

import pytest

from fu import core


def days_ago(n: int) -> str:
    return (date.today() - timedelta(days=n)).isoformat()


class TestStorage:
    def test_missing_board_is_empty(self):
        assert core.load_db() == {"items": [], "jobs": [], "types": []}

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
        legacy = {
            "items": [],
            "jobs": [{"id": n, "name": k, "kind": k} for n, k in enumerate(["misc", "idea", "btw", "guide", "task"])],
        }
        (path / "board.json").write_text(json.dumps(legacy))
        jobs = core.load_db()["jobs"]
        assert [j["kind"] for j in jobs] == ["task"] * 5  # an idea is a follow-up now; a guide is an output
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
        assert core.KINDS == ("epic", "story", "bug", "spike", "task")
        assert core.job_types() == list(core.KINDS)

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

    def test_deleting_a_job_keeps_its_tasks_and_lifts_its_children(self):
        db = core.load_db()
        epic = core.create_job(db, "Backprop", "epic")
        story = core.create_job(db, "Gradient check", parent="Backprop")
        bug = core.create_job(db, "ReLU bug", "bug", parent="Gradient check")
        task = core.new_item(db, "Print both grads", job="Gradient check")
        assert core.remove_job(db, story) == 1
        assert task["job_id"] is None and task in db["items"]
        assert bug["parent_id"] == epic["id"]
        assert story not in db["jobs"]

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


class TestBoardSort:
    @staticmethod
    def board():
        db = core.load_db()
        core.create_job(db, "Alpha")
        core.create_job(db, "Beta")
        core.new_item(db, "a-done", status="done", job="Alpha", last_worked="2026-11-01", added="2026-10-01")
        core.new_item(db, "a-todo-new", job="Alpha", last_worked="2026-11-05", added="2026-10-02")
        core.new_item(db, "a-todo-old", job="Alpha", last_worked="2026-11-02", added="2026-10-03")
        core.new_item(db, "b-doing", status="doing", job="Beta", last_worked="2026-11-09", added="2026-10-04")
        core.new_item(db, "loose", last_worked="2026-11-03", added="2026-10-05")
        return db

    def names(self, db, column, descending=False):
        return [i["summary"] for i in core.sort_board(db, db["items"], column, descending)]

    def test_status_then_last_worked_then_added(self):
        db = self.board()
        # todo (oldest last-worked first), then doing, then done
        assert self.names(db, "status") == ["a-todo-old", "loose", "a-todo-new", "b-doing", "a-done"]

    def test_job_then_status_then_last_worked_then_added(self):
        db = self.board()
        # Alpha's tasks by status (todo before done) then last worked, then Beta, then no job last
        assert self.names(db, "job") == ["a-todo-old", "a-todo-new", "a-done", "b-doing", "loose"]

    def test_descending_is_the_exact_reverse(self):
        db = self.board()
        for column in core.SORT_COLUMNS:
            assert self.names(db, column, True) == self.names(db, column)[::-1]

    def test_last_worked_added_and_id_columns(self):
        db = self.board()
        assert self.names(db, "last_worked")[0] == "a-done"
        assert self.names(db, "added")[0] == "a-done"
        assert self.names(db, "id") == ["a-done", "a-todo-new", "a-todo-old", "b-doing", "loose"]

    def test_rows_that_tie_on_everything_keep_a_fixed_order_by_id(self):
        db = core.load_db()
        for name in ("first", "second", "third"):
            core.new_item(db, name)
        assert self.names(db, "status") == ["first", "second", "third"]
        assert self.names(db, "status", True) == ["third", "second", "first"]

    def test_summary_column_ignores_case(self):
        db = core.load_db()
        for name in ("beta", "Alpha", "gamma"):
            core.new_item(db, name)
        assert self.names(db, "summary") == ["Alpha", "beta", "gamma"]


class TestJobsBoard:
    @staticmethod
    def board():
        db = core.load_db()
        epic = core.create_job(db, "Backprop", "epic", ext_id="ML-1")
        core.create_job(db, "Gradient check", "story", ext_id="ML-2", parent="ML-1")
        core.create_job(db, "ReLU bug", "bug")
        core.create_job(db, "Log queries", "btw")
        epic["created"] = "2026-09-01"
        db["jobs"][1]["created"] = "2026-10-05"
        db["jobs"][2]["created"] = "2026-10-20"
        db["jobs"][3]["created"] = "2026-11-02"
        core.new_item(db, "t1", job="ML-2", last_worked="2026-11-10", agent="claude", session_id="s1")
        core.new_item(db, "t2", job="ML-2", last_worked="2026-11-12", agent="copilot", session_id="s2")
        core.new_item(db, "t3", job="ReLU bug", last_worked="2026-11-01")
        return db

    def test_rows_carry_the_columns_newest_activity_first(self):
        rows = core.job_rows(self.board())
        assert [r["title"] for r in rows] == ["Gradient check", "Log queries", "ReLU bug", "Backprop"]
        story = rows[0]
        assert (story["id"], story["kind"], story["parent"], story["added"]) == (
            "ML-2",
            "story",
            "Backprop",
            "2026-10-05",
        )
        assert story["last_worked"] == "2026-11-12"  # the latest of its tasks

    def test_a_job_without_tasks_uses_the_day_it_was_created(self):
        rows = {r["title"]: r for r in core.job_rows(self.board())}
        assert rows["Backprop"]["last_worked"] == "2026-09-01"

    def test_text_filter_is_a_case_insensitive_contains_on_that_column(self):
        rows = core.job_rows(self.board())
        out = core.filter_jobs(rows, {"title": {"text": "CHECK"}})
        assert [r["title"] for r in out] == ["Gradient check"]
        assert [r["title"] for r in core.filter_jobs(rows, {"parent": {"text": "back"}})] == ["Gradient check"]

    def test_filters_on_several_columns_combine(self):
        rows = core.job_rows(self.board())
        out = core.filter_jobs(rows, {"kind": {"text": "story"}, "title": {"text": "relu"}})
        assert out == []

    def test_date_filter_is_inclusive_on_both_ends(self):
        rows = core.job_rows(self.board())
        out = core.filter_jobs(rows, {"added": {"from": "2026-10-05", "to": "2026-10-20"}})
        assert sorted(r["title"] for r in out) == ["Gradient check", "ReLU bug"]

    def test_suggestions_put_prefix_matches_first_and_cap_nothing(self):
        rows = core.job_rows(self.board())
        assert core.suggestions(rows, "title", "") == ["Backprop", "Gradient check", "Log queries", "ReLU bug"]
        assert core.suggestions(rows, "title", "g") == ["Gradient check", "Log queries", "ReLU bug"]  # "bug" has a g
        assert core.suggestions(rows, "title", "zzz") == []

    def test_kind_suggestions_are_the_default_list_whether_or_not_a_job_uses_them(self):
        assert core.suggestions(core.job_rows(core.load_db()), "kind") == list(core.KINDS)
        assert core.suggestions([], "kind", "sp") == ["spike"]

    def test_resume_picks_the_most_recent_restartable_task(self):
        db = self.board()
        job = core.job_by_ref(db, "ML-2")
        assert core.job_resume_item(db, job)["session_id"] == "s2"
        assert core.job_resume_item(db, core.job_by_ref(db, "ReLU bug")) is None  # no session captured


class TestDates:
    def test_format(self):
        assert core.fmt_date(date(2026, 11, 13)) == "Nov 13 2026"

    def test_week_runs_monday_to_sunday(self):
        assert core.date_range("week", date(2026, 11, 13)) == ("2026-11-09", "2026-11-15")  # a Friday
        assert core.date_range("week", date(2026, 11, 15)) == ("2026-11-09", "2026-11-15")  # the Sunday
        assert core.date_range("week", date(2026, 11, 16)) == ("2026-11-16", "2026-11-22")  # next Monday

    def test_month_handles_december_and_leap_february(self):
        assert core.date_range("month", date(2026, 12, 9)) == ("2026-12-01", "2026-12-31")
        assert core.date_range("month", date(2028, 2, 10)) == ("2028-02-01", "2028-02-29")

    def test_year_and_day(self):
        assert core.date_range("year", date(2026, 6, 1)) == ("2026-01-01", "2026-12-31")
        assert core.date_range("day", date(2026, 6, 1)) == ("2026-06-01", "2026-06-01")

    def test_week_options_lead_with_this_and_last_week(self):
        opts = core.range_options("week", date(2026, 11, 13))
        assert [o[0] for o in opts[:3]] == ["This week", "Last week", "Week of Oct 26 2026"]
        assert opts[0][1:] == ("2026-11-09", "2026-11-15")
        assert len(opts) == 8

    def test_month_options_cross_the_year_boundary(self):
        labels = [o[0] for o in core.range_options("month", date(2026, 2, 3), 4)]
        assert labels == ["Feb 2026", "Jan 2026", "Dec 2025", "Nov 2025"]

    def test_year_options(self):
        assert [o[0] for o in core.range_options("year", date(2026, 11, 13))] == ["2026", "2025", "2024", "2023"]


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


def test_a_job_has_a_home_folder_stored_absolute(tmp_path):
    db = core.load_db()
    (tmp_path / "repo").mkdir()
    job = core.create_job(db, "With home", home=str(tmp_path / "repo"))
    assert job["home"] == str((tmp_path / "repo").resolve())
    assert core.create_job(db, "Without")["home"] == ""


def test_old_jobs_get_an_empty_home():
    core.save_db({"items": [], "jobs": [{"id": 1, "name": "Old", "kind": "story", "created": "2026-01-01"}]})
    assert core.load_db()["jobs"][0]["home"] == ""


def test_jobs_sort_by_any_column_both_ways():
    db = core.load_db()
    for name in ("beta", "Alpha", "gamma"):
        core.create_job(db, name)
    rows = core.job_rows(db)
    assert [r["title"] for r in core.sort_jobs(rows, "title", False)] == ["Alpha", "beta", "gamma"]
    assert [r["title"] for r in core.sort_jobs(rows, "title", True)] == ["gamma", "beta", "Alpha"]


def test_a_failed_save_leaves_the_old_board_whole_and_no_temp_file(monkeypatch):
    core.save_db({"items": [], "jobs": [], "marker": "keep me"})
    before = (core.data_dir() / "board.json").read_text()

    def explode(*_a, **_k):
        raise OSError("disk full")

    monkeypatch.setattr(core.json, "dump", explode)
    with pytest.raises(OSError):
        core.save_db({"items": [], "jobs": []})
    assert (core.data_dir() / "board.json").read_text() == before
    assert not list(core.data_dir().glob("*.tmp"))


@pytest.mark.parametrize("hostile", ["/w'; touch pwned; '", "/w && rm -rf ~", "/w $(id) `id`", "/w\nid"])
def test_a_hostile_folder_or_session_stays_one_argument(hostile):
    import shlex

    cmd = core.resume_cmd({"agent": "claude", "session_id": "s1", "cwd": hostile})
    assert shlex.split(cmd) == ["cd", hostile, "&&", "claude", "--resume", "s1"]
    cmd = core.resume_cmd({"agent": "copilot", "session_id": hostile, "cwd": "/w"})
    assert shlex.split(cmd) == ["cd", "/w", "&&", "copilot", f"--resume={hostile}"]
