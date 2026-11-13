"""Drive the real Textual app headlessly. Each test pins behaviour that once broke."""

import asyncio

import pytest

pytest.importorskip("textual")

from textual.widgets import DataTable, Input  # noqa: E402

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


def test_tab_moves_between_form_fields(seeded):
    # Regression: the dialog guard disabled Textual's own focus action, so Tab did nothing
    # and everything typed landed in the first field.
    async def steps(app, pilot):
        await pilot.press("a")
        await pilot.press(*"summary text", "tab", *"why text")
        values = {i.id: i.value for i in app.screen.query(Input)}
        assert values["summary"] == "summary text" and values["why"] == "why text"

    drive(steps)


def test_adding_a_task_with_a_new_name_creates_the_job(seeded):
    async def steps(app, pilot):
        await pilot.press("a")
        await pilot.press(*"Plan outline", "tab", "tab", *"Week 2 report", "ctrl+s")
        await pilot.pause()
        db = core.load_db()
        assert any(j["name"] == "Week 2 report" for j in db["jobs"])
        assert any(i["summary"] == "Plan outline" and i["job_id"] for i in db["items"])

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
