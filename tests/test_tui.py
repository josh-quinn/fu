"""Drive the real Textual app headlessly. Each test pins behaviour that once broke."""

import asyncio
from datetime import date
from pathlib import Path

import pytest

pytest.importorskip("textual")

from textual.widgets import DataTable, Input, Select  # noqa: E402

from fu import core  # noqa: E402
from fu.tui import build_app  # noqa: E402

SIZE = (140, 40)


def drive(steps):
    """Run an async scenario against a fresh app."""

    async def scenario():
        app = build_app()
        app.ran = []
        app.runner = app.ran.append  # record the commands sessions would run instead of running them
        async with app.run_test(size=SIZE) as pilot:
            await pilot.pause()
            await steps(app, pilot)

    asyncio.run(scenario())


def test_help_opens_and_closes(seeded):
    async def steps(app, pilot):
        await pilot.press("h")
        assert app.screen.__class__.__name__ == "Help"
        await pilot.press("escape")
        assert app.screen.__class__.__name__ != "Help"

    drive(steps)


def jobs_table(app):
    return app.query_one("#jobs-table", DataTable)


def job_titles(app) -> list[str]:
    table = jobs_table(app)
    return [str(table.get_row_at(n)[3]) for n in range(table.row_count)]


async def select_job(app, pilot, title: str) -> None:
    """Move the Jobs cursor onto a job by title, however the rows happen to be ordered."""
    want = job_titles(app).index(title)
    gap = want - jobs_table(app).cursor_row
    await pilot.press(*(["down"] * gap if gap > 0 else ["up"] * -gap))


def test_jobs_screen_is_a_table_with_one_row_per_job_and_no_session_list(seeded):
    async def steps(app, pilot):
        await pilot.press("1")
        table = jobs_table(app)
        assert [str(c.label).split(" ")[0] for c in table.columns.values()] == [
            "ID",
            "Type",
            "Parent",
            "Title",
            "Added",
            "Last",
        ]
        assert sorted(job_titles(app)) == ["Backprop from scratch", "ReLU derivative bug"]
        assert not app.query("Tree")  # the folder tree and its Sessions list are gone

    drive(steps)


def test_jobs_headers_move_and_right_past_the_last_swipes_to_the_board(seeded):
    async def steps(app, pilot):
        await pilot.press("1", "up")
        assert app.view == "jobs" and app.header == 0
        await pilot.press("left")
        assert app.view == "jobs" and app.header == 0  # nothing to the left of the first header
        await pilot.press(*["right"] * 5)
        assert app.header == 5
        await pilot.press("right")
        assert app.view == "board" and app.header is None

    drive(steps)


def test_shift_r_on_a_job_with_sessions_offers_restart_or_a_new_session(seeded):
    async def steps(app, pilot):
        await pilot.press("1")
        await select_job(app, pilot, "Backprop from scratch")  # the epic with two sessions
        await pilot.press("R")
        assert app.screen.__class__.__name__ == "SessionChoice"
        assert len(app.screen.sessions) == 2
        await pilot.press("escape")
        assert app.ran == [] and app.view == "jobs"
        await pilot.press("R")
        await pilot.pause()
        first = app.screen.sessions[0][0]
        await pilot.press("enter")  # Restart is the default, on the first listed session
        await pilot.pause()
        assert app.ran == [core.resume_cmd(core.find(core.load_db()["items"], first))]
        assert app.screen.__class__.__name__ != "SessionChoice"  # back on the board once the session ends

    drive(steps)


def test_restart_can_target_another_session_with_up_and_down(seeded):
    async def steps(app, pilot):
        await pilot.press("1")
        await select_job(app, pilot, "Backprop from scratch")
        await pilot.press("R")
        await pilot.pause()
        second = app.screen.sessions[1][0]
        await pilot.press("down", "enter")
        await pilot.pause()
        assert app.ran == [core.resume_cmd(core.find(core.load_db()["items"], second))]

    drive(steps)


def test_right_picks_new_session_and_enter_opens_the_start_dialog(seeded):
    async def steps(app, pilot):
        await pilot.press("1")
        await select_job(app, pilot, "Backprop from scratch")
        await pilot.press("R")
        await pilot.pause()
        await pilot.press("right")
        await pilot.pause()
        assert not app.screen.query_one("#sessions").display  # New Session hides the list of old ones
        await pilot.press("enter")
        await pilot.pause()
        assert app.screen.__class__.__name__ == "NewSession" and app.ran == []

    drive(steps)


def test_shift_r_on_a_job_without_sessions_goes_straight_to_the_start_dialog(seeded):
    async def steps(app, pilot):
        db = core.load_db()
        core.create_job(db, "Cheatsheet", "btw")
        core.save_db(db)
        app.reload()
        await pilot.press("1")
        await select_job(app, pilot, "Cheatsheet")
        await pilot.press("R")
        await pilot.pause()
        assert app.screen.__class__.__name__ == "NewSession"

    drive(steps)


async def open_header(app, pilot, n: int) -> None:
    """Jobs screen: open column n's search (typing on a header or Enter in column mode both get here)."""
    await pilot.press("1")
    app.filter_column(n)
    await pilot.pause()


async def onto_headers(app, pilot) -> None:
    for _ in range(30):  # the cursor can sit on any row: Up until it has stepped onto the headers
        if app.header is not None:
            break
        await pilot.press("up")


def test_enter_on_a_jobs_header_sorts_by_it_and_again_flips_the_order(seeded):
    async def steps(app, pilot):
        await pilot.press("1")
        await onto_headers(app, pilot)
        await pilot.press("right", "right", "right", "enter")  # Title
        assert app.screen.__class__.__name__ != "Suggest" and app.jsort == ("title", False)
        assert job_titles(app) == ["Backprop from scratch", "ReLU derivative bug"]
        await pilot.press("enter")
        assert app.jsort == ("title", True)
        assert job_titles(app) == ["ReLU derivative bug", "Backprop from scratch"]

    drive(steps)


def test_typing_on_a_header_still_starts_its_search(seeded):
    async def steps(app, pilot):
        await pilot.press("1")
        await onto_headers(app, pilot)
        await pilot.press("right", "right", "right", "r")
        await pilot.pause()
        assert app.screen.__class__.__name__ == "Suggest" and app.jfilters == {"title": {"text": "r"}}

    drive(steps)


def test_a_text_column_search_filters_live_and_enter_locks(seeded):
    async def steps(app, pilot):
        await open_header(app, pilot, 3)  # Title
        assert app.screen.__class__.__name__ == "Suggest"
        await pilot.press(*"relu")
        await pilot.pause()
        assert job_titles(app) == ["ReLU derivative bug"]  # the table filters while you type
        await pilot.press("enter")
        await pilot.pause()
        assert app.screen.__class__.__name__ != "Suggest"
        assert app.jfilters == {"title": {"text": "relu"}}
        assert "●" in str(jobs_table(app).columns["title"].label)

    drive(steps)


