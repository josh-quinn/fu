"""The interactive board (Textual). Imported lazily so plain CLI calls stay fast."""

import os
from datetime import date
from pathlib import Path

from fu import artifacts, launch, summary
from fu.core import (
    AGENTS,
    DATE_COLUMNS,
    DEFAULT_KIND,
    KIND_GLYPH,
    KINDS,
    MONTHS,
    STATUSES,
    age,
    check_ext_id,
    clip,
    create_job,
    date_range,
    descendants,
    filter_jobs,
    fmt_date,
    heat,
    home_path,
    idle_days,
    job_by_ref,
    job_label,
    job_name,
    job_resume_item,
    job_rows,
    key_modifier,
    load_db,
    matches,
    new_item,
    range_options,
    remove_job,
    resume_cmd,
    save_db,
    set_parent,
    sort_board,
    sort_jobs,
    suggestions,
    today,
    update,
)

# -------------------------------------------------------------------- TUI

JOB_COLUMNS_UI = [
    ("id", "ID"),
    ("kind", "Type"),
    ("parent", "Parent"),
    ("title", "Title"),
    ("added", "Added"),
    ("last_worked", "Last worked"),
]
ORANGE = "#ffa62b"  # the cursor colour: the highlighted row, and the header picked on the headers or in column mode
COLUMN_TINT = "on grey19"  # background of the column picked in column mode
HEADER_PICKED = f"bold black on {ORANGE}"
LIST_ROWS_TYPING = 6
LIST_ROWS_EMPTY = 15
COLUMNS = [
    ("id", "ID"),
    ("status", "Status"),
    ("job", "Job"),
    ("summary", "Summary"),
    ("added", "Added"),
    ("last_worked", "Last worked"),
]

HELP = """\
[b]Screens[/]
  [b]2[/]  Board   every follow-up in one list (the default screen)
  [b]1[/]  Jobs    your jobs as a table: ID, Type, Parent, Title, Added, Last worked
  [b]↑[/]  from the first row, step onto the column headers; [b]↑[/] again reaches the Jobs / Board tabs,
     where [b]← →[/] switch screen and [b]↓[/] comes back to the headers
  [b]←[/]  on the Board's first header: swipe over to Jobs;  [b]→[/] on the Jobs table's last header: to the Board
  [b]shift+.[/] (>)  show or hide the summary / detail panel

[b]Moving and starting sessions[/]
  [b]↑ ↓[/]     move through the rows
  [b]enter[/]   Board: resume the highlighted session (runs its restart command and exits)
          Jobs: pick a whole column to search (see Column mode)
  [b]shift+r[/] (R)  on a job (or inside its summary panel): sessions exist, so choose [b]Restart[/] or [b]New Session[/]
          ([b]← →[/] choose, [b]↑ ↓[/] pick the session to restart). No sessions: go straight to New Session.
          New Session asks for the agent, which context to hand over (why, notes, artifacts, parent, child
          jobs, earlier sessions), a first prompt (type [b]/[/] for skills) and the folder (type a path for
          live suggestions). [b]tab[/] completes, [b]ctrl+n[/] / [b]ctrl+p[/] pick, [b]ctrl+s[/] starts.

[b]Working on a task[/]
  [b]a[/]  add a task (in the Jobs view: add a job)
  [b]e[/]  edit the task or job (the session, agent and folder are locked)
  [b]s[/]  cycle status: todo > doing > done
  [b]d[/]  mark done (kept until you delete it)
  [b]t[/]  set last worked to today
  [b]y[/]  copy the restart command
  [b]x[/]  delete the task (or job: its tasks are kept, unassigned; child jobs move up)

[b]Sorting (Board)[/]
  [b]↑[/]      from the first row, step up onto the column headers
  [b]← →[/]    move between headers          [b]↓[/] or [b]esc[/]  back to the rows
  [b]enter[/]  sort by that header; again to flip ascending / descending (it is always one or the other)
  Ties fall back to: job > status > last worked > added;  status > last worked > added.

[b]Filtering (Jobs)[/]
  On a column header, just start typing to search it, or press [b]enter[/] to open the box. The list suggests
  matches (an empty box lists everything; once you type, 6 show and the rest scroll) while the table filters
  live. [b]↑ ↓[/] pick a suggestion; [b]enter[/] locks it in (on an empty box it clears that column);
  [b]esc[/] puts the old filter back. The box does not dim the table behind it.
  Type  lists all seven kinds before you type, and searches them as you type.
  Added / Last worked  open a date picker on today: [b]← →[/] move across Month, Day, Year, Apply, Clear;
          [b]enter[/] on Month, Day or Year to type and pick; Apply filters to that day. [b]↓[/] to
          "Select by…" and [b]enter[/] to filter a whole week, month or year.
  [b]c[/]  clear every filter (the first [b]esc[/] just steps off the headers)

[b]Column mode (Jobs)[/]
  [b]enter[/]  on a row: the whole Title column lights up.  [b]← →[/] pick another column, [b]↑ ↓[/] move the row.
  [b]enter[/]  searches that column starting from the highlighted row's own value, so enter, enter shows every
          job with the same parent (or type, or title). Typing instead starts a fresh search.
  [b]esc[/]    brings back every result; a second esc leaves column mode.
  While in column mode plain letters type, so use Ctrl for shortcuts: [b]ctrl+a[/] add, [b]ctrl+e[/] edit,
  [b]ctrl+d[/] done, [b]ctrl+y[/] copy ... The modifier is [b]modifier[/] under \\[keys] in
  ~/.config/jq-tools/follow-ups/config.toml ("ctrl" by default; "alt" or "super" if you prefer). To switch
  screens leave column mode with [b]esc[/] and press 1 / 2. [b]F1[/] opens help. [b].[/] and [b]R[/] stay plain.

[b]The summary panel (Jobs)[/]
  [b]→[/]      on a job row, step into the panel on the right;  [b]←[/] (or esc) goes back to the rows
  [b]↑ ↓[/]    move between its entries: Parent, child Jobs, Sessions, Artifacts, Notes. The cursor starts on
          the parent when there is one. Long names are cut to one line; rest on one for a second to see all.
  [b]enter[/]  on a job or the parent: jump to that job (you stay in the panel)
          on a session: Restart it, or Open session folder
          on Artifacts: a list of what the sessions left (runbooks, explainers, skills, repos);
                        enter opens one in its app, [b]x[/] hides a wrong guess
          on Notes: add or edit a note ([b]ctrl+s[/] saves)
  Drag the panel's left edge with the mouse to resize it.

[b]Filtering (Board)[/]
  [b]f[/] or [b]/[/]  filter by text, job, status, agent, session, idle days, recently worked
  [b]c[/] or [b]esc[/]  clear all filters
  [b].[/]  show or hide done tasks

[b]Good to know[/]
  [b]Done tasks are never auto-deleted.[/] [b].[/] only hides them; they stay in board.json until you press x.
  Last worked is [green]green[/] under 3 days, [yellow]yellow[/] under 7, [red]red[/] after that.
  A task belongs to one job and one session. Jobs and sessions are many-to-many through their tasks.
  [b]h[/] or [b]?[/]  this help      [b]q[/]  quit

[dim]esc, h or q to close[/]"""


