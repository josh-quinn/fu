"""Drive the real Textual app headlessly. Each test pins behaviour that once broke."""

import asyncio

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


def test_enter_on_a_job_asks_before_restarting_its_latest_session(seeded):
    async def steps(app, pilot):
        await pilot.press("1")
        await select_job(app, pilot, "Backprop from scratch")  # the epic with two sessions
        await pilot.press("enter")
        assert app.screen.__class__.__name__ == "Confirm"
        await pilot.press("n")
        assert app.pick is None and app.view == "jobs"
        await pilot.press("enter", "y")
        assert app.pick == "2"  # the most recently worked task of the job: "Vectorise softmax"

    drive(steps)


def test_enter_on_a_job_with_no_session_just_says_so(seeded):
    async def steps(app, pilot):
        db = core.load_db()
        core.create_job(db, "Cheatsheet", "btw")
        core.save_db(db)
        app.reload()
        await pilot.press("1")
        await select_job(app, pilot, "Cheatsheet")
        await pilot.press("enter")
        assert app.screen.__class__.__name__ != "Confirm"

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