def test_up_and_down_pick_a_suggestion_and_enter_locks_that_one(seeded):
    async def steps(app, pilot):
        await open_header(app, pilot, 3)
        await pilot.press("down", "down", "enter")  # two suggestions down: alphabetical, so the second
        await pilot.pause()
        assert app.jfilters == {"title": {"text": "ReLU derivative bug"}}

    drive(steps)


def test_escape_puts_the_previous_filter_back(seeded):
    async def steps(app, pilot):
        await open_header(app, pilot, 3)
        await pilot.press(*"backprop", "enter")
        await pilot.press("enter")  # still on the Title header: reopen it
        await pilot.pause()
        await pilot.press(*"zzz")
        await pilot.pause()
        assert job_titles(app) == []  # live
        await pilot.press("escape")
        await pilot.pause()
        assert app.jfilters == {"title": {"text": "backprop"}}
        assert job_titles(app) == ["Backprop from scratch"]

    drive(steps)


def test_locking_an_empty_box_clears_that_filter(seeded):
    async def steps(app, pilot):
        app.jfilters = {"title": {"text": "relu"}}
        app.reload()
        await open_header(app, pilot, 3)
        await pilot.press(*["backspace"] * 4, "enter")
        await pilot.pause()
        assert app.jfilters == {} and len(job_titles(app)) == 2

    drive(steps)


def test_type_header_offers_the_default_kinds_and_searches_them(seeded):
    async def steps(app, pilot):
        from textual.widgets import OptionList

        await open_header(app, pilot, 1)  # Type
        opts = app.screen.query_one(OptionList)
        assert opts.option_count == len(core.KINDS)  # the whole default list before anything is typed
        assert opts.size.height == len(core.KINDS)  # ...and every one of them is visible, none hidden by a scrollbar
        await pilot.press(*"sp")
        assert [str(opts.get_option_at_index(n).prompt) for n in range(opts.option_count)] == ["spike"]

    drive(steps)


def test_an_empty_search_lists_everything_and_typing_caps_the_list_at_six_rows(seeded):
    async def steps(app, pilot):
        from textual.widgets import OptionList

        db = core.load_db()
        for n in range(8):
            core.create_job(db, f"Job number {n}")
        core.save_db(db)
        app.reload()
        await open_header(app, pilot, 3)  # Title: 10 jobs
        opts = app.screen.query_one(OptionList)
        assert opts.option_count == 10 and opts.size.height == 10  # empty: all shown
        await pilot.press(*"job")
        await pilot.pause()
        assert opts.option_count == 8 and opts.size.height == 6  # typing: six rows, the rest scroll
        await pilot.press(*["backspace"] * 3)
        await pilot.pause()
        assert opts.size.height == 10  # emptied again: everything is back

    drive(steps)


def test_suggestions_only_come_from_rows_the_other_filters_leave(seeded):
    async def steps(app, pilot):
        from textual.widgets import OptionList

        app.jfilters = {"kind": {"text": "bug"}}
        app.reload()
        await open_header(app, pilot, 3)
        opts = app.screen.query_one(OptionList)
        assert opts.option_count == 1  # only the bug is left to suggest

    drive(steps)


def test_c_clears_the_jobs_filters_and_escape_first_leaves_the_headers(seeded):
    async def steps(app, pilot):
        app.jfilters = {"title": {"text": "relu"}}
        app.reload()
        await pilot.press("1", "up", "escape")
        assert app.header is None and app.jfilters  # the first escape only steps off the headers
        await pilot.press("c")
        await pilot.pause()
        assert app.jfilters == {} and len(job_titles(app)) == 2

    drive(steps)


def test_date_header_opens_a_picker_on_todays_date_and_apply_filters_that_day(seeded):
    async def steps(app, pilot):
        db = core.load_db()
        db["jobs"][0]["created"] = "2026-01-15"
        core.save_db(db)
        app.reload()
        await open_header(app, pilot, 4)  # Added
        picker = app.screen
        assert picker.__class__.__name__ == "DatePick"
        assert (picker.y, picker.m, picker.d) == (date.today().year, date.today().month, date.today().day)
        await pilot.press("right", "right", "right", "enter")  # month, day, year, then Apply
        await pilot.pause()
        assert app.jfilters["added"]["from"] == app.jfilters["added"]["to"] == date.today().isoformat()
        assert job_titles(app) == ["ReLU derivative bug"]  # the epic was added in January

    drive(steps)


def test_picking_a_month_by_typing_then_apply_filters_that_day(seeded):
    # Regression: the month and year segment editors shared a name with the 'Select by' ranges,
    # so choosing a month crashed trying to read it as a (from, to) pair.
    async def steps(app, pilot):
        db = core.load_db()
        db["jobs"][0]["created"] = "2026-01-15"
        core.save_db(db)
        app.reload()
        await open_header(app, pilot, 4)
        await pilot.press("enter", *"jan", "enter")  # month segment: type and take the first match
        assert app.screen.m == 1
        await pilot.press("right", "enter", "1", "5", "enter")  # day segment: 15
        assert app.screen.d == 15
        await pilot.press("right", "right", "enter")  # year, then Apply
        await pilot.pause()
        assert app.jfilters["added"]["from"] == "2026-01-15"
        assert job_titles(app) == ["Backprop from scratch"]

    drive(steps)


def test_changing_the_month_keeps_the_day_inside_it(seeded):
    async def steps(app, pilot):
        await open_header(app, pilot, 4)
        app.screen.d = 31
        await pilot.press("enter", *"feb", "enter")
        assert (app.screen.m, app.screen.d) == (2, 28)  # 2026 is not a leap year

    drive(steps)


def test_select_by_week_offers_this_week_first_and_filters_the_range(seeded):
    async def steps(app, pilot):
        db = core.load_db()
        db["jobs"][0]["created"] = "2026-01-15"
        core.save_db(db)
        app.reload()
        await open_header(app, pilot, 4)
        await pilot.press("down", "enter", "enter")  # row 'Select by…', pick Week (first match)
        assert app.screen.sub == "range:week"
        await pilot.press("enter")  # This week
        await pilot.pause()
        f = app.jfilters["added"]
        assert f["label"] == "This week"
        assert f["from"] <= date.today().isoformat() <= f["to"]
        assert job_titles(app) == ["ReLU derivative bug"]

    drive(steps)


def test_picker_clear_removes_the_filter_and_escape_leaves_it_alone(seeded):
    async def steps(app, pilot):
        app.jfilters = {"added": {"from": "2026-01-01", "to": "2026-01-31", "label": "Jan 2026"}}
        app.reload()
        await open_header(app, pilot, 4)
        await pilot.press("escape")
        assert app.jfilters["added"]["label"] == "Jan 2026"
        await open_header(app, pilot, 4)  # reopen it
        await pilot.press("right", "right", "right", "right", "enter")  # to Clear
        await pilot.pause()
        assert app.jfilters == {}

    drive(steps)