def build_app():
    """Build the Textual app (separate from run_tui so tests can drive it headlessly)."""
    from rich.markup import escape
    from rich.text import Text
    from textual.app import App, ComposeResult
    from textual.binding import Binding
    from textual.containers import Horizontal, Vertical, VerticalScroll
    from textual.screen import ModalScreen
    from textual.widgets import (
        ContentSwitcher,
        DataTable,
        Footer,
        Header,
        Input,
        Label,
        OptionList,
        Select,
        SelectionList,
        Static,
        TextArea,
    )
    from textual.widgets.option_list import Option

    BADGE = {"todo": ("○ todo", "yellow"), "doing": ("◐ doing", "cyan"), "done": ("● done", "green")}

    class Help(ModalScreen[None]):
        BINDINGS = [("escape,h,q,question_mark", "close", "Close")]

        def compose(self) -> ComposeResult:
            with VerticalScroll(classes="dialog wide"):
                yield Label("[b]follow-ups help[/]")
                yield Static(HELP)

        def action_close(self) -> None:
            self.dismiss(None)

    class Confirm(ModalScreen[bool]):
        BINDINGS = [("y", "yes", "Yes"), ("n,escape", "no", "No")]

        def __init__(self, question: str) -> None:
            super().__init__()
            self.question = question

        def compose(self) -> ComposeResult:
            with Vertical(classes="dialog"):
                yield Label(self.question)
                yield Label("[dim]y / n[/]")

        def action_yes(self) -> None:
            self.dismiss(True)

        def action_no(self) -> None:
            self.dismiss(False)

    class Form(ModalScreen["dict | None"]):
        """A stack of single-line inputs; subclasses set FIELDS and validate()."""

        BINDINGS = [("escape", "cancel", "Cancel"), ("ctrl+s", "save", "Save")]
        FIELDS: list[tuple[str, str]] = []

        def __init__(self, heading: str, values: dict | None = None) -> None:
            super().__init__()
            self.heading, self.values = heading, values or {}

        def compose(self) -> ComposeResult:
            with Vertical(classes="dialog"):
                yield Label(f"[b]{self.heading}[/]")
                for key, label in self.FIELDS:
                    yield Label(label, classes="field")
                    yield Input(value=str(self.values.get(key) or ""), id=key)
                yield Label("[dim]enter next · ctrl+s save · esc cancel[/]", classes="field")

        def on_mount(self) -> None:
            self.query_one(f"#{self.FIELDS[0][0]}", Input).focus()

        def on_input_submitted(self, event: Input.Submitted) -> None:
            if event.input.id == self.FIELDS[-1][0]:
                self.action_save()
            else:
                self.focus_next()

        def validate(self, values: dict) -> str | None:
            return None

        def action_save(self) -> None:
            values = {k: self.query_one(f"#{k}", Input).value.strip() for k, _ in self.FIELDS}
            problem = self.validate(values)
            if problem:
                self.notify(problem, severity="error")
            else:
                self.dismiss(values)

        def action_cancel(self) -> None:
            self.dismiss(None)

    class FieldRow(Static, can_focus=True):
        """One form value shown as a row; Enter turns it into an editor."""

    class RowForm(ModalScreen["dict | None"]):
        """Rows you move through with the arrows. Enter edits a row, Enter again leaves it.

        FIELDS are (key, label, mode); mode is "text", "readonly" (greyed, skipped by the arrows), a
        tuple of options (a dropdown), "job" (searchable list of jobs) or "folder" (path with suggestions).
        """

        BINDINGS = [
            Binding("escape", "back", "Back"),
            Binding("ctrl+s", "save", "Save"),
            Binding("up,shift+tab", "move(-1)", show=False),
            Binding("down,tab", "move(1)", show=False),
            Binding("enter", "edit_row", show=False),
        ]
        FIELDS: list[tuple[str, str, object]] = []

        def __init__(self, heading: str, values: dict | None = None, jobs: list[tuple[str, str]] | None = None) -> None:
            super().__init__()
            self.heading = heading
            self.vals = {k: str((values or {}).get(k) or "") for k, _, _ in self.FIELDS}
            self.jobs = jobs or []  # (label, name) the "job" fields choose from
            self.editing: str | None = None

        def compose(self) -> ComposeResult:
            with Vertical(classes="frame"), Vertical(classes="dialog"):
                yield Label(f"[b]{self.heading}[/]")
                for key, label, mode in self.FIELDS:
                    yield Label(
                        label + (" [dim](set by the session)[/]" if mode == "readonly" else ""), classes="field"
                    )
                    yield FieldRow(self.shown(key), id=f"row-{key}", classes="row ro" if mode == "readonly" else "row")
                    if isinstance(mode, tuple):
                        yield Select(
                            [(o, o) for o in mode],
                            value=self.vals[key] if self.vals[key] in mode else mode[0],
                            allow_blank=False,
                            id=f"edit-{key}",
                        )
                    elif mode == "text":
                        yield Input(value=self.vals[key], id=f"edit-{key}")
                    elif mode == "job":
                        yield PickInput(self.vals[key], lambda: self.jobs, id=f"edit-{key}")
                    elif mode == "folder":
                        yield PathInput(self.vals[key], id=f"edit-{key}")
                yield Label("[dim]↑↓ move · enter edit / confirm · ctrl+s save · esc back[/]", classes="field")
            yield Completion()

        def on_mount(self) -> None:
            for editor in self.query(".dialog Input, .dialog Select"):
                editor.display = False
            for key, _, mode in self.FIELDS:
                self.query_one(f"#row-{key}", FieldRow).can_focus = mode != "readonly"
            first = next((k for k, _, m in self.FIELDS if m != "readonly"), None)
            if first:
                self.query_one(f"#row-{first}").focus()

        def shown(self, key: str) -> str:
            value = self.vals[key]
            name = dict(self.jobs).get(value) if {k: m for k, _, m in self.FIELDS}[key] == "job" else None
            return (escape(value) + (f"  [dim]{escape(name)}[/]" if name else "")) if value else "[dim]-[/]"

        def rows(self) -> list:
            return [r for r in self.query(FieldRow) if r.can_focus]

        def action_move(self, step: int) -> None:
            rows = self.rows()
            if self.editing or not rows:
                return
            now = rows.index(self.focused) if self.focused in rows else 0
            rows[max(0, min(len(rows) - 1, now + step))].focus()

        def action_edit_row(self) -> None:
            if self.editing or not isinstance(self.focused, FieldRow):
                return
            key = self.focused.id.removeprefix("row-")
            self.editing = key
            self.focused.display = False
            editor = self.query_one(f"#edit-{key}")
            editor.display = True
            if isinstance(editor, Input):
                editor.value = self.vals[key]
            editor.focus()
            if isinstance(editor, Select):
                editor.call_after_refresh(setattr, editor, "expanded", True)

        def leave_edit(self, keep: bool) -> None:
            key = self.editing
            if key is None:
                return
            editor = self.query_one(f"#edit-{key}")
            if keep and editor.value is not Select.BLANK:
                self.vals[key] = str(editor.value).strip()
            self.editing = None
            editor.display = False
            row = self.query_one(f"#row-{key}", FieldRow)
            row.update(self.shown(key))
            row.display = True
            row.focus()

        def on_input_submitted(self, event: Input.Submitted) -> None:
            event.stop()
            self.leave_edit(keep=True)

        def on_select_changed(self, event: Select.Changed) -> None:
            event.stop()
            if self.editing and event.select.id == f"edit-{self.editing}":
                self.leave_edit(keep=True)

        def validate(self, values: dict) -> str | None:
            return None

        def action_save(self) -> None:
            self.leave_edit(keep=True)
            editable = {k: self.vals[k] for k, _, m in self.FIELDS if m != "readonly"}
            problem = self.validate(editable)
            if problem:
                self.notify(problem, severity="error")
            else:
                self.dismiss(editable)

        def action_back(self) -> None:
            if self.editing:
                self.leave_edit(keep=False)
            else:
                self.dismiss(None)

    class ItemForm(RowForm):
        FIELDS = [
            ("summary", "Summary (one line)", "text"),
            ("why", "Why you started this", "text"),
            ("job", "Job (name or id; a new name creates a job; blank for none)", "text"),
            ("cwd", "Folder", "readonly"),
            ("agent", "Agent", "readonly"),
            ("session_id", "Session id", "readonly"),
        ]

        def validate(self, v: dict) -> str | None:
            return None if v["summary"] else "Summary is required"

    class JobForm(RowForm):
        FIELDS = [
            ("name", "Title", "text"),
            ("ext_id", "ID (optional, e.g. a Jira key)", "text"),
            ("kind", "Type", tuple(KINDS)),
            ("parent", "Parent job (type to search; blank for none)", "job"),
            ("home", "Home folder (new sessions start here)", "folder"),
            ("description", "Description", "text"),
        ]

        def validate(self, v: dict) -> str | None:
            return None if v["name"] else "Title is required"

    class FilterForm(Form):
        FIELDS = [
            ("text", "Text in summary / why / notes"),
            ("job", "Job (name, or 'none')"),
            ("status", "Status (todo / doing / done)"),
            ("agent", "Agent (claude / copilot)"),
            ("session", "Session (id fragment, or 'none')"),
            ("idle", "Idle for at least N days"),
            ("recent", "Worked within the last N days"),
        ]

        def validate(self, v: dict) -> str | None:
            if v["status"] and v["status"] not in STATUSES:
                return "Status must be todo, doing or done"
            if v["agent"] and v["agent"] not in AGENTS:
                return "Agent must be claude or copilot"
            for k in ("idle", "recent"):
                if v[k] and not v[k].isdigit():
                    return f"{k} must be a whole number of days"
            return None

    def size_list(opts, typed: str) -> None:
        """An empty search shows every option (up to what fits on screen); once you type, six rows show
        and the rest scroll."""
        opts.styles.max_height = LIST_ROWS_TYPING if typed.strip() else LIST_ROWS_EMPTY

    class Suggest(ModalScreen["str | None"]):
        """A search box with a live suggestion list (6 rows, scrolls). Typing filters the list and,
        through `live`, the board behind it. Up/Down pick a suggestion; Enter locks in the picked
        suggestion, or what was typed when none is picked. Esc cancels."""

        BINDINGS = [
            Binding("escape", "cancel", "Cancel"),
            Binding("up", "move(-1)", show=False),
            Binding("down", "move(1)", show=False),
        ]

        def __init__(self, title: str, options, initial: str, live, x: int) -> None:
            super().__init__()
            self.title_text, self.options, self.initial, self.live, self.x = title, options, initial, live, x

        def compose(self) -> ComposeResult:
            with Vertical(classes="popup"):
                yield Label(f"[b]{self.title_text}[/] [dim]search · ↑↓ pick · enter locks · esc[/]")
                yield Input(value=self.initial, id="q")
                yield OptionList(id="opts")

        def on_mount(self) -> None:
            self.styles.align = ("left", "top")
            self.query_one(".popup").styles.margin = (4, 0, 0, self.x)
            self.query_one(OptionList).can_focus = False
            self.fill(self.initial)
            box = self.query_one(Input)
            box.focus()
            box.cursor_position = len(self.initial)
            if self.initial:
                self.live(self.initial.strip())

        def fill(self, text: str) -> None:
            opts = self.query_one(OptionList)
            opts.clear_options()
            opts.add_options(self.options(text))
            opts.highlighted = None
            size_list(opts, text)

        def on_input_changed(self, event: Input.Changed) -> None:
            event.stop()
            self.fill(event.value)
            self.live(event.value.strip())

        def on_input_submitted(self, event: Input.Submitted) -> None:
            event.stop()
            opts = self.query_one(OptionList)
            if opts.highlighted is not None:
                self.dismiss(str(opts.get_option_at_index(opts.highlighted).prompt))
            else:
                self.dismiss(event.value.strip())

        def action_move(self, step: int) -> None:
            opts = self.query_one(OptionList)
            opts.action_cursor_down() if step > 0 else opts.action_cursor_up()

        def action_cancel(self) -> None:
            self.dismiss(None)

    class DatePick(ModalScreen["dict | None"]):
        """Month / Day / Year segments (←→ move, enter edits one with type-to-filter), Apply, Clear,
        and 'Select by…' for a whole week, month or year. Returns a filter dict, {"clear": True} or None."""

        BINDINGS = [
            Binding("escape", "back", "Back"),
            Binding("left", "step(-1)", show=False),
            Binding("right", "step(1)", show=False),
            Binding("up", "vert(-1)", show=False),
            Binding("down", "vert(1)", show=False),
            Binding("enter", "choose", show=False),
        ]
        RING = ("month", "day", "year", "apply", "clear")
        AUTO_FOCUS = ""  # the picker's own bindings need the keys; the hidden search box must not grab them

        def __init__(self, title: str, start: date, x: int) -> None:
            super().__init__()
            self.title_text, self.x = title, x
            self.y, self.m, self.d = start.year, start.month, start.day
            self.row, self.pos = 0, 0
            self.sub: str | None = None  # what the open list is choosing
            self.choices: list = []  # (label, value) behind the open list

        def compose(self) -> ComposeResult:
            with Vertical(classes="popup"):
                yield Label(f"[b]{self.title_text}[/] [dim]←→ move · enter select · esc[/]")
                yield Static(id="dateline")
                yield Static(id="byline")
                yield Input(id="q")
                yield OptionList(id="opts")

        def on_mount(self) -> None:
            self.styles.align = ("left", "top")
            self.query_one(".popup").styles.margin = (4, 0, 0, self.x)
            self.query_one(OptionList).can_focus = False
            self.hide_list()
            self.draw()

        def day_count(self) -> int:
            return (date(self.y + (self.m == 12), self.m % 12 + 1, 1) - date(self.y, self.m, 1)).days

        def draw(self) -> None:
            def seg(name: str, text: str) -> str:
                on = self.row == 0 and self.RING[self.pos] == name
                return f"[reverse b] {text} [/]" if on else f" {text} "

            line = (
                seg("month", MONTHS[self.m - 1])
                + seg("day", str(self.d))
                + seg("year", str(self.y))
                + "   "
                + seg("apply", "Apply")
                + seg("clear", "Clear")
            )
            self.query_one("#dateline", Static).update(line)
            by = "Select by…  [dim]week · month · year[/]"
            self.query_one("#byline", Static).update(f"[reverse b] {by} [/]" if self.row == 1 else f" {by} ")

        def hide_list(self) -> None:
            self.sub = None
            self.query_one("#q").display = False
            self.query_one("#opts").display = False
            self.set_focus(None)

        def open_list(self, sub: str, choices: list) -> None:
            self.sub, self.choices = sub, choices
            q = self.query_one("#q", Input)
            q.value = ""
            q.display = True
            self.query_one("#opts").display = True
            self.fill("")
            q.focus()

        def fill(self, text: str) -> None:
            opts = self.query_one(OptionList)
            opts.clear_options()
            low = text.strip().lower()
            hits = [c for c in self.choices if low in c[0].lower()]
            self.shown = sorted(hits, key=lambda c: not c[0].lower().startswith(low))
            opts.add_options([c[0] for c in self.shown])
            opts.highlighted = None
            size_list(opts, text)

        def on_input_changed(self, event: Input.Changed) -> None:
            event.stop()
            if self.sub:
                self.fill(event.value)

        def on_input_submitted(self, event: Input.Submitted) -> None:
            event.stop()
            if not (self.sub and self.shown):
                return
            opts = self.query_one(OptionList)
            label, value = self.shown[opts.highlighted if opts.highlighted is not None else 0]
            sub = self.sub
            self.hide_list()
            if sub == "by":
                self.open_list(
                    f"range:{value}", [(lab, (lo, hi)) for lab, lo, hi in range_options(value, date.today())]
                )
            elif sub.startswith("range:"):
                self.dismiss({"from": value[0], "to": value[1], "label": label})
            else:
                setattr(self, {"month": "m", "day": "d", "year": "y"}[sub], value)
                self.d = min(self.d, self.day_count())
                self.draw()

        def action_step(self, step: int) -> None:
            if self.sub or self.row:
                return
            self.pos = max(0, min(len(self.RING) - 1, self.pos + step))
            self.draw()

        def action_vert(self, step: int) -> None:
            if self.sub:
                opts = self.query_one(OptionList)
                opts.action_cursor_down() if step > 0 else opts.action_cursor_up()
                return
            self.row = max(0, min(1, self.row + step))
            self.draw()

        def action_choose(self) -> None:
            if self.sub:
                return
            if self.row == 1:
                self.open_list("by", [(u.capitalize(), u) for u in ("week", "month", "year")])
                return
            name = self.RING[self.pos]
            if name == "apply":
                lo, hi = date_range("day", date(self.y, self.m, self.d))
                self.dismiss({"from": lo, "to": hi, "label": fmt_date(date(self.y, self.m, self.d))})
            elif name == "clear":
                self.dismiss({"clear": True})
            elif name == "month":
                self.open_list("month", [(m, n + 1) for n, m in enumerate(MONTHS)])
            elif name == "day":
                self.open_list("day", [(str(n), n) for n in range(1, self.day_count() + 1)])
            else:
                first = date.today().year - 5
                self.open_list("year", [(str(n), n) for n in range(first, date.today().year + 2)])

        def action_back(self) -> None:
            if self.sub:
                self.hide_list()
            else:
                self.dismiss(None)

    class SummaryList(OptionList):
        """The Jobs summary panel: Up/Down walk its entries, Enter acts on one, Left goes back to the rows."""

        BINDINGS = [Binding("left,escape", "back", show=False)]
        REVEAL_AFTER = 1.0  # seconds the cursor rests on a long entry before its full text shows in place

        def __init__(self, *args, **kwargs) -> None:
            super().__init__(*args, **kwargs)
            self.full: dict[str, Text] = {}  # option id -> the entry's whole text
            self.revealed: str | None = None
            self.timer = None
            self.dragging = False

        def action_back(self) -> None:
            self.app.focus_rows()

        def entry_id(self) -> str | None:
            return None if self.highlighted is None else self.get_option_at_index(self.highlighted).id

        def collapse(self) -> None:
            """Back to one truncated line; a keystroke or a move of the cursor does this."""
            if self.timer:
                self.timer.stop()
                self.timer = None
            if self.revealed in self.full:
                self.replace_option_prompt(self.revealed, self.clip(self.full[self.revealed]))
            self.revealed = None

        @staticmethod
        def clip(text: Text) -> Text:
            clipped = text.copy()
            clipped.no_wrap, clipped.overflow = True, "ellipsis"
            return clipped

        def arm(self) -> None:
            self.collapse()
            if self.entry_id() in self.full:
                self.timer = self.set_timer(self.REVEAL_AFTER, self.reveal)

        def reveal(self) -> None:
            self.timer = None
            key = self.entry_id()
            if key in self.full and self.full[key].cell_len > self.size.width - 4:
                self.replace_option_prompt(key, self.full[key])
                self.revealed = key

        def on_option_list_option_highlighted(self, event) -> None:
            self.arm()

        # Drag the panel's left edge to resize it.
        EDGE = 2  # columns from the left edge that grab the drag
        MIN_WIDTH = 24

        def on_mouse_down(self, event) -> None:
            if event.x < self.EDGE:
                self.dragging = True
                self.capture_mouse()
                event.stop()

        def on_mouse_move(self, event) -> None:
            if self.dragging:
                room = self.screen.size.width - 4 - 30  # the table keeps at least 30 columns
                self.styles.width = max(self.MIN_WIDTH, min(room, self.screen.size.width - 2 - event.screen_x))
                event.stop()

        def on_mouse_up(self, event) -> None:
            if self.dragging:
                self.dragging = False
                self.release_mouse()
                event.stop()

        def on_key(self, event) -> None:
            if self.revealed:
                self.arm()

        def actionable(self) -> list[int]:
            return [n for n in range(self.option_count) if not self.get_option_at_index(n).disabled]

        # Stop at the first and last entry instead of wrapping round, like every other list here.
        def action_cursor_down(self) -> None:
            if self.highlighted is None or self.highlighted < max(self.actionable(), default=0):
                super().action_cursor_down()

        def action_cursor_up(self) -> None:
            if self.highlighted is None or self.highlighted > min(self.actionable(), default=0):
                super().action_cursor_up()

    def chips(options: list[tuple[str, str]], on: str) -> str:
        """A row of buttons; the chosen one is lit."""
        return "   ".join(f"[reverse b] {label} [/]" if key == on else f"[dim] {label} [/]" for key, label in options)

    class SessionActions(ModalScreen["str | None"]):
        """Enter on a session: two buttons, Resume and Session folder. ← → choose, enter runs it, esc closes."""

        AUTO_FOCUS = ""
        BINDINGS = [
            Binding("escape", "close", "Close"),
            Binding("left", "pick(-1)", show=False),
            Binding("right", "pick(1)", show=False),
            Binding("enter", "choose", show=False),
        ]
        BUTTONS = [("resume", "Resume"), ("folder", "Session folder")]

        def __init__(self, label: str) -> None:
            super().__init__()
            self.label, self.on = label, "resume"

        def compose(self) -> ComposeResult:
            with Vertical(classes="dialog"):
                yield Label(f"[b]{escape(self.label)}[/]")
                yield Static(id="buttons", classes="field")
                yield Label("[dim]← → choose · enter · esc closes[/]", classes="field")

        def on_mount(self) -> None:
            self.draw()

        def draw(self) -> None:
            self.query_one("#buttons", Static).update(chips(self.BUTTONS, self.on))

        def action_pick(self, step: int) -> None:
            self.on = self.BUTTONS[1 if step > 0 else 0][0]
            self.draw()

        def action_choose(self) -> None:
            self.dismiss(self.on)

        def action_close(self) -> None:
            self.dismiss(None)

    class NotesForm(ModalScreen["str | None"]):
        BINDINGS = [Binding("escape", "cancel", "Cancel"), Binding("ctrl+s", "save", "Save")]

        def __init__(self, text: str) -> None:
            super().__init__()
            self.text = text

        def compose(self) -> ComposeResult:
            with Vertical(classes="dialog wide"):
                yield Label("[b]Notes[/] [dim]ctrl+s saves · esc cancels[/]")
                yield TextArea(self.text, id="notes-text")

        def on_mount(self) -> None:
            area = self.query_one(TextArea)
            area.focus()
            area.move_cursor(area.document.end)

        def action_save(self) -> None:
            self.dismiss(self.query_one(TextArea).text.strip())

        def action_cancel(self) -> None:
            self.dismiss(None)

    class SessionChoice(ModalScreen["dict | None"]):
        """The job already has sessions: ← → pick Restart or New Session; on Restart ↑ ↓ pick which one."""

        AUTO_FOCUS = ""  # keys are the screen's own; the list is only displayed

        BINDINGS = [
            Binding("escape", "cancel", "Cancel"),
            Binding("left", "pick(-1)", show=False),
            Binding("right", "pick(1)", show=False),
            Binding("up", "move(-1)", show=False),
            Binding("down", "move(1)", show=False),
            Binding("enter", "choose", show=False),
        ]

        def __init__(self, sessions: list[tuple[str, str]]) -> None:
            super().__init__()
            self.sessions = sessions  # (task id, line)
            self.mode = "restart"

        def compose(self) -> ComposeResult:
            with Vertical(classes="dialog"):
                yield Static(id="choice")
                yield OptionList(*[Option(line, id=tid) for tid, line in self.sessions], id="sessions")
                yield Label(id="hint")

        def on_mount(self) -> None:
            opts = self.query_one(OptionList)
            opts.can_focus = False
            opts.highlighted = 0
            self.draw()

        def draw(self) -> None:
            self.query_one("#choice", Static).update(chips([("restart", "Restart"), ("new", "New Session")], self.mode))
            self.query_one("#sessions").display = self.mode == "restart"
            self.query_one("#hint", Label).update(
                "[dim]← → restart or new · ↑ ↓ session · enter · esc cancels[/]"
                if self.mode == "restart"
                else "[dim]← → restart or new · enter sets it up · esc cancels[/]"
            )

        def action_pick(self, step: int) -> None:
            self.mode = "new" if step > 0 else "restart"
            self.draw()

        def action_move(self, step: int) -> None:
            opts = self.query_one(OptionList)
            at = opts.highlighted or 0
            if self.mode == "restart" and 0 <= at + step < opts.option_count:
                opts.highlighted = at + step

        def action_choose(self) -> None:
            if self.mode == "new":
                self.dismiss({"new": True})
            else:
                opts = self.query_one(OptionList)
                self.dismiss({"restart": opts.get_option_at_index(opts.highlighted or 0).id})

        def action_cancel(self) -> None:
            self.dismiss(None)

    class Completion(OptionList):
        """A Helix-style suggestion box that floats under the cursor of the field it serves, over
        whatever is there, so nothing in the dialog moves. Each line is a value and a dim kind."""

        MAX_ROWS = 10

        def __init__(self) -> None:
            super().__init__(id="completion")
            self.owner = None
            self.values: list[str] = []

        def on_mount(self) -> None:
            self.can_focus = False
            self.display = False

        def open(self, owner, items: list[tuple[str, str]], back: int = 0) -> None:
            """Show items under owner's cursor; `back` cells left so the list lines up with the word."""
            if not items:
                self.close()
                return
            self.owner, self.values = owner, [v for v, _ in items]
            wide = min(70, max(len(v) for v, _ in items) + max(len(k) for _, k in items) + 6)
            self.clear_options()
            self.add_options([Option(Text.assemble(f" {v:<{wide - len(k) - 4}}", (k, "dim"), " ")) for v, k in items])
            self.highlighted = 0
            rows = min(self.MAX_ROWS, len(items))
            self.styles.width, self.styles.height = wide, rows
            cur, screen = owner.cursor_screen_offset, self.screen.size
            x = max(0, min(cur.x - back - 1, screen.width - wide))
            y = cur.y + 1 if cur.y + 1 + rows <= screen.height else max(0, cur.y - rows)
            self.styles.offset = (x, y)
            self.display = True

        def close(self) -> None:
            self.display = False
            self.owner = None

        def move(self, step: int) -> None:
            if self.highlighted is not None:
                self.highlighted = max(0, min(self.option_count - 1, self.highlighted + step))

        def current(self) -> str | None:
            return self.values[self.highlighted] if self.display and self.highlighted is not None else None

    class Completing:
        """For an Input or TextArea with a Completion box: while it shows, ↑ ↓ pick, tab or enter take
        the pick and esc hides the box; otherwise the keys do what they always do."""

        def popup(self) -> "Completion | None":
            box = next(iter(self.screen.query(Completion)), None)
            return box if box is not None and box.display and box.owner is self else None

        def on_key(self, event) -> None:
            box = self.popup()
            if box is None:
                return
            if event.key in ("up", "down"):
                box.move(-1 if event.key == "up" else 1)
            elif event.key in ("tab", "enter"):
                self.take(box.current())
            elif event.key == "escape":
                box.close()
            else:
                return
            event.prevent_default()
            event.stop()

        def on_blur(self) -> None:
            if (box := self.popup()) is not None:
                box.close()

        def suggest_now(self) -> None:
            pass

        def take(self, value: str | None) -> None:
            pass

    class PathInput(Completing, Input):
        """A path box: typing lists matching folders (and files, if asked) under the cursor."""

        def __init__(self, value: str = "", files: bool = False, **kw) -> None:
            super().__init__(value, select_on_focus=False, **kw)
            self.files = files

        def on_input_changed(self, event: Input.Changed) -> None:
            if self.has_focus:
                self.suggest_now()

        def suggest_now(self) -> None:
            box = self.screen.query_one(Completion)
            typed = self.value
            box.open(self, launch.path_suggestions(typed, files=self.files), back=len(typed.rpartition("/")[2]))

        def take(self, value: str | None) -> None:
            if value is None:
                return
            self.value = value
            self.cursor_position = len(value)
            if not value.endswith("/"):
                self.screen.query_one(Completion).close()

    class PickInput(Completing, Input):
        """A box that searches a fixed list of choices (value, kind) as you type."""

        def __init__(self, value: str, choices, **kw) -> None:
            super().__init__(value, select_on_focus=False, **kw)
            self.choices = choices

        def on_input_changed(self, event: Input.Changed) -> None:
            if self.has_focus:
                self.suggest_now()

        def on_focus(self) -> None:
            self.suggest_now()

        def suggest_now(self) -> None:
            low = self.value.strip().lower()
            hits = [c for c in self.choices() if low in f"{c[0]} {c[1]}".lower()]
            self.screen.query_one(Completion).open(self, hits, back=self.cursor_position)

        def take(self, value: str | None) -> None:
            if value is None:
                return
            self.value = value
            self.cursor_position = len(value)
            self.screen.query_one(Completion).close()

    class PromptArea(Completing, TextArea):
        """The first prompt: a word starting with / lists matching skills under the cursor."""

        def word(self) -> tuple[str, int, int, int] | None:
            row, col = self.cursor_location
            before = self.document.get_line(row)[:col]
            word = before.rsplit(None, 1)[-1] if before.strip() and not before[-1:].isspace() else ""
            return (word, row, col - len(word), col) if word.startswith("/") else None

        def on_text_area_changed(self, event: TextArea.Changed) -> None:
            if self.has_focus:
                self.suggest_now()

        def suggest_now(self) -> None:
            box = self.screen.query_one(Completion)
            word = self.word()
            if word:
                box.open(self, launch.skill_suggestions(word[0]), back=len(word[0]))
            else:
                box.close()

        def take(self, value: str | None) -> None:
            word = self.word()
            if value and word:
                self.replace(value + " ", (word[1], word[2]), (word[1], word[3]))
            self.screen.query_one(Completion).close()

    class NewSession(ModalScreen["dict | None"]):
        """Start a fresh session for a job: the agent, what to hand over (each section previews what it
        holds, and list sections let you pick entries), a first prompt (/ for skills) and the folder."""

        BINDINGS = [
            Binding("escape", "cancel", "Cancel"),
            Binding("ctrl+enter,ctrl+j,ctrl+s", "start", "Start", priority=True),
            Binding("right", "into_peek", show=False),
            Binding("left", "out_of_peek", show=False),
        ]

        def __init__(self, db: dict, job: dict, agent: str) -> None:
            super().__init__()
            self.db, self.job, self.agent = db, job, agent
            self.have = launch.available(db, job)
            self.lists = {k: launch.entries(db, job, k) for k in launch.LISTS}
            self.picked = {k: {i for i, _ in v} for k, v in self.lists.items()}
            self.peeking: str | None = None  # the section the preview box shows
            self.cwd_edited = False

        def compose(self) -> ComposeResult:
            with Vertical(classes="frame"), VerticalScroll(classes="dialog wide"):
                yield Label(f"[b]New session[/] [dim]for {escape(job_label(self.job))} {escape(self.job['name'])}[/]")
                with Vertical(classes="section"):
                    yield Label("Agent", classes="section-label")
                    yield Select([(a, a) for a in AGENTS], value=self.agent, allow_blank=False, id="agent")
                with Vertical(classes="section"):
                    yield Label(
                        "Hand over  [dim]space ticks · → picks entries[/]"
                        + ("" if self.have else "  [dim](nothing recorded for this job yet)[/]"),
                        classes="section-label",
                    )
                    yield SelectionList(
                        *[(self.ctx_label(k, label), k, k in self.have) for k, label in launch.CONTEXT], id="ctx"
                    )
                with Vertical(classes="section"):
                    yield Label(
                        "Prompt  [dim]/ for skills · empty: it sums up the job and waits[/]", classes="section-label"
                    )
                    yield PromptArea("", id="prompt")
                with Vertical(classes="section"):
                    yield Label("Start session from", classes="section-label")
                    yield PathInput(launch.home(self.default_folder()), id="cwd")
                yield Label("[dim]ctrl+enter starts the session · esc cancels[/]", classes="field")
            yield Static(id="peek-text", classes="peek")
            yield SelectionList(id="peek-list", classes="peek")
            yield Completion()

        def ctx_label(self, key: str, label: str) -> str:
            n = len(self.lists.get(key, []))
            return f"{label} ({n})" if key in launch.LISTS else label

        def on_mount(self) -> None:
            for peek in self.query(".peek"):
                peek.display = False
                peek.can_focus = False
            self.query_one("#prompt", PromptArea).focus()

        def default_folder(self) -> str:
            include = list(self.query_one("#ctx", SelectionList).selected) if self.is_mounted else self.have
            return launch.default_folder(self.db, self.job, include) or os.getcwd()

        # -- the preview box beside "Hand over"
        def on_selection_list_selection_highlighted(self, event) -> None:
            if event.selection_list.id == "ctx":
                self.peek(event.selection.value)

        def on_descendant_focus(self, event) -> None:
            focused = getattr(event, "widget", None) or self.focused
            if getattr(focused, "id", None) == "ctx":
                ctx = self.query_one("#ctx", SelectionList)
                if ctx.highlighted is not None:
                    self.peek(ctx.get_option_at_index(ctx.highlighted).value)
            elif getattr(focused, "id", None) != "peek-list":
                self.hide_peek()
            if getattr(focused, "id", None) != "peek-list":
                self.query_one("#peek-list").can_focus = False  # only → enters it; Tab passes it by

        def hide_peek(self) -> None:
            self.peeking = None
            for peek in self.query(".peek"):
                peek.display = False

        def peek(self, key: str) -> None:
            self.peeking = key
            ctx = self.query_one("#ctx", SelectionList)
            text, box = self.query_one("#peek-text", Static), self.query_one("#peek-list", SelectionList)
            x = ctx.region.x + 26
            width = max(30, min(70, self.size.width - x - 2))
            y = ctx.region.y + (ctx.highlighted or 0)
            if key in launch.LISTS:
                text.display = False
                box.clear_options()
                rows = self.lists[key]
                if not rows:
                    box.display = False
                    text.update(Text("nothing yet", style="dim"))
                    text.display = True
                    text.styles.offset, text.styles.width = (x, y), width
                    return
                box.add_options(
                    [(Text(clip(line, width - 8)), ident, ident in self.picked[key]) for ident, line in rows]
                )
                box.styles.offset, box.styles.width = (x, y), width
                box.styles.height = min(10, len(rows)) + 2
                box.border_title = (
                    "what each did; its transcript is read only if needed" if key == "sessions" else "→ to pick"
                )
                box.display = True
            else:
                box.display = False
                text.update(Text(launch.preview(self.db, self.job, key)))
                text.styles.offset, text.styles.width = (x, y), width
                text.display = True

        def action_into_peek(self) -> None:
            box = self.query_one("#peek-list", SelectionList)
            if getattr(self.focused, "id", None) == "ctx" and box.display:
                box.can_focus = True
                box.focus()
                box.highlighted = 0

        def action_out_of_peek(self) -> None:
            if getattr(self.focused, "id", None) == "peek-list":
                self.query_one("#ctx", SelectionList).focus()

        def check_action(self, action: str, parameters: tuple) -> bool | None:
            if action == "into_peek":
                return getattr(self.focused, "id", None) == "ctx"
            if action == "out_of_peek":
                return getattr(self.focused, "id", None) == "peek-list"
            return True

        def on_selection_list_selected_changed(self, event) -> None:
            if event.selection_list.id == "peek-list" and self.peeking in launch.LISTS:
                chosen = set(event.selection_list.selected)
                self.picked[self.peeking] = chosen
                ctx = self.query_one("#ctx", SelectionList)
                if chosen:
                    ctx.select(self.peeking)  # picking an entry hands the section over
                else:
                    ctx.deselect(self.peeking)
            elif event.selection_list.id == "ctx" and not self.cwd_edited:
                self.query_one("#cwd", PathInput).value = launch.home(self.default_folder())

        def on_input_changed(self, event: Input.Changed) -> None:
            if event.input.id == "cwd" and event.input.has_focus:
                self.cwd_edited = True

        # -- finish
        def action_start(self) -> None:
            cwd = Path(self.query_one("#cwd", Input).value.strip() or ".").expanduser()
            if not cwd.is_dir():
                self.notify(f"{cwd} is not a folder", severity="error")
                return
            self.dismiss(
                {
                    "agent": self.query_one("#agent", Select).value,
                    "cwd": str(cwd),
                    "include": list(self.query_one("#ctx", SelectionList).selected),
                    "picked": {k: sorted(v) for k, v in self.picked.items()},
                    "prompt": self.query_one("#prompt", TextArea).text,
                }
            )

        def action_cancel(self) -> None:
            if getattr(self.focused, "id", None) == "peek-list":
                self.query_one("#ctx", SelectionList).focus()
            else:
                self.dismiss(None)

    class ArtifactList(ModalScreen[None]):
        """What a job's sessions left behind. Enter opens one; x hides a wrong guess (it moves to Hidden,
        where x brings it back); ctrl+z undoes the last change; a adds a file or folder by hand."""

        BINDINGS = [
            Binding("escape", "close", "Close"),
            Binding("x", "toggle_hidden", "Hide / bring back"),
            Binding("a", "add", "Add"),
            Binding("ctrl+z", "undo", "Undo"),
        ]

        def __init__(self, ops: dict) -> None:
            super().__init__()
            self.ops = ops  # list() -> (artifacts, hidden paths); hide, restore, add, remove (path)
            self.rows: list[tuple[str, str]] = []  # (state, path) behind each line; state: live | hidden
            self.undo: list[tuple[str, str]] = []  # (op that reverses it, path)

        def compose(self) -> ComposeResult:
            with Vertical(classes="frame"), Vertical(classes="dialog wide"):
                yield Label("[b]Artifacts[/] [dim]enter opens · x hides or brings back · a adds · ctrl+z undo[/]")
                yield OptionList(id="arts")
                yield Label("Add a file or folder", id="add-label", classes="field")
                yield PathInput("", files=True, id="add-path")
            yield Completion()

        def on_mount(self) -> None:
            self.query_one("#add-label").display = False
            self.query_one("#add-path").display = False
            self.fill()
            self.query_one(OptionList).focus()

        def fill(self, at: int | None = None) -> None:
            opts = self.query_one("#arts", OptionList)
            opts.clear_options()
            live, hidden = self.ops["list"]()
            home = str(Path.home())
            self.rows = []
            options = []
            for a in live:
                self.rows.append(("live", a["path"]))
                options.append(
                    Option(
                        Text.from_markup(
                            f"{a['kind']:<6} [b]{escape(a['label'])}[/]  [dim]{escape(a['path'].replace(home, '~'))}[/]"
                        )
                    )
                )
            if not live:
                self.rows.append(("none", ""))
                options.append(Option(Text("No artifacts yet. a adds one.", style="dim"), disabled=True))
            if hidden:
                self.rows.append(("none", ""))
                options.append(
                    Option(Text(f"\nHidden ({len(hidden)})  x brings one back", style="dim bold"), disabled=True)
                )
                for path in hidden:
                    self.rows.append(("hidden", path))
                    options.append(Option(Text(f"       {path.replace(home, '~')}", style="dim")))
            opts.add_options(options)
            pickable = [n for n, (state, _) in enumerate(self.rows) if state != "none"]
            opts.highlighted = (
                (min(pickable, key=lambda n: abs(n - at)) if at is not None else pickable[0]) if pickable else None
            )

        def current(self) -> tuple[str, str] | None:
            opts = self.query_one("#arts", OptionList)
            if opts.highlighted is None or self.rows[opts.highlighted][0] == "none":
                return None
            return self.rows[opts.highlighted]

        def on_option_list_option_selected(self, event) -> None:
            event.stop()
            row = self.current()
            if row and not artifacts.open_path(row[1]):
                self.notify(f"Could not open {row[1]}", severity="error")

        def action_toggle_hidden(self) -> None:
            row = self.current()
            if not row:
                return
            state, path = row
            if state == "live":
                self.ops["hide"](path)
                self.undo.append(("restore", path))
            else:
                self.ops["restore"](path)
                self.undo.append(("hide", path))
            self.fill(self.query_one("#arts", OptionList).highlighted)

        def action_undo(self) -> None:
            if not self.undo:
                self.notify("Nothing to undo")
                return
            op, path = self.undo.pop()
            self.ops[op](path)
            self.fill(self.query_one("#arts", OptionList).highlighted)

        def action_add(self) -> None:
            self.query_one("#add-label").display = True
            box = self.query_one("#add-path", PathInput)
            box.display = True
            box.value = "~/"
            box.focus()
            box.cursor_position = 2

        def on_input_submitted(self, event: Input.Submitted) -> None:
            event.stop()
            path = Path(event.value.strip()).expanduser()
            if not event.value.strip() or not path.exists():
                self.notify(f"{event.value.strip() or 'That'} does not exist", severity="error")
                return
            self.ops["add"](str(path))
            self.undo.append(("remove", str(path)))
            self.close_add()
            self.fill()

        def close_add(self) -> None:
            self.query_one("#add-label").display = False
            self.query_one("#add-path").display = False
            self.query_one("#arts", OptionList).focus()

        def check_action(self, action: str, parameters: tuple) -> bool | None:
            adding = self.query_one("#add-path").display
            return not (adding and action in ("toggle_hidden", "add"))  # letters belong to the path box

        def action_close(self) -> None:
            if self.query_one("#add-path").display:
                self.close_add()
            else:
                self.dismiss(None)

    class HeaderTable(DataTable):
        """Up from the first row steps onto the column headers; there the arrows pick a header, Enter
        sorts by it, typing searches it, and Down returns to the rows. Enter on a row starts column mode."""

        def action_cursor_up(self) -> None:
            h = self.app.header
            if h is None:
                if self.cursor_row == 0 or not self.row_count:
                    self.app.enter_header()
                else:
                    super().action_cursor_up()
            elif h >= 0:
                self.app.enter_tabs()  # one more Up reaches the Jobs / Board tabs

        def action_cursor_down(self) -> None:
            h = self.app.header
            if h is None:
                super().action_cursor_down()
            elif h < 0:
                self.app.enter_header()
            else:
                self.app.leave_header()

        def action_cursor_left(self) -> None:
            h = self.app.header
            if self.app.col is not None:
                self.app.column_move(-1)
            elif h is not None and h < 0:
                self.app.tab_move(-1)
            elif h is not None:
                self.app.header_move(-1)

        def action_cursor_right(self) -> None:
            h = self.app.header
            if self.app.col is not None:
                self.app.column_move(1)
            elif h is not None and h < 0:
                self.app.tab_move(1)
            elif h is not None:
                self.app.header_move(1)
            else:
                self.app.focus_panel()

        def on_key(self, event) -> None:
            """Typing in column mode, or on a header, starts that column's search right away."""
            app = self.app
            if ("+" in event.key and event.key != "plus") or event.key in ("R", "greater_than_sign"):
                return  # a chord (Ctrl+E) or Shift+R / Shift+. is a shortcut, never text for the search
            if app.col is not None and event.is_printable:
                if event.character and event.character != " ":
                    event.stop()
                    event.prevent_default()
                    app.column_search(event.character)
                return
            if app.header is not None and app.header >= 0 and event.is_printable:
                col = app.cols()[app.header][0]
                if col not in DATE_COLUMNS and event.character and event.character != " ":
                    event.stop()
                    event.prevent_default()
                    app.filter_by_header(event.character)

        def action_select_cursor(self) -> None:
            if self.app.col is not None:
                self.app.column_search()
            elif self.app.header is not None and self.app.header >= 0:
                self.app.header_enter()
            else:
                self.app.enter_column()  # at once, not via RowSelected, so a quick → after it moves the column

    class Board(App):
        TITLE = "follow-ups"
        BINDINGS = [
            Binding("1", "view('jobs')", "Jobs"),
            Binding("2", "view('board')", "Board"),
            Binding("a", "add", "Add"),
            Binding("R", "start_session", "Session"),
            Binding("e", "edit", "Edit"),
            Binding("s", "advance", "Status"),
            Binding("d", "done", "Done"),
            Binding("t", "touch", "Worked today"),
            Binding("y", "copy", "Copy restart"),
            Binding("x", "delete", "Delete"),
            Binding("f", "filter", "Filter"),
            Binding("slash", "filter", "Filter", show=False),
            Binding("c", "clear_filters", "Clear", show=False),
            Binding("escape", "clear_filters", "Clear", show=False),
            Binding("full_stop", "toggle_done", "Show done"),
            Binding("greater_than_sign", "toggle_panel", "Panel"),
            Binding("h", "help", "Help"),
            Binding("f1", "help", "Help", show=False),
            Binding("question_mark", "help", "Help", show=False),
            Binding("q", "quit", "Quit"),
        ]
        CSS = """
        Screen { background: $background; }
        #tabs { height: 1; padding: 0 2; }
        #bar { height: 1; padding: 0 2; color: $text-muted; }
        #views { height: 1fr; }
        #board, #jobs { height: 1fr; padding: 1 2; }
        #table, #jobs-table { width: 5fr; height: 1fr; background: $background; }
        #jobs-table { width: 7fr; }
        .detail { width: 3fr; height: 1fr; margin-left: 2; padding: 1 2; border-left: solid $primary 40%; }
        ModalScreen { align: center middle; background: $background 40%; }
        Suggest { background: transparent; }  /* a search keeps the board in view; only dialogs dim it */
        .dialog { width: 76; height: auto; max-height: 90%; padding: 1 2; background: $surface;
                  border: round $primary; }
        .dialog.wide { width: 100; }
        .field { margin-top: 1; color: $text-muted; }
        .dialog Input { height: 1; border: none; padding: 0 1; background: $boost; }
        .dialog Select { height: 1; }
        .dialog Select > SelectCurrent { border: none; height: 1; padding: 0 1; background: $boost; }
        .popup { width: 60; height: auto; max-height: 22; padding: 0 1; background: $surface; border: round $primary; }
        .popup Input { height: 1; border: none; padding: 0 1; background: $boost; }
        .popup OptionList { height: auto; border: none; padding: 0; background: $surface; }
        #notes-text { height: 10; }
        #prompt { height: 6; }
        #ctx { height: 9; }
        .section { height: auto; margin-top: 1; padding-left: 1; border-left: blank; }
        .section:focus-within { border-left: outer $accent; }
        .section-label { color: $text-muted; }
        .section:focus-within > .section-label { color: $accent; text-style: bold; }
        .frame { width: 100%; height: 100%; align: center middle; }  /* floating boxes never move the dialog */
        #completion { overlay: screen; position: absolute; background: $panel; border: none; padding: 0;
                      scrollbar-size-vertical: 1; }
        .peek { overlay: screen; position: absolute; height: auto; max-height: 14; padding: 0 1;
                background: $panel; border: round $accent; }
        #jobs-detail, #board-detail { background: $background; border: none; border-left: solid $primary 40%;
                                      padding: 1 1; }
        #jobs-detail > .option-list--option-disabled, #board-detail > .option-list--option-disabled { color: $text; }
        HeaderTable > .datatable--cursor { background: #ffa62b 30%; color: $text; text-style: bold; }
        HeaderTable:focus > .datatable--cursor { background: #ffa62b 40%; }
        SummaryList > .option-list--option-highlighted { background: #ffa62b 30%; color: $text; text-style: bold; }
        .row { height: 1; padding: 0 1; background: $boost; }
        .row:focus { background: $primary 35%; text-style: bold; }
        .row.ro { background: transparent; color: $text-disabled; }
        """

        def __init__(self) -> None:
            super().__init__()
            mod = key_modifier()
            for key, action in self.MODIFIED.items():
                self.bind(f"{mod}+{key}", action, show=False)
            self.db: dict = {"items": [], "jobs": []}
            self.view = "board"
            self.header: int | None = None  # column header under the cursor, None while on the rows
            self.sort: tuple[str, bool] = ("status", False)  # (column, descending)
            self.show_done = False
            self.filters: dict = {}
            self.jfilters: dict = {}  # Jobs board: column -> filter
            self.in_panel = False  # the Jobs summary panel has the cursor, not the rows
            self.panel_shown = True  # the detail / summary panel beside the table (shift+. toggles it)
            self.col: int | None = None  # Jobs column under column mode (Enter on a row), None outside it
            self.shown_job: int | None = None  # whose summary the Jobs panel currently shows
            self.shown_item: int | None = None  # whose details the Board panel currently shows
            self.jsort: tuple[str, bool] = ("last_worked", True)  # Jobs: (column, descending)
            self.bfilters: dict = {}  # Board column mode: column -> filter
            self.runner = self.run_suspended  # tests swap this for a recorder

        # ---- layout
        def compose(self) -> ComposeResult:
            yield Header()
            yield Static(id="tabs")
            yield Static(id="bar")
            with ContentSwitcher(initial="board", id="views"):
                with Horizontal(id="board"):
                    yield HeaderTable(id="table", cursor_type="row", zebra_stripes=False)
                    yield SummaryList(id="board-detail", classes="detail")
                with Horizontal(id="jobs"):
                    yield HeaderTable(id="jobs-table", cursor_type="row", zebra_stripes=False)
                    yield SummaryList(id="jobs-detail", classes="detail")
            yield Footer()

        def on_mount(self) -> None:
            self.reload()
            self.query_one("#table", DataTable).focus()

        # Shortcuts that also answer to modifier+key (Ctrl by default), the way to reach them while
        # a column search is typing and plain letters belong to the search box. Digits, c and h are
        # left out: terminals send no Ctrl+digit, and Ctrl+c / Ctrl+h are control codes (use esc and F1).
        MODIFIED = {
            "a": "add",
            "e": "edit",
            "s": "advance",
            "d": "done",
            "t": "touch",
            "y": "copy",
            "x": "delete",
            "f": "filter",
            "q": "quit",
        }

        OWN_ACTIONS = {
            "view",
            "add",
            "edit",
            "advance",
            "done",
            "touch",
            "copy",
            "start_session",
            "delete",
            "filter",
            "clear_filters",
            "toggle_done",
            "toggle_panel",
            "help",
            "quit",
        }

        def check_action(self, action: str, parameters: tuple) -> bool | None:
            if action not in self.OWN_ACTIONS:
                return True  # Textual's own actions (Tab focus, quit, palette) must keep working in dialogs
            if isinstance(self.screen, ModalScreen):
                return False  # our keys belong to the dialog
            if action == "filter" and self.view != "board":
                return False  # the Jobs board filters through its column headers
            return not (action in ("advance", "done", "touch") and self.view != "board")

        # ---- state
        def reload(self, keep=None) -> None:
            self.db = load_db()
            self.refresh_table(keep if isinstance(keep, str) else None)
            self.refresh_jobs()
            self.update_chrome()

        def effective_filters(self) -> dict:
            return {**self.filters, "all": self.show_done}

        def visible_items(self) -> list[dict]:
            items = sort_board(
                self.db, [i for i in self.db["items"] if matches(i, self.effective_filters())], *self.sort
            )
            keep = {r["item"]["id"] for r in filter_jobs(self.board_rows(items), self.bfilters)}
            return [i for i in items if i["id"] in keep]

        def board_rows(self, items: list[dict] | None = None) -> list[dict]:
            """The Board's rows as column -> text, what column mode searches."""
            items = (
                items if items is not None else [i for i in self.db["items"] if matches(i, self.effective_filters())]
            )
            return [
                {
                    "item": i,
                    "id": str(i["id"]),
                    "status": i["status"],
                    "job": job_name(self.db, i),
                    "summary": i["summary"],
                    "added": i["added"],
                    "last_worked": i["last_worked"],
                }
                for i in items
            ]

        def jobs_visible(self) -> list[dict]:
            return sort_jobs(filter_jobs(job_rows(self.db), self.jfilters), *self.jsort)

        # what differs between the two screens, so headers, column mode and the panel serve both
        def cols(self) -> list[tuple[str, str]]:
            return COLUMNS if self.view == "board" else JOB_COLUMNS_UI

        def vfilters(self) -> dict:
            return self.bfilters if self.view == "board" else self.jfilters

        def all_rows(self) -> list[dict]:
            return self.board_rows() if self.view == "board" else job_rows(self.db)

        def table_id(self) -> str:
            return "#table" if self.view == "board" else "#jobs-table"

        def panel_id(self) -> str:
            return "#board-detail" if self.view == "board" else "#jobs-detail"

        def cursor_row(self) -> dict | None:
            """The highlighted row as column -> text."""
            if self.view == "board":
                item = self.table_item()
                return next((r for r in self.board_rows([item])), None) if item else None
            job = self.current_job()
            return next((r for r in job_rows(self.db) if r["job"]["id"] == job["id"]), None) if job else None

        def table_item(self) -> dict | None:
            key = self.cursor_key("#table")
            return next((i for i in self.db["items"] if str(i["id"]) == key), None)

        def cursor_key(self, selector: str) -> str | None:
            table = self.query_one(selector, DataTable)
            if not table.row_count:
                return None
            return table.coordinate_to_cell_key(table.cursor_coordinate).row_key.value

        def current_item(self) -> dict | None:
            return self.table_item() if self.view == "board" else None

        def current_job(self) -> dict | None:
            key = self.cursor_key("#jobs-table") if self.view == "jobs" else None
            return next((j for j in self.db["jobs"] if str(j["id"]) == key), None)

        def update_chrome(self) -> None:
            tabs = [("jobs", "1 Jobs"), ("board", "2 Board")]
            on_tabs = self.header == -1
            self.query_one("#tabs", Static).update(
                "   ".join(
                    (f"[reverse b u] {t} [/]" if on_tabs else f"[reverse b] {t} [/]")
                    if v == self.view
                    else f"[dim] {t} [/]"
                    for v, t in tabs
                )
            )
            items = self.db["items"]
            n = {s: sum(i["status"] == s for i in items) for s in STATUSES}
            chips = " · ".join(c for c in (self.filter_chips(), self.column_chips()) if c)
            self.query_one("#bar", Static).update(
                f"{n['doing']} doing · {n['todo']} todo · {n['done']} done"
                + ("" if self.show_done or not n["done"] else "  [dim](done hidden: . to show)[/]")
                + (f"   [b]filter:[/] {chips}  [dim](c clears)[/]" if chips else "")
                + ("   [b]panel:[/] [dim]↑ ↓ move · enter opens · ← back to the rows[/]" if self.in_panel else "")
                + (
                    "   [b]column:[/] [dim]← → pick · ↑ ↓ row · type or enter searches · esc all/leave[/]"
                    if self.col is not None
                    else ""
                )
                + (
                    "   [b]screens:[/] [dim]← → switch between Jobs and Board · ↓ to the headers[/]"
                    if self.header == -1
                    else "   [b]headers:[/] [dim]← → move · enter sorts · type searches · ↑ screens · ↓ rows[/]"
                    if self.header is not None
                    else ""
                )
            )
            self.refresh_bindings()

        def filter_chips(self) -> str:
            if self.view != "board":
                return ""
            f, parts = self.filters, []
            if f.get("text"):
                parts.append(f"“{escape(f['text'])}”")
            if f.get("job") is not None:
                job = next((j for j in self.db["jobs"] if j["id"] == f["job"]), None)
                parts.append("job: " + ("none" if f["job"] == "none" else escape(job["name"]) if job else "?"))
            if f.get("session"):
                parts.append(f"session: {f['session'][:14]}")
            for k, label in (("status", "status"), ("agent", "agent")):
                if f.get(k):
                    parts.append(f"{label}: {f[k]}")
            if f.get("idle") is not None:
                parts.append(f"idle ≥ {f['idle']}d")
            if f.get("recent") is not None:
                parts.append(f"worked ≤ {f['recent']}d ago")
            return " · ".join(parts)

        def column_chips(self) -> str:
            labels = dict(self.cols())
            return " · ".join(
                f"{labels[c]}: " + (f"“{escape(f['text'])}”" if "text" in f else escape(f["label"]))
                for c, f in self.vfilters().items()
            )

        def header_text(self, view: str, n: int, col: str, label: str) -> Text:
            """A column header: the sort arrow, a dot when filtered, orange while picked."""
            key, desc = self.sort if view == "board" else self.jsort
            filtered = col in (self.bfilters if view == "board" else self.jfilters)
            mark = ((" ▼" if desc else " ▲") if key == col else "") + (" ●" if filtered else "")
            picked = self.view == view and (self.header == n or self.col == n)
            return Text(label + mark, style=HEADER_PICKED if picked else ("bold" if key == col or filtered else ""))

        # ---- board view
        def refresh_table(self, keep: str | None) -> None:
            keep = keep or (str(self.table_item()["id"]) if self.table_item() else None)
            visible = self.visible_items()
            table = self.query_one("#table", DataTable)
            table.clear(columns=True)
            for n, (col, label) in enumerate(COLUMNS):
                table.add_column(self.header_text("board", n, col, label), key=col)
            table.show_cursor = not (self.header is not None and self.view == "board")
            tint = self.col if self.view == "board" else None
            for i in visible:
                label, colour = BADGE[i["status"]]
                job = next((j for j in self.db["jobs"] if j["id"] == i.get("job_id")), None)
                cells = [
                    Text(str(i["id"]), style="dim"),
                    Text(label, style=colour),
                    Text(
                        f"{KIND_GLYPH[job['kind']]} {clip(job['name'], 16)}" if job else "-", style="" if job else "dim"
                    ),
                    Text(i["summary"], style="dim" if i["status"] == "done" else "bold"),
                    Text(i["added"], style="dim"),
                    Text(f"{i['last_worked']}  {age(i['last_worked'])}", style=heat(idle_days(i))),
                ]
                if tint is not None:
                    cells[tint].stylize(COLUMN_TINT)  # column mode: the whole column stands out
                table.add_row(*cells, key=str(i["id"]))
            ids = [str(i["id"]) for i in visible]
            if keep in ids:
                table.move_cursor(row=ids.index(keep))
            self.show_board_detail()

        STYLES = {"title": "bold", "meta": "dim", "head": "dim bold", "text": "", "action": ""}

        def fill_panel(self, panel: "SummaryList", entries: list[dict]) -> None:
            options, panel.full, panel.revealed = [], {}, None
            for e in entries:
                text = Text(("\n" if e["style"] == "head" else "") + e["text"], style=self.STYLES[e["style"]])
                if e["key"] and e["key"] not in ("notes",) and e["style"] == "action":
                    text.stylize("not dim")
                if e["style"] == "action" and e["key"]:
                    panel.full[e["key"]] = text
                    text = panel.clip(text)
                options.append(Option(text, id=e["key"], disabled=not e["enabled"]))
            panel.add_options(options)

        def show_board_detail(self, force: bool = True) -> None:
            panel = self.query_one("#board-detail", SummaryList)
            item = self.table_item()
            shown = item["id"] if item else None
            if not force and shown == self.shown_item and panel.option_count:
                return
            self.shown_item = shown
            panel.clear_options()
            if not item:
                msg = "Nothing here. Press a to add a follow-up, or c to clear filters."
                panel.add_options([Option(Text(msg, style="dim"), disabled=True)])
                return
            self.fill_panel(panel, summary.build_item(self.db, item))

        # ---- jobs view
        def refresh_jobs(self) -> None:
            keep = self.cursor_key("#jobs-table")
            rows = self.jobs_visible()
            table = self.query_one("#jobs-table", DataTable)
            table.clear(columns=True)
            for n, (col, label) in enumerate(JOB_COLUMNS_UI):
                table.add_column(self.header_text("jobs", n, col, label), key=col)
            table.show_cursor = not (self.header is not None and self.view == "jobs")
            tint = self.col if self.view == "jobs" else None
            for r in rows:
                job = r["job"]
                cells = [
                    Text(r["id"], style="dim"),
                    Text(f"{KIND_GLYPH[r['kind']]} {r['kind']}"),
                    Text(clip(r["parent"], 14) or "-", style="" if r["parent"] else "dim"),
                    Text(job["name"], style="bold"),
                    Text(r["added"], style="dim"),
                    Text(
                        f"{r['last_worked']}  {age(r['last_worked'])}",
                        style=heat(idle_days(r)),
                    ),
                ]
                if tint is not None:
                    cells[tint].stylize(COLUMN_TINT)  # column mode: the whole column stands out
                table.add_row(*cells, key=str(job["id"]))
            ids = [str(r["job"]["id"]) for r in rows]
            if keep in ids:
                table.move_cursor(row=ids.index(keep))
            self.show_jobs_detail()

        def show_jobs_detail(self, force: bool = True) -> None:
            """Rebuild the panel for the job under the cursor. A row-highlight event passes force=False so
            it does not wipe the panel's own cursor when the job has not changed."""
            panel = self.query_one("#jobs-detail", SummaryList)
            job = self.current_job()
            shown = job["id"] if job else None
            if not force and shown == self.shown_job and panel.option_count:
                return
            self.shown_job = shown
            panel.clear_options()
            if not job:
                msg = (
                    "No jobs yet. Press a to add one."
                    if not self.db["jobs"]
                    else "No job matches the filters. c clears them."
                )
                panel.add_options([Option(Text(msg, style="dim"), disabled=True)])
                return
            self.fill_panel(panel, summary.build(self.db, job))

        def show_detail(self) -> None:
            self.show_board_detail() if self.view == "board" else self.show_jobs_detail()

        def first_enabled(self) -> int | None:
            panel = self.query_one(self.panel_id(), SummaryList)
            return next((n for n in range(panel.option_count) if not panel.get_option_at_index(n).disabled), None)

        def focus_panel(self, key: str | None = None) -> None:
            """Put the cursor in the panel, on the entry with this key (else the first actionable one)."""
            panel = self.query_one(self.panel_id(), SummaryList)
            if (self.current_job() if self.view == "jobs" else self.table_item()) is None:
                return
            if not self.panel_shown:
                self.set_panel(True)
            at = next((n for n in range(panel.option_count) if key and panel.get_option_at_index(n).id == key), None)
            panel.highlighted = at if at is not None else self.first_enabled()
            panel.focus()
            self.in_panel = True
            self.update_chrome()

        def focus_rows(self) -> None:
            self.query_one(self.table_id(), DataTable).focus()
            self.in_panel = False
            self.update_chrome()

        def select_job(self, job_id: int) -> None:
            """Jump to a job's row on the Jobs screen (clearing filters that hide it) and stay in the panel."""
            if self.view != "jobs":
                self.action_view("jobs")
            if not any(r["job"]["id"] == job_id for r in self.jobs_visible()):
                self.jfilters = {}
                self.refresh_jobs()
            rows = self.jobs_visible()
            self.query_one("#jobs-table", DataTable).move_cursor(row=[r["job"]["id"] for r in rows].index(job_id))
            self.show_jobs_detail()
            self.update_chrome()
            self.call_after_refresh(self.focus_panel)

        # ---- the panels' entries
        def on_option_list_option_selected(self, event) -> None:
            key = event.option.id or ""
            if event.option_list.id == "jobs-detail" and (job := self.current_job()):
                if key == "notes":
                    self.edit_notes(job)
                elif key == "artifacts":
                    self.open_artifacts(job=job)
                elif key.startswith("job:"):
                    self.select_job(int(key.split(":", 1)[1]))
                elif key.startswith("session:"):
                    self.session_actions(summary.session_target(self.db, job, key.split(":", 1)[1]))
            elif event.option_list.id == "board-detail" and (item := self.table_item()):
                if key == "notes":
                    self.edit_notes(item=item)
                elif key == "artifacts":
                    self.open_artifacts(item=item)
                elif key.startswith("job:"):
                    self.select_job(int(key.split(":", 1)[1]))
                elif key.startswith("session:"):
                    self.session_actions(item)

        def edit_notes(self, job: dict | None = None, item: dict | None = None) -> None:
            def done(text: str | None) -> None:
                if text is None:
                    return
                db = load_db()
                if job:
                    next(j for j in db["jobs"] if j["id"] == job["id"])["notes"] = text
                else:
                    next(i for i in db["items"] if i["id"] == item["id"])["notes"] = text
                save_db(db)
                self.db = db
                self.show_detail()
                self.call_after_refresh(self.focus_panel, "notes")

            self.push_screen(NotesForm((job or item).get("notes", "")), done)

        def open_artifacts(self, job: dict | None = None, item: dict | None = None) -> None:
            def change(fn) -> None:
                """Apply fn(db, owner) to the job or task as saved, then refresh the panel."""
                db = load_db()
                owner = (
                    next(j for j in db["jobs"] if j["id"] == job["id"])
                    if job
                    else next(i for i in db["items"] if i["id"] == item["id"])
                )
                fn(db, owner)
                save_db(db)
                self.db = db
                self.show_detail()

            def listing() -> tuple[list[dict], list[str]]:
                if job:
                    fresh = next(j for j in self.db["jobs"] if j["id"] == job["id"])
                    return summary.job_artifacts(self.db, fresh), summary.hidden_artifacts(self.db, fresh)
                fresh = next(i for i in self.db["items"] if i["id"] == item["id"])
                return artifacts.item_artifacts(fresh), list(fresh.get("artifacts_dismissed", []))

            ops = {
                "list": listing,
                "hide": lambda path: change(
                    lambda db, o: summary.dismiss_job_artifact(db, o, path) if job else artifacts.dismiss(o, path)
                ),
                "restore": lambda path: change(
                    lambda db, o: summary.restore_job_artifact(db, o, path) if job else artifacts.restore(o, path)
                ),
                "add": lambda path: change(lambda db, o: artifacts.add_manual(o, path)),
                "remove": lambda path: change(lambda db, o: artifacts.remove_manual(o, path)),
            }
            self.push_screen(ArtifactList(ops))

        # ---- running sessions: the board steps aside while the agent runs, then comes back
        def run_suspended(self, cmd: str) -> None:
            import subprocess

            with self.suspend():
                subprocess.run(["/bin/sh", "-c", cmd], check=False)  # noqa: S603 - our own command, built with shlex

        def run_session(self, cmd: str | None) -> None:
            if not cmd:
                self.notify("No session id stored for this item", severity="warning")
                return
            self.runner(cmd)
            self.reload()

        def resume(self, item_id: str) -> None:
            self.run_session(launch.prepare_resume(item_id))

        def session_actions(self, item: dict | None) -> None:
            """Resume the session this task came from, or open its folder."""
            if not item or not item.get("session_id"):
                self.notify("No session recorded for this task", severity="warning")
                return

            def done(choice: str | None) -> None:
                if choice == "resume":
                    self.resume(str(item["id"]))
                elif choice == "folder":
                    cwd = item.get("cwd")
                    if not cwd or not Path(cwd).is_dir():
                        self.notify("This session's folder no longer exists", severity="warning")
                    else:
                        artifacts.open_path(cwd)

            self.push_screen(
                SessionActions(summary.session_line(item["agent"], item["session_id"], item.get("cwd"))), done
            )

        # ---- events
        def on_data_table_row_highlighted(self, event) -> None:
            if event.data_table.id == "jobs-table":
                self.show_jobs_detail(force=False)
            else:
                self.show_board_detail(force=False)

        def restart_job(self, job: dict | None) -> None:
            item = job_resume_item(self.db, job) if job else None
            if not job:
                return
            if not item:
                self.notify("This job has no session to restart", severity="warning")
                return

            def done(yes: bool | None) -> None:
                if yes:
                    self.resume(str(item["id"]))

            self.push_screen(Confirm(f"Restart session?\n{item['agent']} · {item['summary']}"), done)

        def resume_item(self, item: dict | None) -> None:
            if item and resume_cmd(item):
                self.resume(str(item["id"]))
            elif item:
                self.notify("No session id stored for this item", severity="warning")

        # ---- actions
        def action_view(self, name: str) -> None:
            self.view = name
            self.header = None
            self.col = None
            self.in_panel = False
            self.query_one(ContentSwitcher).current = name
            self.query_one("#table" if name == "board" else "#jobs-table", DataTable).focus()
            self.update_chrome()
            self.refresh_jobs() if name == "jobs" else self.refresh_table(None)

        # ---- column headers
        def refresh_view(self) -> None:
            self.refresh_table(None) if self.view == "board" else self.refresh_jobs()
            self.update_chrome()

        def enter_header(self) -> None:
            """Step onto the headers: the Board on the column it is sorted by, Jobs on the first."""
            self.col = None
            self.header = (
                next((n for n, (c, _) in enumerate(COLUMNS) if c == self.sort[0]), 0) if self.view == "board" else 0
            )
            self.refresh_view()

        def enter_tabs(self) -> None:
            self.header = -1
            self.refresh_view()

        def tab_move(self, step: int) -> None:
            """On the tab row ← → switch screen and stay on the tab row."""
            names = ["jobs", "board"]
            self.action_view(names[max(0, min(1, names.index(self.view) + step))])
            self.header = -1
            self.refresh_view()

        # ---- column mode: Enter on a row picks a whole column to search (it starts on ID)
        def enter_column(self) -> None:
            if self.cursor_row() is None:
                return
            self.col = self.col if self.col is not None else 0
            self.refresh_view()

        def leave_column(self) -> None:
            self.col = None
            self.refresh_view()

        def column_move(self, step: int) -> None:
            self.col = max(0, min(len(self.cols()) - 1, self.col + step))
            self.refresh_view()

        def column_search(self, typed: str = "") -> None:
            """Search the highlighted column. Plain Enter starts from the highlighted row's own value, so
            Enter, Enter shows every row that shares it (every child of a parent, say)."""
            row = self.cursor_row()
            if self.col is None or row is None:
                return
            col = self.cols()[self.col][0]
            if col in DATE_COLUMNS:
                if not typed:
                    self.filter_column(self.col, start=date.fromisoformat(row[col]))
                return
            self.filter_column(self.col, typed or row[col])

        def leave_header(self) -> None:
            self.header = None
            self.refresh_view()

        def header_move(self, step: int) -> None:
            if self.header is None:
                return
            last = len(self.cols()) - 1
            if self.view == "board" and self.header + step < 0:
                self.action_view("jobs")  # swipe left past the first header onto Jobs
            elif self.view == "jobs" and self.header + step > last:
                self.action_view("board")  # swipe right past the last header onto the Board
            else:
                self.header = max(0, min(last, self.header + step))
                self.refresh_view()

        def header_enter(self) -> None:
            """Enter on a header sorts by it; again flips ascending / descending."""
            col = self.cols()[self.header][0]
            if self.view == "board":
                self.sort = (col, not self.sort[1]) if self.sort[0] == col else (col, False)
            else:
                self.jsort = (col, not self.jsort[1]) if self.jsort[0] == col else (col, False)
            self.refresh_view()

        def header_x(self, n: int) -> int:
            """Where header n starts, so a popup can sit under it."""
            table = self.query_one(self.table_id(), DataTable)
            try:
                return 2 + sum(c.get_render_width(table) for c in list(table.columns.values())[:n])
            except Exception:  # noqa: BLE001 - placement is cosmetic; fall back to the left edge
                return 2

        def set_vfilter(self, col: str, value: dict | None) -> None:
            filters = self.vfilters()
            if value:
                filters[col] = value
            else:
                filters.pop(col, None)
            self.refresh_view()

        def filter_by_header(self, typed: str = "") -> None:
            self.filter_column(self.header, typed)

        def filter_column(self, n: int, typed: str = "", start: date | None = None) -> None:
            """Open column n's filter: a search list (text, with `typed` already in the box), the kind
            list, or the date picker."""
            col, label = self.cols()[n]
            saved = self.vfilters().get(col)
            x = self.header_x(n)
            if col in DATE_COLUMNS:
                start = start or (
                    date.fromisoformat(saved["from"]) if saved and saved["from"] == saved["to"] else date.today()
                )

                def picked(v: dict | None) -> None:
                    if v is not None:
                        self.set_vfilter(col, None if v.get("clear") else v)

                self.push_screen(DatePick(label, start, x), picked)
                return
            others = {k: v for k, v in self.vfilters().items() if k != col}
            rows = filter_jobs(self.all_rows(), others)

            def picked_text(v: str | None) -> None:
                self.set_vfilter(col, saved if v is None else ({"text": v} if v else None))

            self.push_screen(
                Suggest(
                    label,
                    lambda q: suggestions(rows, col, q),
                    typed or (saved["text"] if saved and "text" in saved else ""),
                    lambda value: self.set_vfilter(col, {"text": value} if value else None),
                    x,
                ),
                picked_text,
            )

        def action_start_session(self) -> None:
            if self.view != "jobs":
                self.resume_item(self.table_item())
                return
            job = self.current_job()
            if not job:
                return
            sessions = summary.sessions_of(self.db, job)
            if not sessions:
                self.new_session(job)
                return
            choices = [
                (
                    str(summary.session_target(self.db, job, k)["id"]),
                    summary.session_line(g[0]["agent"], g[0]["session_id"], g[0].get("cwd")),
                )
                for k, g in sessions
            ]

            def chosen(v: dict | None) -> None:
                if not v:
                    return
                if v.get("new"):
                    self.new_session(job)
                else:
                    self.resume(v["restart"])

            self.push_screen(SessionChoice(choices), chosen)

        def new_session(self, job: dict) -> None:
            """Ask how to start a session for the job, then run it while the board waits."""
            last = max(
                (i for i in self.db["items"] if i.get("job_id") == job["id"] and i.get("agent")),
                key=lambda i: (i["last_worked"], i["id"]),
                default=None,
            )

            def started(v: dict | None) -> None:
                if v:
                    self.run_session(launch.prepare({**v, "job_id": job["id"]}))

            self.push_screen(NewSession(self.db, job, last["agent"] if last else AGENTS[0]), started)

        def action_help(self) -> None:
            self.push_screen(Help())

        def mutate(self, **changes) -> None:
            item = self.current_item()
            if item:
                update(str(item["id"]), **changes)
                self.reload(str(item["id"]))

        def action_advance(self) -> None:
            item = self.current_item()
            if item:
                self.mutate(status=STATUSES[(STATUSES.index(item["status"]) + 1) % len(STATUSES)])

        def action_done(self) -> None:
            self.mutate(status="done", last_worked=today())

        def action_touch(self) -> None:
            self.mutate(last_worked=today())

        def set_panel(self, shown: bool) -> None:
            self.panel_shown = shown
            for sel in ("#jobs-detail", "#board-detail"):
                self.query_one(sel).display = shown
            if not shown and self.in_panel:
                self.focus_rows()

        def action_toggle_panel(self) -> None:
            self.set_panel(not self.panel_shown)

        def action_toggle_done(self) -> None:
            self.show_done = not self.show_done
            self.reload()

        def action_copy(self) -> None:
            import subprocess

            job = self.current_job()
            item = job_resume_item(self.db, job) if job else self.current_item()
            cmd = resume_cmd(item) if item else None
            if not cmd:
                self.notify("Nothing to copy", severity="warning")
                return
            subprocess.run(["pbcopy"], input=cmd.encode(), check=False)
            self.notify("Restart command copied")

        def action_add(self) -> None:
            if self.view == "jobs":

                def job_done(v: dict | None) -> None:
                    if v:
                        db = load_db()
                        if job_by_ref(db, v["name"], fuzzy=False):
                            self.notify("A job with that name exists", severity="error")
                            return
                        try:
                            create_job(
                                db,
                                v["name"],
                                v["kind"],
                                ext_id=v["ext_id"],
                                parent=v["parent"] or None,
                                desc=v["description"],
                                home=v["home"],
                            )
                        except SystemExit as err:  # core reports bad ids and parents by exiting
                            self.notify(str(err.code), severity="error")
                            return
                        save_db(db)
                        self.reload()

                self.push_screen(JobForm("New job", {"kind": DEFAULT_KIND}, self.parent_choices()), job_done)
                return

            def done(v: dict | None) -> None:
                if v:
                    db = load_db()
                    new = new_item(
                        db,
                        v["summary"],
                        why=v["why"],
                        cwd=os.getcwd(),
                        job=v["job"] or None,
                    )
                    save_db(db)
                    self.reload(str(new["id"]))

            self.push_screen(ItemForm("New follow-up", {"cwd": os.getcwd()}), done)

        def action_edit(self) -> None:
            item, job = self.current_item(), self.current_job()
            if item:

                def done(v: dict | None) -> None:
                    if v:
                        update(str(item["id"]), job=v.pop("job"), **v)
                        self.reload(str(item["id"]))

                self.push_screen(ItemForm(f"Edit #{item['id']}", {**item, "job": job_name(self.db, item)}), done)
            elif job:

                def job_done(v: dict | None) -> None:
                    if v:
                        db = load_db()
                        target = next(j for j in db["jobs"] if j["id"] == job["id"])
                        try:
                            check_ext_id(db, v["ext_id"], target)
                            set_parent(db, target, v["parent"] or None)
                        except SystemExit as err:
                            self.notify(str(err.code), severity="error")
                            return
                        target.update(
                            name=v["name"],
                            kind=v["kind"],
                            ext_id=v["ext_id"],
                            description=v["description"],
                            home=home_path(v["home"]),
                        )
                        save_db(db)
                        self.reload()

                parent = next((j for j in self.db["jobs"] if j["id"] == job["parent_id"]), None)
                values = {**job, "parent": job_label(parent) if parent else "", "home": launch.home(job.get("home"))}
                self.push_screen(JobForm(f"Edit {job_label(job)}", values, self.parent_choices(job)), job_done)

        def parent_choices(self, job: dict | None = None) -> list[tuple[str, str]]:
            """(label, name) of every job that could be this one's parent: not itself, not its own children."""
            barred = {job["id"], *(d["id"] for d in descendants(self.db, job))} if job else set()
            return [(job_label(j), j["name"]) for j in self.db["jobs"] if j["id"] not in barred]

        def action_delete(self) -> None:
            item, job = self.current_item(), self.current_job()
            if item:

                def done(yes: bool | None) -> None:
                    if yes:
                        db = load_db()
                        db["items"] = [i for i in db["items"] if i["id"] != item["id"]]
                        save_db(db)
                        self.reload()

                self.push_screen(Confirm(f"Delete #{item['id']} '{item['summary']}'?"), done)
            elif job:

                def job_done(yes: bool | None) -> None:
                    if yes:
                        db = load_db()
                        remove_job(db, next(j for j in db["jobs"] if j["id"] == job["id"]))
                        save_db(db)
                        self.reload()

                self.push_screen(
                    Confirm(f"Delete job '{job['name']}'? Its tasks are kept, unassigned; child jobs move up."),
                    job_done,
                )

        def action_filter(self) -> None:
            f = self.filters
            job = next((j for j in self.db["jobs"] if j["id"] == f.get("job")), None)
            current = {
                "text": f.get("text", ""),
                "job": "none" if f.get("job") == "none" else job["name"] if job else "",
                "status": f.get("status", ""),
                "agent": f.get("agent", ""),
                "session": f.get("session", ""),
                "idle": "" if f.get("idle") is None else f["idle"],
                "recent": "" if f.get("recent") is None else f["recent"],
            }

            def done(v: dict | None) -> None:
                if v is None:
                    return
                new: dict = {k: v[k] for k in ("text", "status", "agent", "session") if v[k]}
                for k in ("idle", "recent"):
                    if v[k]:
                        new[k] = int(v[k])
                if v["job"]:
                    ref = None if v["job"].lower() == "none" else job_by_ref(self.db, v["job"])
                    if v["job"].lower() != "none" and not ref:
                        self.notify(f"No job matching '{v['job']}'", severity="error")
                        return
                    new["job"] = "none" if ref is None else ref["id"]
                self.filters = new
                self.reload()

            self.push_screen(FilterForm("Filter the board", current), done)

        def action_clear_filters(self) -> None:
            """Esc steps back one level: off the headers, then the column searches, then column mode, then
            the Board's own filters."""
            if self.header is not None:
                self.leave_header()
            elif self.vfilters():
                self.vfilters().clear()
                self.reload()
            elif self.col is not None:
                self.leave_column()
            elif self.view == "board" and self.filters:
                self.filters = {}
                self.reload()

    return Board()


def run_tui() -> None:
    """Run the board. Sessions started from it run inside it, and the board comes back when they end."""
    build_app().run()
