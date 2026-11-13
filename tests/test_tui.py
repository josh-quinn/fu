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


def test_enter_on_a_job_filters_the_board_and_c_clears_it(seeded):
    # Regression: clearing the filter after Enter on a job crashed, because the job
    # detail panel looked the job up through a view-dependent helper.
    async def steps(app, pilot):
        await pilot.press("2", "down", "enter")
        await pilot.pause()
        assert app.view == "board" and app.filters == {"job": 1}
        assert app.query_one(DataTable).row_count == 2
        await pilot.press("c")
        await pilot.pause()
        assert app.filters == {} and app.query_one(DataTable).row_count == 3

    drive(steps)


def test_a_job_spread_over_sessions_shows_its_sessions_first(seeded):
    async def steps(app, pilot):
        await pilot.press("2", "down", "right")
        await pilot.pause()
        job_node = app.nodes[("job", 1)]
        assert job_node.is_expanded
        assert [c.data[0] for c in job_node.children] == ["jobsess", "jobsess"]

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
        await pilot.press("2", "a")
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
        await pilot.press("2", "a", "enter", *"Orphan", "enter", "down", "down", "down")
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