def test_task_keys_do_nothing_on_the_jobs_screen(seeded):
    async def steps(app, pilot):
        before = [i["status"] for i in core.load_db()["items"]]
        await pilot.press("1", "s", "d", "t")
        assert [i["status"] for i in core.load_db()["items"]] == before

    drive(steps)


def test_deleting_a_job_lifts_its_child_jobs(seeded):
    async def steps(app, pilot):
        db = core.load_db()
        epic = core.job_by_ref(db, "Backprop from scratch")
        core.create_job(db, "Child story", "story", parent=epic["name"])
        core.save_db(db)
        app.reload()
        await pilot.press("1")
        await select_job(app, pilot, "Backprop from scratch")
        await pilot.press("x", "y")
        await pilot.pause()
        db = core.load_db()
        assert core.job_by_ref(db, "Backprop from scratch") is None
        assert core.job_by_ref(db, "Child story")["parent_id"] is None

    drive(steps)


def focused(app) -> str:
    return app.screen.focused.id


def test_tab_still_moves_between_form_rows(seeded):
    # Regression: the dialog guard disabled Textual's own focus action, so Tab did nothing
    # and everything typed landed in the first field. Tab now steps rows like the down arrow.
    async def steps(app, pilot):
        await pilot.press("a")
        assert focused(app) == "row-summary"
        await pilot.press("tab")
        assert focused(app) == "row-why"
        await pilot.press("shift+tab")
        assert focused(app) == "row-summary"

    drive(steps)


def test_arrows_move_rows_enter_edits_and_enter_again_leaves(seeded):
    async def steps(app, pilot):
        await pilot.press("a")
        await pilot.press("enter")
        assert isinstance(app.screen.focused, Input) and app.screen.editing == "summary"
        await pilot.press(*"Plan outline", "down")  # arrows do nothing while typing
        assert app.screen.editing == "summary"
        await pilot.press("enter")
        assert app.screen.editing is None and focused(app) == "row-summary"
        assert app.screen.vals["summary"] == "Plan outline"
        await pilot.press("down")
        assert focused(app) == "row-why"
        await pilot.press("ctrl+s")
        await pilot.pause()
        assert any(i["summary"] == "Plan outline" for i in core.load_db()["items"])

    drive(steps)


def test_escape_leaves_an_edit_without_keeping_it_then_closes_the_form(seeded):
    async def steps(app, pilot):
        await pilot.press("a", "enter", *"discard me", "escape")
        assert app.screen.editing is None and app.screen.vals["summary"] == ""
        assert app.screen.__class__.__name__ == "ItemForm"
        await pilot.press("escape")
        assert app.screen.__class__.__name__ not in ("ItemForm", "RowForm")

    drive(steps)


def test_adding_a_task_with_a_new_name_creates_the_job(seeded):
    async def steps(app, pilot):
        await pilot.press("a")
        await pilot.press("enter", *"Plan outline", "enter", "down", "down")
        await pilot.press("enter", *"Week 2 report", "enter", "ctrl+s")
        await pilot.pause()
        db = core.load_db()
        assert any(j["name"] == "Week 2 report" for j in db["jobs"])
        assert any(i["summary"] == "Plan outline" and i["job_id"] for i in db["items"])

    drive(steps)


def test_session_agent_and_folder_are_greyed_out_and_cannot_be_edited(seeded):
    async def steps(app, pilot):
        before = {k: core.load_db()["items"][0][k] for k in ("cwd", "agent", "session_id")}
        await pilot.press("e")
        form = app.screen
        locked = {k for k in ("cwd", "agent", "session_id") if not form.query_one(f"#row-{k}").can_focus}
        assert locked == {"cwd", "agent", "session_id"}
        assert all(form.query_one(f"#row-{k}").has_class("ro") for k in locked)
        await pilot.press("down", "down", "down", "down", "down")  # runs off the last editable row
        assert focused(app) == "row-job"
        await pilot.press("enter", *"x", "enter", "ctrl+s")
        await pilot.pause()
        after = core.load_db()["items"][0]
        assert {k: after[k] for k in before} == before

    drive(steps)


def test_job_type_is_a_dropdown_of_the_default_kinds(seeded):
    async def steps(app, pilot):
        await pilot.press("1", "a")
        form = app.screen
        options = [value for _, value in form.query_one("#edit-kind", Select)._options]
        assert options == list(core.KINDS)
        assert form.vals["kind"] == core.DEFAULT_KIND
        await pilot.press("enter", *"Cache is stale", "enter", "down", "down")
        assert focused(app) == "row-kind"
        await pilot.press("enter")
        await pilot.pause()
        await pilot.press("up", "enter")  # story -> the kind above it
        await pilot.pause()
        assert form.editing is None
        await pilot.press("ctrl+s")
        await pilot.pause()
        job = next(j for j in core.load_db()["jobs"] if j["name"] == "Cache is stale")
        assert job["kind"] == core.KINDS[core.KINDS.index(core.DEFAULT_KIND) - 1]

    drive(steps)


def test_a_bad_parent_is_reported_without_crashing_the_app(seeded):
    async def steps(app, pilot):
        await pilot.press("1", "a", "enter", *"Orphan", "enter", "down", "down", "down")
        await pilot.press("enter", *"no such job", "enter", "ctrl+s")
        await pilot.pause()
        assert not any(j["name"] == "Orphan" for j in core.load_db()["jobs"])
        assert app.is_running

    drive(steps)


def test_done_hides_the_task_but_keeps_it_on_the_board(seeded):
    async def steps(app, pilot):
        before = app.query_one(DataTable).row_count
        await pilot.press("d")
        await pilot.pause()
        assert app.query_one(DataTable).row_count == before - 1
        assert sum(i["status"] == "done" for i in core.load_db()["items"]) == 2
        await pilot.press("full_stop")
        await pilot.pause()
        assert app.query_one(DataTable).row_count == before + 1

    drive(steps)


def board_order(app) -> list[str]:
    return [i["summary"] for i in app.visible_items()]


def test_the_board_is_the_default_screen_and_keys_are_1_jobs_2_board(seeded):
    async def steps(app, pilot):
        assert app.view == "board"
        await pilot.press("1")
        assert app.view == "jobs"
        await pilot.press("2")
        assert app.view == "board"

    drive(steps)


def test_columns_match_the_sortable_columns():
    from fu.tui import COLUMNS

    assert [c for c, _ in COLUMNS] == list(core.SORT_COLUMNS)


def test_up_from_the_first_row_steps_onto_the_headers_and_down_returns(seeded):
    async def steps(app, pilot):
        assert app.header is None
        await pilot.press("down", "up")  # still on the rows
        assert app.header is None
        await pilot.press("up")
        assert app.header is not None
        await pilot.press("down")
        assert app.header is None

    drive(steps)


def test_left_and_right_move_across_the_headers_and_stop_at_the_last(seeded):
    async def steps(app, pilot):
        await pilot.press("up")
        start = app.header
        await pilot.press("right")
        assert app.header == start + 1
        await pilot.press(*["right"] * 10)
        assert app.header == 5  # last column, no wrap
        await pilot.press("left")
        assert app.header == 4

    drive(steps)


def test_left_past_the_first_header_swipes_over_to_jobs(seeded):
    async def steps(app, pilot):
        await pilot.press("up", *["left"] * 6)
        assert app.view == "jobs"
        assert app.header is None

    drive(steps)


def test_enter_on_a_header_sorts_and_again_flips_never_unsorted(seeded):
    async def steps(app, pilot):
        assert app.sort == ("status", False)
        await pilot.press("up", "right", "enter")  # starts on Status; one right is Job
        assert app.sort == ("job", False)
        await pilot.press("enter")
        assert app.sort == ("job", True)
        await pilot.press("enter")
        assert app.sort == ("job", False)  # only ever ascending or descending
        assert app.header is not None  # enter sorted; it did not resume the session

    drive(steps)


def test_sort_by_job_orders_by_job_then_status_then_last_worked(seeded):
    async def steps(app, pilot):
        await pilot.press("up", "right", "enter")
        asc = board_order(app)
        assert asc == ["Write gradient check", "Vectorise softmax", "Check relu_backward"]
        await pilot.press("enter")
        assert board_order(app) == asc[::-1]

    drive(steps)


def test_escape_on_the_headers_returns_to_the_rows_without_clearing_filters(seeded):
    async def steps(app, pilot):
        app.filters = {"text": "softmax"}
        app.reload()
        await pilot.press("up", "escape")
        assert app.header is None and app.filters == {"text": "softmax"}

    drive(steps)


def test_quit_key_is_ignored_inside_a_confirm_dialog(seeded):
    async def steps(app, pilot):
        await pilot.press("x")
        assert app.screen.__class__.__name__ == "Confirm"
        await pilot.press("q")
        assert app.screen.__class__.__name__ == "Confirm"
        await pilot.press("n")
        assert len(core.load_db()["items"]) == 4

    drive(steps)


def test_filter_dialog_applies_a_text_filter(seeded):
    async def steps(app, pilot):
        await pilot.press("f", *"softmax", "ctrl+s")
        await pilot.pause()
        assert app.filters == {"text": "softmax"}
        assert app.query_one(DataTable).row_count == 1

    drive(steps)


# ----------------------------------------------------------------- summary panel


def panel(app):
    return app.query_one("#jobs-detail")


def entry_key(app) -> str | None:
    p = panel(app)
    return None if p.highlighted is None else p.get_option_at_index(p.highlighted).id


def panel_keys(app) -> list[str]:
    p = panel(app)
    return [o.id for o in (p.get_option_at_index(n) for n in range(p.option_count)) if o.id and not o.disabled]


async def goto_entry(app, pilot, prefix: str) -> None:
    """Walk down the panel until the highlighted entry's key starts with `prefix`."""
    for _ in range(30):
        if (entry_key(app) or "").startswith(prefix):
            return
        await pilot.press("down")
    raise AssertionError(f"no entry {prefix!r} in {panel_keys(app)}")


@pytest.fixture
def epic_board(isolated, monkeypatch):
    """An epic with a child story, two sessions (real folders), and one saved artifact."""
    from fu import artifacts

    monkeypatch.setattr(artifacts, "SCRATCH", ("/scratchpad/", "/node_modules/", "/.git/"))
    work, docs = isolated / "work", isolated / "docs"
    work.mkdir()
    docs.mkdir()
    runbook = docs / "runbook.md"
    runbook.write_text("# how to")
    db = core.load_db()
    core.create_job(db, "Backprop", "epic", ext_id="ML-1")
    core.create_job(db, "Gradient check", "story", ext_id="ML-2", parent="ML-1")
    core.new_item(
        db, "grads", job="ML-1", agent="claude", session_id="aaaa1111-x", cwd=str(work), last_worked="2026-11-10"
    )
    later = core.new_item(
        db, "softmax", job="ML-1", agent="copilot", session_id="bbbb2222-y", cwd=str(docs), last_worked="2026-11-12"
    )
    artifacts.add_manual(later, str(runbook), "Prod runbook")
    core.save_db(db)
    return {"work": work, "docs": docs, "runbook": runbook}


async def open_panel(app, pilot, title="Backprop") -> None:
    await pilot.press("1")
    await select_job(app, pilot, title)
    await pilot.press("right")
    await pilot.pause()


def test_right_enters_the_panel_on_its_first_actionable_entry_and_left_leaves(epic_board):
    async def steps(app, pilot):
        await open_panel(app, pilot)
        assert app.focused is panel(app) and app.in_panel
        assert entry_key(app) == panel_keys(app)[0]
        await pilot.press("left")
        assert app.focused is jobs_table(app) and not app.in_panel

    drive(steps)


def test_up_and_down_land_only_on_actionable_entries(epic_board):
    async def steps(app, pilot):
        await open_panel(app, pilot)
        seen = [entry_key(app)]
        for _ in range(len(panel_keys(app)) + 2):
            await pilot.press("down")
            seen.append(entry_key(app))
        assert set(seen) <= set(panel_keys(app))  # never on a heading or plain text
        assert seen[-1] == panel_keys(app)[-1] == "notes"  # it stops at the end

    drive(steps)


def test_the_panel_cursor_stops_at_the_first_entry_too(epic_board):
    async def steps(app, pilot):
        await open_panel(app, pilot)
        first = entry_key(app)
        await pilot.press("up", "up", "up")
        assert entry_key(app) == first  # no wrapping round to the last entry

    drive(steps)


def test_enter_on_a_child_job_jumps_to_its_row_and_keeps_the_cursor_in_the_panel(epic_board):
    async def steps(app, pilot):
        await open_panel(app, pilot)
        await goto_entry(app, pilot, "job:")
        await pilot.press("enter")
        await pilot.pause()
        assert app.current_job()["name"] == "Gradient check"
        assert app.focused is panel(app)
        assert "Gradient check" in str(panel(app).get_option_at_index(0).prompt)
        # the cursor starts inside the new job's panel, not nowhere and not on a stale row
        assert entry_key(app) == panel_keys(app)[0]

    drive(steps)


def test_jumping_to_a_job_hidden_by_a_filter_clears_the_filters(epic_board):
    async def steps(app, pilot):
        await open_panel(app, pilot)
        app.jfilters = {"title": {"text": "backprop"}}
        app.reload()
        await goto_entry(app, pilot, "job:")
        await pilot.press("enter")
        await pilot.pause()
        assert app.jfilters == {} and app.current_job()["name"] == "Gradient check"

    drive(steps)


def test_enter_on_a_session_offers_resume_or_session_folder_buttons_and_esc_goes_back(epic_board):
    async def steps(app, pilot):
        await open_panel(app, pilot)
        await goto_entry(app, pilot, "session:")
        await pilot.press("enter")
        await pilot.pause()
        assert app.screen.__class__.__name__ == "SessionActions"
        assert [label for _, label in app.screen.BUTTONS] == ["Resume", "Session folder"]
        assert app.screen.on == "resume"
        await pilot.press("escape")
        await pilot.pause()
        assert app.screen.__class__.__name__ != "SessionActions" and app.focused is panel(app)

    drive(steps)


def test_restart_from_a_session_resumes_that_sessions_latest_task(epic_board):
    async def steps(app, pilot):
        await open_panel(app, pilot)
        await goto_entry(app, pilot, "session:claude")
        await pilot.press("enter", "enter")  # Resume is the first button
        await pilot.pause()
        assert app.ran == [f"cd {epic_board['work']} && claude --resume aaaa1111-x"]

    drive(steps)


def test_open_session_folder_opens_that_sessions_working_folder(epic_board, monkeypatch):
    from fu import artifacts

    opened = []
    monkeypatch.setattr(artifacts, "open_path", lambda path: opened.append(path) or True)

    async def steps(app, pilot):
        await open_panel(app, pilot)
        await goto_entry(app, pilot, "session:claude")
        await pilot.press("enter", "right", "enter")
        await pilot.pause()
        assert opened == [str(epic_board["work"])]

    drive(steps)


def test_a_sessions_missing_folder_is_reported_not_opened(epic_board, monkeypatch):
    from fu import artifacts

    opened = []
    monkeypatch.setattr(artifacts, "open_path", lambda path: opened.append(path) or True)
    epic_board["work"].rmdir()

    async def steps(app, pilot):
        await open_panel(app, pilot)
        await goto_entry(app, pilot, "session:claude")
        await pilot.press("enter", "right", "enter")
        await pilot.pause()
        assert opened == [] and app.is_running

    drive(steps)


def test_enter_on_artifacts_lists_them_and_enter_opens_one_in_its_app(epic_board, monkeypatch):
    from fu import artifacts

    opened = []
    monkeypatch.setattr(artifacts, "open_path", lambda path: opened.append(path) or True)

    async def steps(app, pilot):
        await open_panel(app, pilot)
        await goto_entry(app, pilot, "artifacts")
        await pilot.press("enter")
        await pilot.pause()
        assert app.screen.__class__.__name__ == "ArtifactList"
        assert app.screen.rows == [("live", str(epic_board["runbook"]))]
        await pilot.press("enter")
        assert opened == [str(epic_board["runbook"])]
        await pilot.press("escape")
        await pilot.pause()
        assert app.screen.__class__.__name__ != "ArtifactList"

    drive(steps)


def test_x_hides_a_wrong_guess_but_keeps_it_under_hidden_where_x_brings_it_back(epic_board):
    from fu import summary

    def state():
        db = core.load_db()
        job = core.job_by_ref(db, "ML-1")
        return [a["path"] for a in summary.job_artifacts(db, job)], summary.hidden_artifacts(db, job)

    async def steps(app, pilot):
        await open_panel(app, pilot)
        await goto_entry(app, pilot, "artifacts")
        await pilot.press("enter", "x")
        await pilot.pause()
        runbook = str(epic_board["runbook"])
        assert state() == ([], [runbook])
        assert ("hidden", runbook) in app.screen.rows
        await pilot.press("x")  # the cursor sits on the hidden one now
        await pilot.pause()
        assert state() == ([runbook], [])

    drive(steps)


def test_ctrl_z_undoes_hiding_an_artifact(epic_board):
    async def steps(app, pilot):
        await open_panel(app, pilot)
        await goto_entry(app, pilot, "artifacts")
        await pilot.press("enter", "x", "ctrl+z")
        await pilot.pause()
        assert app.screen.rows[0] == ("live", str(epic_board["runbook"]))

    drive(steps)


def test_artifacts_can_be_added_by_hand_even_when_there_are_none(isolated):
    note = isolated / "cheats.md"
    note.write_text("x")
    db = core.load_db()
    core.create_job(db, "Cheatsheet", "btw")
    core.save_db(db)

    async def steps(app, pilot):
        await open_panel(app, pilot, "Cheatsheet")
        await goto_entry(app, pilot, "artifacts")
        await pilot.press("enter")
        await pilot.pause()
        assert app.screen.__class__.__name__ == "ArtifactList" and app.screen.rows == [("none", "")]
        await pilot.press("a")
        box = app.screen.query_one("#add-path")
        box.value = str(note)
        await pilot.press("escape")  # closes the suggestions first, not the list
        await pilot.press("enter")
        await pilot.pause()
        assert app.screen.rows == [("live", str(note))]
        job = core.job_by_ref(core.load_db(), "Cheatsheet")
        assert [a["path"] for a in job["artifacts"]] == [str(note)]

    drive(steps)


def test_notes_are_added_with_ctrl_s_and_esc_discards(epic_board):
    async def steps(app, pilot):
        await open_panel(app, pilot)
        await goto_entry(app, pilot, "notes")
        await pilot.press("enter", *"ask about relu", "escape")
        assert core.job_by_ref(core.load_db(), "ML-1")["notes"] == ""
        await pilot.press("enter", *"ask about relu", "ctrl+s")
        await pilot.pause()
        assert core.job_by_ref(core.load_db(), "ML-1")["notes"] == "ask about relu"
        assert app.focused is panel(app)
        await pilot.press("enter")
        assert app.screen.query_one("#notes-text").text == "ask about relu"  # editing, not starting over

    drive(steps)


def test_the_bar_hints_at_the_panel_keys_while_you_are_in_it(epic_board):
    async def steps(app, pilot):
        await open_panel(app, pilot)
        assert "panel:" in str(app.query_one("#bar").render())
        await pilot.press("left")
        assert "panel:" not in str(app.query_one("#bar").render())

    drive(steps)


def prompt_of(app, key):
    p = panel(app)
    return next(o.prompt for o in (p.get_option_at_index(n) for n in range(p.option_count)) if o.id == key)


@pytest.fixture
def long_child(epic_board):
    db = core.load_db()
    core.create_job(db, "Gradient check " + "with a very long descriptive title " * 4, "story", parent="ML-1")
    core.save_db(db)


def test_long_entries_are_clipped_to_one_line(epic_board, long_child):
    async def steps(app, pilot):
        await open_panel(app, pilot)
        key = next(k for k in panel_keys(app) if k.startswith("job:") and "very long" in str(panel(app).full[k]))
        assert prompt_of(app, key).no_wrap

    drive(steps)


def test_resting_on_an_entry_reveals_its_full_name_and_a_key_puts_it_back(epic_board, long_child):
    async def steps(app, pilot):
        panel(app).REVEAL_AFTER = 0.2
        await open_panel(app, pilot)
        await goto_entry(app, pilot, "job:")
        while "very long" not in str(panel(app).full[entry_key(app)]):
            await pilot.press("down")
        key = entry_key(app)
        await pilot.pause(0.5)
        assert not prompt_of(app, key).no_wrap and panel(app).revealed == key
        await pilot.press("down")
        await pilot.pause()
        assert panel(app).revealed is None and prompt_of(app, key).no_wrap

    drive(steps)


def test_up_from_the_headers_reaches_the_screen_tabs_and_left_right_switch_screens(seeded):
    async def steps(app, pilot):
        await pilot.press("1", "up", "up")
        assert app.view == "jobs" and app.header == -1
        await pilot.press("right")
        assert app.view == "board" and app.header == -1
        await pilot.press("left")
        assert app.view == "jobs" and app.header == -1
        await pilot.press("left")  # no screen further left
        assert app.view == "jobs" and app.header == -1

    drive(steps)


def test_down_from_the_tabs_goes_to_the_headers_then_the_rows(seeded):
    async def steps(app, pilot):
        await pilot.press("2", "up", "up")
        assert app.view == "board" and app.header == -1
        await pilot.press("down")
        assert app.header is not None and app.header >= 0
        await pilot.press("down")
        assert app.header is None

    drive(steps)


def test_enter_on_the_tabs_does_nothing_and_escape_leaves(seeded):
    async def steps(app, pilot):
        await pilot.press("2", "up", "up", "enter")
        assert app.header == -1 and app.screen.__class__.__name__ != "Suggest"
        await pilot.press("escape")
        assert app.header is None

    drive(steps)


def test_typing_on_a_header_starts_the_search_without_enter(seeded):
    async def steps(app, pilot):
        await pilot.press("1")
        for _ in range(30):
            if app.header is not None:
                break
            await pilot.press("up")
        await pilot.press("right", "right", "right", "g")  # Title column
        await pilot.pause()
        assert app.screen.__class__.__name__ == "Suggest"
        assert app.screen.query_one(Input).value == "g"
        assert app.jfilters == {"title": {"text": "g"}}
        await pilot.press("r")
        assert app.screen.query_one(Input).value == "gr"
        await pilot.press("enter")
        assert app.screen.__class__.__name__ != "Suggest"
        assert app.jfilters == {"title": {"text": "gr"}}

    drive(steps)


def test_the_search_box_does_not_dim_the_board_behind_it(seeded):
    async def steps(app, pilot):
        await open_header(app, pilot, 3)
        assert app.screen.__class__.__name__ == "Suggest"
        assert app.screen.styles.background.a == 0

    drive(steps)


def test_typing_on_a_date_header_does_not_open_anything(seeded):
    async def steps(app, pilot):
        await pilot.press("1")
        for _ in range(30):
            if app.header is not None:
                break
            await pilot.press("up")
        await pilot.press("right", "right", "right", "right", "g")
        await pilot.pause()
        assert app.screen.__class__.__name__ != "Suggest" and app.jfilters == {}

    drive(steps)


async def to_row(app, pilot, title):
    await pilot.press("1")
    await select_job(app, pilot, title)


def test_enter_on_a_row_enters_column_mode_on_the_id_column(epic_board):
    async def steps(app, pilot):
        await to_row(app, pilot, "Backprop")
        await pilot.press("enter")
        assert app.col == 0 and app.screen.__class__.__name__ != "Confirm"
        await pilot.press("left", "left", "left", "left", "left")
        assert app.col == 0  # stops at the first column
        await pilot.press(*["right"] * 9)
        assert app.col == 5  # and at the last

    drive(steps)


def test_up_and_down_in_column_mode_move_the_row_not_the_column(epic_board):
    async def steps(app, pilot):
        await to_row(app, pilot, "Backprop")
        await pilot.press("enter")
        await pilot.pause()
        seen = {app.current_job()["id"]}
        for key in ("down", "up"):
            await pilot.press(key)
            await pilot.pause()
            seen.add(app.current_job()["id"])
        assert app.col == 0 and len(seen) == 2  # the other job was reached, the column never moved

    drive(steps)


def test_enter_enter_on_the_parent_column_shows_every_job_with_that_parent(epic_board):
    async def steps(app, pilot):
        await to_row(app, pilot, "Gradient check")
        await pilot.press("enter", "right", "right")  # ID -> Parent
        assert app.col == 2
        await pilot.press("enter")
        assert app.screen.__class__.__name__ == "Suggest"
        assert app.screen.query_one(Input).value == "Backprop"  # the row's own parent
        await pilot.press("enter")
        assert app.jfilters == {"parent": {"text": "Backprop"}}
        assert app.col == 2 and app.screen.__class__.__name__ != "Suggest"  # back on the highlighted column
        assert app.query_one("#jobs-table", DataTable).row_count == 1

    drive(steps)


def test_typing_in_column_mode_searches_that_column(epic_board):
    async def steps(app, pilot):
        await to_row(app, pilot, "Backprop")
        await pilot.press("enter", "right", "right", "right", "x")  # ID -> Title
        assert app.screen.__class__.__name__ == "Suggest"
        assert app.screen.query_one(Input).value == "x" and app.jfilters == {"title": {"text": "x"}}

    drive(steps)


def test_escape_in_column_mode_brings_back_all_results_then_leaves(epic_board):
    async def steps(app, pilot):
        await to_row(app, pilot, "Gradient check")
        await pilot.press("enter", "right", "right", "enter", "enter")
        assert app.jfilters
        await pilot.press("escape")
        assert not app.jfilters and app.col == 2
        assert app.query_one("#jobs-table", DataTable).row_count == 2
        await pilot.press("escape")
        assert app.col is None

    drive(steps)


def test_enter_on_a_date_column_opens_the_picker_on_that_rows_date(epic_board):
    async def steps(app, pilot):
        await to_row(app, pilot, "Backprop")
        await pilot.press("enter", *["right"] * 4)  # ID -> Added
        await pilot.press("enter")
        assert app.screen.__class__.__name__ == "DatePick"

    drive(steps)


async def enter_column_mode(app, pilot):
    await to_row(app, pilot, "Backprop")
    await pilot.press("enter")
    await pilot.pause()
    assert app.col == 0


def test_plain_letters_type_in_column_mode_but_ctrl_runs_shortcuts(epic_board):
    async def steps(app, pilot):
        await enter_column_mode(app, pilot)
        await pilot.press("a")  # a plain a is typed into the search, not the Add shortcut
        await pilot.pause()
        assert app.screen.__class__.__name__ == "Suggest"
        await pilot.press("escape")
        await pilot.pause()
        await pilot.press("ctrl+a")
        await pilot.pause()
        assert app.screen.__class__.__name__ == "JobForm"

    drive(steps)


def test_the_shortcut_modifier_comes_from_the_config(epic_board, tmp_path, monkeypatch):
    cfg = tmp_path / "cfg" / "follow-ups" / "config.yaml"
    cfg.parent.mkdir(parents=True)
    cfg.write_text("keys:\n  modifier: alt\n")

    async def steps(app, pilot):
        await enter_column_mode(app, pilot)
        await pilot.press("ctrl+a")  # no longer bound
        await pilot.pause()
        assert app.screen.__class__.__name__ != "JobForm"
        await pilot.press("alt+a")
        await pilot.pause()
        assert app.screen.__class__.__name__ == "JobForm"

    drive(steps)


def test_escape_then_a_digit_switches_screen_out_of_column_mode(epic_board):
    async def steps(app, pilot):
        await enter_column_mode(app, pilot)
        await pilot.press("escape", "2")
        assert app.col is None and app.view == "board"

    drive(steps)


def test_shift_r_and_shift_full_stop_are_shortcuts_not_search_text_in_column_mode(epic_board):
    async def steps(app, pilot):
        await enter_column_mode(app, pilot)
        await pilot.press("greater_than_sign")
        assert not panel(app).display and app.screen.__class__.__name__ != "Suggest"
        await pilot.press("R")
        await pilot.pause()
        assert app.screen.__class__.__name__ in ("SessionChoice", "NewSession")

    drive(steps)


def test_f1_opens_help_even_in_column_mode(epic_board):
    async def steps(app, pilot):
        await enter_column_mode(app, pilot)
        await pilot.press("f1")
        await pilot.pause()
        assert app.screen.__class__.__name__ == "Help"

    drive(steps)


def test_shift_full_stop_hides_and_shows_the_panel_and_right_reopens_it(epic_board):
    async def steps(app, pilot):
        await to_row(app, pilot, "Backprop")
        assert panel(app).display
        await pilot.press("greater_than_sign")
        assert not panel(app).display and not app.query_one("#board-detail").display
        await pilot.press("greater_than_sign")
        assert panel(app).display
        await pilot.press("greater_than_sign", "right")  # entering the panel shows it again
        await pilot.pause()
        assert panel(app).display and app.in_panel

    drive(steps)


def test_hiding_the_panel_while_inside_it_returns_to_the_rows(epic_board):
    async def steps(app, pilot):
        await open_panel(app, pilot)
        assert app.in_panel
        await pilot.press("greater_than_sign")
        assert not app.in_panel and app.focused.id == "jobs-table"

    drive(steps)


async def open_new_session(app, pilot):
    await to_row(app, pilot, "Backprop")
    await pilot.press("R")
    await pilot.pause()
    await pilot.press("right", "enter")
    await pilot.pause()
    assert app.screen.__class__.__name__ == "NewSession"


def test_new_session_defaults_to_the_last_agent_and_folder_with_available_context_ticked(epic_board):
    async def steps(app, pilot):
        await open_new_session(app, pilot)
        screen = app.screen
        assert screen.query_one("#agent").value == "copilot"  # the most recently worked session
        assert screen.query_one("#cwd").value == str(epic_board["docs"])
        assert set(screen.query_one("#ctx").selected) == {"tasks", "jobs", "sessions", "artifacts"}

    drive(steps)


def test_ctrl_s_starts_the_session_inside_the_board_with_a_written_brief(epic_board):
    async def steps(app, pilot):
        await open_new_session(app, pilot)
        await pilot.press(*"go")
        await pilot.press("ctrl+s")
        await pilot.pause()
        assert app.screen.__class__.__name__ != "NewSession" and len(app.ran) == 1
        item = core.load_db()["items"][-1]
        assert (item["agent"], item["cwd"], item["summary"]) == ("copilot", str(epic_board["docs"]), "go")
        assert item["job_id"] == core.job_by_ref(core.load_db(), "ML-1")["id"]
        brief = Path(item["brief"]).read_text()
        assert "## Child jobs" in brief and "Gradient check" in brief
        assert f"copilot --session-id {item['session_id']}" in app.ran[0] and "## Your task" in app.ran[0]

    drive(steps)


def test_ctrl_j_starts_too_the_key_most_terminals_send_for_ctrl_enter(epic_board):
    async def steps(app, pilot):
        await open_new_session(app, pilot)
        await pilot.press("ctrl+j")
        await pilot.pause()
        assert len(app.ran) == 1

    drive(steps)


def test_a_folder_that_does_not_exist_keeps_the_dialog_open(epic_board):
    async def steps(app, pilot):
        await open_new_session(app, pilot)
        app.screen.query_one("#cwd").value = "/no/such/place"
        await pilot.press("ctrl+s")
        await pilot.pause()
        assert app.screen.__class__.__name__ == "NewSession" and app.ran == []

    drive(steps)


def test_escape_cancels_the_new_session(epic_board):
    async def steps(app, pilot):
        await open_new_session(app, pilot)
        await pilot.press("escape")
        await pilot.pause()
        assert app.ran == [] and app.screen.__class__.__name__ != "NewSession"

    drive(steps)


def completion(app):
    return app.screen.query_one("#completion")


def test_typing_a_path_floats_folder_suggestions_and_enter_takes_the_picked_one(epic_board):
    async def steps(app, pilot):
        await open_new_session(app, pilot)
        cwd = app.screen.query_one("#cwd")
        cwd.focus()
        await pilot.pause()
        cwd.value = ""
        await pilot.press(*(str(epic_board["docs"].parent) + "/"))
        await pilot.pause()
        box = completion(app)
        assert box.display and box.owner is cwd
        assert {str(epic_board["docs"]) + "/", str(epic_board["work"]) + "/"} <= set(box.values)
        dialog = app.screen.query_one(".dialog").region
        await pilot.press("w")
        await pilot.pause()
        assert box.values == [str(epic_board["work"]) + "/"]
        await pilot.press("enter")
        assert cwd.value == str(epic_board["work"]) + "/"
        assert app.screen.query_one(".dialog").region == dialog  # the box floats; the dialog never moves

    drive(steps)


def test_escape_hides_the_suggestions_before_it_cancels(epic_board):
    async def steps(app, pilot):
        await open_new_session(app, pilot)
        cwd = app.screen.query_one("#cwd")
        cwd.focus()
        cwd.value = ""
        await pilot.press("/")
        await pilot.pause()
        assert completion(app).display
        await pilot.press("escape")
        assert not completion(app).display and app.screen.__class__.__name__ == "NewSession"

    drive(steps)


def test_a_slash_in_the_prompt_suggests_skills_and_arrows_pick_without_moving_the_cursor(epic_board, tmp_path):
    for name in ("jq-clean-ui", "jq-repo-setup"):
        skill = tmp_path / "home" / ".claude" / "skills" / name
        skill.mkdir(parents=True)
        (skill / "SKILL.md").write_text("x")

    async def steps(app, pilot):
        await open_new_session(app, pilot)
        await pilot.press("f", "i", "x", " ", "/", "j", "q")
        await pilot.pause()
        box = completion(app)
        assert box.display and box.values == ["/jq-clean-ui", "/jq-repo-setup"]
        await pilot.press("down", "enter")
        assert app.screen.query_one("#prompt").text == "fix /jq-repo-setup "
        assert not box.display

    drive(steps)


async def to_hand_over(app, pilot, key: str):
    ctx = app.screen.query_one("#ctx")
    ctx.focus()
    await pilot.pause()
    ctx.highlighted = [ctx.get_option_at_index(n).value for n in range(ctx.option_count)].index(key)
    await pilot.pause()
    return ctx


def test_hand_over_previews_a_text_section_in_a_floating_box(epic_board):
    async def steps(app, pilot):
        await open_new_session(app, pilot)
        await to_hand_over(app, pilot, "why")
        assert app.screen.query_one("#peek-text").display and not app.screen.query_one("#peek-list").display

    drive(steps)


def test_hand_over_lists_child_jobs_and_unticking_all_of_them_drops_the_section(epic_board):
    async def steps(app, pilot):
        await open_new_session(app, pilot)
        ctx = await to_hand_over(app, pilot, "jobs")
        box = app.screen.query_one("#peek-list")
        assert box.display and box.option_count == 1 and "Gradient check" in str(box.get_option_at_index(0).prompt)
        await pilot.press("right")
        assert app.focused is box
        await pilot.press("space")
        await pilot.pause()
        assert app.screen.picked["jobs"] == set() and "jobs" not in ctx.selected
        await pilot.press("space")
        await pilot.pause()
        assert app.screen.picked["jobs"] and "jobs" in ctx.selected  # picking one hands the section over again
        await pilot.press("left")
        assert app.focused is ctx

    drive(steps)


def test_only_the_picked_artifacts_reach_the_brief(epic_board):
    async def steps(app, pilot):
        await open_new_session(app, pilot)
        await to_hand_over(app, pilot, "artifacts")
        await pilot.press("right", "space", "ctrl+s")
        await pilot.pause()
        brief = Path(core.load_db()["items"][-1]["brief"]).read_text()
        assert "runbook" not in brief.lower()

    drive(steps)


def test_dragging_the_panels_left_edge_resizes_it(epic_board):
    async def steps(app, pilot):
        await to_row(app, pilot, "Backprop")
        p = panel(app)
        wide = p.size.width
        await pilot.mouse_down(p, offset=(0, 3))
        await pilot.hover(offset=(p.region.x - 20, 5))  # 20 columns to the left
        await pilot.mouse_up(p, offset=(0, 3))
        await pilot.pause()
        assert p.size.width > wide + 10
        await pilot.hover(offset=(p.region.x - 40, 5))  # not dragging any more: nothing moves
        await pilot.pause()
        assert p.size.width > wide + 10 and not p.dragging

    drive(steps)


# ---- the Board shares column mode and the summary panel with Jobs


def test_enter_on_a_board_row_enters_column_mode_and_shift_r_resumes(seeded):
    async def steps(app, pilot):
        await pilot.press("enter")
        assert app.view == "board" and app.col == 0 and app.ran == []
        await pilot.press("escape", "R")
        await pilot.pause()
        assert len(app.ran) == 1 and "--resume" in app.ran[0]

    drive(steps)


def test_board_column_mode_enter_enter_shows_every_task_of_that_job(seeded):
    async def steps(app, pilot):
        table = app.query_one("#table", DataTable)
        while app.table_item()["summary"] != "Vectorise softmax":
            await pilot.press("down")
        await pilot.press("enter", "right", "right", "enter")  # ID -> Job, search its own value
        await pilot.pause()
        assert app.screen.__class__.__name__ == "Suggest"
        await pilot.press("enter")
        await pilot.pause()
        assert app.bfilters == {"job": {"text": "Backprop from scratch"}}
        assert sorted(str(table.get_row_at(n)[3]) for n in range(table.row_count)) == [
            "Vectorise softmax",
            "Write gradient check",
        ]
        await pilot.press("escape")
        assert app.bfilters == {} and app.col == 2

    drive(steps)


def test_right_on_a_board_row_enters_its_panel_and_the_job_entry_jumps_to_jobs(seeded):
    async def steps(app, pilot):
        while app.table_item()["summary"] != "Vectorise softmax":
            await pilot.press("down")
        await pilot.press("right")
        await pilot.pause()
        board_panel = app.query_one("#board-detail")
        assert app.focused is board_panel and app.in_panel
        keys = [board_panel.get_option_at_index(n).id for n in range(board_panel.option_count)]
        assert [k for k in keys if k] == [
            "job:1",
            "session:copilot:bbbb2222-0000-0000-0000-000000000002",
            "artifacts",
            "notes",
        ]
        await pilot.press("enter")  # on the job
        await pilot.pause()
        assert app.view == "jobs" and app.current_job()["name"] == "Backprop from scratch"

    drive(steps)


def test_a_board_tasks_session_entry_offers_resume(seeded):
    async def steps(app, pilot):
        while app.table_item()["summary"] != "Vectorise softmax":
            await pilot.press("down")
        await pilot.press("right", "down", "enter")
        await pilot.pause()
        assert app.screen.__class__.__name__ == "SessionActions"
        await pilot.press("enter")
        await pilot.pause()
        assert app.ran == ["cd /d && copilot --resume=bbbb2222-0000-0000-0000-000000000002"]

    drive(steps)


def test_the_picked_header_is_orange(seeded):
    from fu.tui import HEADER_PICKED

    async def steps(app, pilot):
        await pilot.press("1", "enter")
        label = list(jobs_table(app).columns.values())[0].label
        assert str(label.style) == HEADER_PICKED

    drive(steps)


# ---- the job form


def test_the_parent_field_searches_jobs_by_id_or_name(seeded):
    async def steps(app, pilot):
        await pilot.press("1")
        await select_job(app, pilot, "ReLU derivative bug")
        await pilot.press("e")
        await pilot.pause()
        form = app.screen
        form.query_one("#row-parent").focus()
        await pilot.press("enter")
        await pilot.pause()
        box = form.query_one("#completion")
        assert box.display and box.values == ["J1"]  # every other job; never itself
        await pilot.press(*"back")
        await pilot.pause()
        assert box.values == ["J1"]
        await pilot.press("enter", "enter")  # take the pick, then leave the field
        await pilot.press("ctrl+s")
        await pilot.pause()
        db = core.load_db()
        assert core.job_by_ref(db, "ReLU derivative bug")["parent_id"] == 1

    drive(steps)


def test_the_home_folder_is_saved_and_shown_with_a_tilde(seeded, isolated):
    home = isolated / "home" / "repo"
    home.mkdir(parents=True)

    async def steps(app, pilot):
        await pilot.press("1")
        await select_job(app, pilot, "ReLU derivative bug")
        await pilot.press("e")
        await pilot.pause()
        form = app.screen
        form.query_one("#row-home").focus()
        await pilot.press("enter", *"~/re")
        await pilot.pause()
        assert form.query_one("#completion").values == ["~/repo/"]
        await pilot.press("enter", "enter", "ctrl+s")
        await pilot.pause()
        assert core.job_by_ref(core.load_db(), "ReLU derivative bug")["home"] == str(home.resolve())

    drive(steps)


def test_a_quick_right_straight_after_enter_moves_the_column_not_into_the_panel(seeded):
    async def steps(app, pilot):
        await pilot.press("1", "enter", "right")
        assert app.col == 1 and not app.in_panel

    drive(steps)
