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
    filter_jobs,
    fmt_date,
    heat,
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
    session_label,
    set_parent,
    skey,
    sort_board,
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
COLUMN_TINT = "on grey19"  # background of the column picked in column mode
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
  [b]alt+.[/]  show or hide the summary / detail panel

[b]Moving and starting sessions[/]
  [b]↑ ↓[/]     move through the rows
  [b]enter[/]   Board: resume the highlighted session (runs its restart command and exits)
          Jobs: pick a whole column to search (see Column mode)
  [b]alt+r[/]   on a job (or inside its summary panel): sessions exist, so choose [b]Restart[/] or [b]New Session[/]
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
  While in column mode plain letters type, so use the modifier for shortcuts: [b]cmd+a[/], [b]cmd+e[/], [b]cmd+2[/]
  and so on. The modifier is [b]modifier[/] under \\[keys] in ~/.config/jq-tools/follow-ups/config.toml
  ("super" is Cmd and needs a terminal that reports it; "alt" or "ctrl" work anywhere). [b].[/] stays plain.

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

        FIELDS are (key, label, mode); mode is "text", "readonly" (greyed, skipped by the
        arrows) or a tuple of options (a dropdown).
        """

        BINDINGS = [
            Binding("escape", "back", "Back"),
            Binding("ctrl+s", "save", "Save"),
            Binding("up,shift+tab", "move(-1)", show=False),
            Binding("down,tab", "move(1)", show=False),
            Binding("enter", "edit_row", show=False),
        ]
        FIELDS: list[tuple[str, str, object]] = []

        def __init__(self, heading: str, values: dict | None = None) -> None:
            super().__init__()
            self.heading = heading
            self.vals = {k: str((values or {}).get(k) or "") for k, _, _ in self.FIELDS}
            self.editing: str | None = None

        def compose(self) -> ComposeResult:
            with Vertical(classes="dialog"):
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
                yield Label("[dim]↑↓ move · enter edit / confirm · ctrl+s save · esc back[/]", classes="field")

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
            return escape(value) if value else "[dim]-[/]"

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
            ("parent", "Parent job (name or id; blank for none)", "text"),
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

    class ArtifactList(ModalScreen[None]):
        """Everything the job's sessions left behind. Enter opens one in its app; x hides a wrong guess."""

        BINDINGS = [
            Binding("escape,left", "close", "Close"),
            Binding("x", "hide", "Hide this one"),
        ]

        def __init__(self, arts: list[dict]) -> None:
            super().__init__()
            self.arts = arts

        def compose(self) -> ComposeResult:
            with Vertical(classes="dialog wide"):
                yield Label("[b]Artifacts[/] [dim]enter opens · x hides a wrong guess · esc closes[/]")
                yield OptionList(id="arts")

        def on_mount(self) -> None:
            self.fill()
            self.query_one(OptionList).focus()

        def fill(self) -> None:
            opts = self.query_one(OptionList)
            opts.clear_options()
            home = str(Path.home())
            opts.add_options(
                [
                    Option(
                        Text.from_markup(
                            f"{a['kind']:<6} [b]{escape(a['label'])}[/]  [dim]{escape(a['path'].replace(home, '~'))}[/]"
                        ),
                        id=str(n),
                    )
                    for n, a in enumerate(self.arts)
                ]
            )
            opts.highlighted = 0 if self.arts else None

        def on_option_list_option_selected(self, event) -> None:
            event.stop()
            art = self.arts[int(event.option.id)]
            if not artifacts.open_path(art["path"]):
                self.notify(f"Could not open {art['path']}", severity="error")

        def action_hide(self) -> None:
            opts = self.query_one(OptionList)
            if opts.highlighted is None:
                return
            art = self.arts.pop(opts.highlighted)
            self.app.dismiss_artifact(art)
            self.fill()
            if not self.arts:
                self.dismiss(None)

        def action_close(self) -> None:
            self.dismiss(None)

    class SessionActions(ModalScreen["str | None"]):
        BINDINGS = [Binding("escape,left", "close", "Close")]

        def __init__(self, label: str) -> None:
            super().__init__()
            self.label = label

        def compose(self) -> ComposeResult:
            with Vertical(classes="dialog"):
                yield Label(f"[b]{escape(self.label)}[/]")
                yield OptionList(
                    Option("Restart", id="restart"), Option("Open session folder", id="folder"), id="actions"
                )
                yield Label("[dim]enter chooses · esc or ← closes[/]", classes="field")

        def on_mount(self) -> None:
            opts = self.query_one(OptionList)
            opts.highlighted = 0
            opts.focus()

        def on_option_list_option_selected(self, event) -> None:
            event.stop()
            self.dismiss(event.option.id)

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
        """The job already has sessions: ← → pick Restart or New Session, ↑ ↓ pick which session to restart."""

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
                yield Label("[dim]← → restart or new · ↑ ↓ session · enter · esc cancels[/]")

        def on_mount(self) -> None:
            opts = self.query_one(OptionList)
            opts.can_focus = False
            opts.highlighted = 0
            self.draw()

        def draw(self) -> None:
            def chip(name: str, label: str) -> str:
                return f"[reverse b] {label} [/]" if self.mode == name else f"[dim] {label} [/]"

            self.query_one("#choice", Static).update(f"{chip('restart', 'Restart')}   {chip('new', 'New Session')}")

        def action_pick(self, step: int) -> None:
            self.mode = "new" if step > 0 else "restart"
            self.draw()

        def action_move(self, step: int) -> None:
            opts = self.query_one(OptionList)
            at = opts.highlighted or 0
            if 0 <= at + step < opts.option_count:
                opts.highlighted = at + step

        def action_choose(self) -> None:
            if self.mode == "new":
                self.dismiss({"new": True})
            else:
                opts = self.query_one(OptionList)
                self.dismiss({"restart": opts.get_option_at_index(opts.highlighted or 0).id})

        def action_cancel(self) -> None:
            self.dismiss(None)

    class NewSession(ModalScreen["dict | None"]):
        """Start a fresh session for a job: which agent, what context to hand over, a first prompt
        (type /name for a skill) and the folder (type a path for live folder suggestions)."""

        BINDINGS = [
            Binding("escape", "cancel", "Cancel"),
            Binding("ctrl+s", "start", "Start"),
            Binding("tab", "accept", show=False, priority=True),
            Binding("ctrl+n", "next_hit", show=False, priority=True),
            Binding("ctrl+p", "prev_hit", show=False, priority=True),
        ]

        def __init__(self, db: dict, job: dict, agent: str, cwd: str) -> None:
            super().__init__()
            self.db, self.job, self.agent, self.cwd = db, job, agent, cwd

        def compose(self) -> ComposeResult:
            have = launch.available(self.db, self.job)
            with VerticalScroll(classes="dialog wide"):
                yield Label(f"[b]New session[/] [dim]for {escape(self.job['name'])}[/]")
                yield Label("Agent")
                yield Select([(a, a) for a in AGENTS], value=self.agent, allow_blank=False, id="agent")
                yield Label("Hand it" + ("" if have else "  [dim](nothing recorded for this job yet)[/]"))
                yield SelectionList(*[(label, key, key in have) for key, label in launch.CONTEXT], id="ctx")
                yield Label("Prompt  [dim]/ for skills · tab inserts · ctrl+n ctrl+p pick[/]")
                yield TextArea("", id="prompt")
                yield OptionList(id="skills")
                yield Label("Where to start  [dim]type a path · tab completes · ctrl+n ctrl+p pick[/]")
                yield Input(self.cwd, id="cwd")
                yield OptionList(id="folders")
                yield Label("[dim]ctrl+s starts the session · esc cancels[/]")

        def on_mount(self) -> None:
            for sel in ("#skills", "#folders"):
                box = self.query_one(sel, OptionList)
                box.can_focus = False
                box.display = False
                box.styles.max_height = LIST_ROWS_TYPING
            self.query_one("#prompt", TextArea).focus()

        # -- live suggestions
        def hits(self) -> OptionList | None:
            focus = self.focused
            name = {"prompt": "#skills", "cwd": "#folders"}.get(getattr(focus, "id", None))
            box = self.query_one(name, OptionList) if name else None
            return box if box is not None and box.display and box.option_count else None

        def show(self, box: OptionList, values: list[str]) -> None:
            box.clear_options()
            box.add_options([Option(v) for v in values])
            box.display = bool(values)
            box.highlighted = 0 if values else None

        def skill_word(self) -> tuple[str, int, int, int] | None:
            area = self.query_one("#prompt", TextArea)
            row, col = area.cursor_location
            before = area.document.get_line(row)[:col]
            word = before.rsplit(None, 1)[-1] if before.strip() and not before[-1:].isspace() else ""
            return (word, row, col - len(word), col) if word.startswith("/") else None

        def on_text_area_changed(self, event: TextArea.Changed) -> None:
            word = self.skill_word()
            self.show(self.query_one("#skills", OptionList), launch.skill_suggestions(word[0]) if word else [])

        def on_input_changed(self, event: Input.Changed) -> None:
            if event.input.id == "cwd":
                self.show(self.query_one("#folders", OptionList), launch.folder_suggestions(event.value))

        def check_action(self, action: str, parameters: tuple) -> bool | None:
            if action in ("next_hit", "prev_hit"):
                return self.hits() is not None
            return True

        def action_next_hit(self) -> None:
            box = self.hits()
            if box and (box.highlighted or 0) + 1 < box.option_count:
                box.highlighted = (box.highlighted or 0) + 1

        def action_prev_hit(self) -> None:
            box = self.hits()
            if box and (box.highlighted or 0) > 0:
                box.highlighted -= 1

        def action_accept(self) -> None:
            box = self.hits()
            if not box:
                self.focus_next()  # nothing to complete: Tab moves on as usual
                return
            value = str(box.get_option_at_index(box.highlighted or 0).prompt)
            if box.id == "folders":
                field = self.query_one("#cwd", Input)
                field.value = value
                field.cursor_position = len(value)
            else:
                word = self.skill_word()
                area = self.query_one("#prompt", TextArea)
                if word:
                    area.replace(value + " ", (word[1], word[2]), (word[1], word[3]))

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
                    "prompt": self.query_one("#prompt", TextArea).text,
                }
            )

        def action_cancel(self) -> None:
            self.dismiss(None)

    class HeaderTable(DataTable):
        """Up from the first row steps onto the column headers; there the arrows pick a
        header, Enter acts on it (sort on the Board, filter on Jobs) and Down returns to the rows."""

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
            elif self.app.view == "jobs":
                self.app.focus_panel()

        def on_key(self, event) -> None:
            """Typing on a Jobs header starts the search right away, without Enter."""
            app = self.app
            if "+" in event.key and event.key != "plus":
                return  # a chord (Cmd+2, Alt+R) is a shortcut, never text for the search
            if app.view == "jobs" and app.col is not None and event.is_printable:
                if event.character and event.character != " ":
                    event.stop()
                    event.prevent_default()
                    app.column_search(event.character)
                return
            if app.view == "jobs" and app.header is not None and app.header >= 0 and event.is_printable:
                col = JOB_COLUMNS_UI[app.header][0]
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
                super().action_select_cursor()

    class Board(App):
        TITLE = "follow-ups"
        BINDINGS = [
            Binding("1", "view('jobs')", "Jobs"),
            Binding("2", "view('board')", "Board"),
            Binding("a", "add", "Add"),
            Binding("alt+r", "start_session", "Session"),
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
            Binding("alt+full_stop", "toggle_panel", "Panel"),
            Binding("h", "help", "Help"),
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
        #ctx { height: 8; }
        #jobs-detail { background: $background; border: none; border-left: solid $primary 40%; padding: 1 1; }
        #jobs-detail > .option-list--option-disabled { color: $text; }
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
            self.launch: dict | None = None  # a new session to start once the TUI has exited
            self.panel_shown = True  # the detail / summary panel beside the table (alt+. toggles it)
            self.col: int | None = None  # Jobs column under column mode (Enter on a row), None outside it
            self.shown_job: int | None = None  # whose summary the panel currently shows
            self.pick: str | None = None

        # ---- layout
        def compose(self) -> ComposeResult:
            yield Header()
            yield Static(id="tabs")
            yield Static(id="bar")
            with ContentSwitcher(initial="board", id="views"):
                with Horizontal(id="board"):
                    yield HeaderTable(id="table", cursor_type="row", zebra_stripes=False)
                    yield Static(id="board-detail", classes="detail")
                with Horizontal(id="jobs"):
                    yield HeaderTable(id="jobs-table", cursor_type="row", zebra_stripes=False)
                    yield SummaryList(id="jobs-detail", classes="detail")
            yield Footer()

        def on_mount(self) -> None:
            self.reload()
            self.query_one("#table", DataTable).focus()

        # Shortcuts that also answer to modifier+key (Cmd by default), the way to reach them while
        # a column search is typing and plain letters belong to the search box.
        MODIFIED = {
            "1": "view('jobs')",
            "2": "view('board')",
            "a": "add",
            "e": "edit",
            "s": "advance",
            "d": "done",
            "t": "touch",
            "y": "copy",
            "x": "delete",
            "f": "filter",
            "c": "clear_filters",
            "h": "help",
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
            return sort_board(
                self.db, [i for i in self.db["items"] if matches(i, self.effective_filters())], *self.sort
            )

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
            chips = self.filter_chips()
            self.query_one("#bar", Static).update(
                f"{n['doing']} doing · {n['todo']} todo · {n['done']} done"
                + ("" if self.show_done or not n["done"] else "  [dim](done hidden: . to show)[/]")
                + (f"   [b]filter:[/] {chips}  [dim](c clears)[/]" if chips and self.view == "board" else "")
                + (
                    f"   [b]filter:[/] {self.job_filter_chips()}  [dim](c clears)[/]"
                    if self.jfilters and self.view == "jobs"
                    else ""
                )
                + (
                    "   [b]panel:[/] [dim]↑ ↓ move · enter opens · ← back to the rows[/]"
                    if self.in_panel and self.view == "jobs"
                    else ""
                )
                + (
                    "   [b]column:[/] [dim]← → pick · ↑ ↓ row · type or enter searches · esc all/leave[/]"
                    if self.col is not None and self.view == "jobs"
                    else ""
                )
                + (
                    "   [b]screens:[/] [dim]← → switch between Jobs and Board · ↓ to the headers[/]"
                    if self.header == -1
                    else "   [b]headers:[/] [dim]← → move · enter sorts · ↑ screens · ↓ back to rows[/]"
                    if self.header is not None and self.view == "board"
                    else "   [b]headers:[/] [dim]← → move · enter filters · ↑ screens · ↓ back to rows[/]"
                    if self.header is not None
                    else ""
                )
            )
            self.refresh_bindings()

        def filter_chips(self) -> str:
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

        # ---- board view
        def refresh_table(self, keep: str | None) -> None:
            keep = keep or (str(self.table_item()["id"]) if self.table_item() else None)
            visible = self.visible_items()
            table = self.query_one(DataTable)
            table.clear(columns=True)
            for n, (col, label) in enumerate(COLUMNS):
                mark = (" ▼" if self.sort[1] else " ▲") if self.sort[0] == col else ""
                style = "reverse bold" if self.header == n else ("bold" if self.sort[0] == col else "")
                table.add_column(Text(label + mark, style=style), key=col)
            table.show_cursor = self.header is None
            for i in visible:
                label, colour = BADGE[i["status"]]
                job = next((j for j in self.db["jobs"] if j["id"] == i.get("job_id")), None)
                table.add_row(
                    Text(str(i["id"]), style="dim"),
                    Text(label, style=colour),
                    Text(
                        f"{KIND_GLYPH[job['kind']]} {clip(job['name'], 16)}" if job else "-", style="" if job else "dim"
                    ),
                    Text(i["summary"], style="dim" if i["status"] == "done" else "bold"),
                    Text(i["added"], style="dim"),
                    Text(f"{i['last_worked']}  {age(i['last_worked'])}", style=heat(idle_days(i))),
                    key=str(i["id"]),
                )
            ids = [str(i["id"]) for i in visible]
            if keep in ids:
                table.move_cursor(row=ids.index(keep))
            self.show_board_detail()

        def item_detail(self, item: dict) -> str:
            cmd = resume_cmd(item)
            job = job_name(self.db, item)
            return (
                f"[b]{escape(item['summary'])}[/]\n\n[dim]Why[/]\n{escape(item['why'] or '-')}\n\n"
                f"[dim]Job[/]  {escape(job) if job else '-'}\n[dim]Session[/]  {escape(session_label(skey(item), [item]))}\n"
                f"[dim]Added[/]  {item['added']}\n[dim]Last worked[/]  {item['last_worked']} ({age(item['last_worked'])})\n\n"
                f"[dim]Restart[/]\n{escape(cmd) if cmd else '[dim]no session id captured[/]'}"
                + (f"\n\n[dim]Notes[/]\n{escape(item['notes'])}" if item.get("notes") else "")
            )

        def show_board_detail(self) -> None:
            item = self.table_item()
            self.query_one("#board-detail", Static).update(
                self.item_detail(item)
                if item
                else "[dim]Nothing here. Press [b]a[/] to add a follow-up, or [b]c[/] to clear filters.[/]"
            )

        # ---- jobs view
        def refresh_jobs(self) -> None:
            keep = self.cursor_key("#jobs-table")
            rows = filter_jobs(job_rows(self.db), self.jfilters)
            table = self.query_one("#jobs-table", DataTable)
            table.clear(columns=True)
            for n, (col, label) in enumerate(JOB_COLUMNS_UI):
                mark = " ●" if col in self.jfilters else ""
                table.add_column(
                    Text(
                        label + mark,
                        style="reverse bold"
                        if (self.header == n or self.col == n) and self.view == "jobs"
                        else ("bold" if col in self.jfilters else ""),
                    ),
                    key=col,
                )
            table.show_cursor = not (self.header is not None and self.view == "jobs")
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
                if self.col is not None:
                    cells[self.col].stylize(COLUMN_TINT)  # column mode: the whole column stands out
                table.add_row(*cells, key=str(job["id"]))
            ids = [str(r["job"]["id"]) for r in rows]
            if keep in ids:
                table.move_cursor(row=ids.index(keep))
            self.show_jobs_detail()

        STYLES = {"title": "bold", "meta": "dim", "head": "dim bold", "text": "", "action": ""}

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
            options, panel.full, panel.revealed = [], {}, None
            for e in summary.build(self.db, job):
                text = Text(("\n" if e["style"] == "head" else "") + e["text"], style=self.STYLES[e["style"]])
                if e["key"] and e["key"] not in ("notes",) and e["style"] == "action":
                    text.stylize("not dim")
                if e["style"] == "action" and e["key"]:
                    panel.full[e["key"]] = text
                    text = panel.clip(text)
                options.append(Option(text, id=e["key"], disabled=not e["enabled"]))
            panel.add_options(options)

        def first_enabled(self) -> int | None:
            panel = self.query_one("#jobs-detail", SummaryList)
            return next((n for n in range(panel.option_count) if not panel.get_option_at_index(n).disabled), None)

        def focus_panel(self, key: str | None = None) -> None:
            """Put the cursor in the panel, on the entry with this key (else the first actionable one)."""
            panel = self.query_one("#jobs-detail", SummaryList)
            if self.current_job() is None:
                return
            if not self.panel_shown:
                self.set_panel(True)
            at = next((n for n in range(panel.option_count) if key and panel.get_option_at_index(n).id == key), None)
            panel.highlighted = at if at is not None else self.first_enabled()
            panel.focus()
            self.in_panel = True
            self.update_chrome()

        def focus_rows(self) -> None:
            self.query_one("#jobs-table", DataTable).focus()
            self.in_panel = False
            self.update_chrome()

        def select_job(self, job_id: int) -> None:
            """Jump to a job's row (clearing filters that hide it) and stay in the panel."""
            if not any(r["job"]["id"] == job_id for r in filter_jobs(job_rows(self.db), self.jfilters)):
                self.jfilters = {}
                self.refresh_jobs()
            rows = filter_jobs(job_rows(self.db), self.jfilters)
            self.query_one("#jobs-table", DataTable).move_cursor(row=[r["job"]["id"] for r in rows].index(job_id))
            self.show_jobs_detail()
            self.update_chrome()
            self.call_after_refresh(self.focus_panel)

        def dismiss_artifact(self, art: dict) -> None:
            """Hide a wrongly detected artifact on every task that carries it."""
            db = load_db()
            job = next((j for j in db["jobs"] if j["id"] == (self.current_job() or {}).get("id")), None)
            for item in db["items"]:
                if job and item.get("job_id") == job["id"]:
                    artifacts.dismiss(item, art["path"])
            save_db(db)
            self.db = db
            self.show_jobs_detail()

        def on_option_list_option_selected(self, event) -> None:
            if event.option_list.id != "jobs-detail":
                return
            job, key = self.current_job(), event.option.id or ""
            if not job:
                return
            if key == "notes":
                self.edit_notes(job)
            elif key == "artifacts":
                self.push_screen(ArtifactList(summary.job_artifacts(self.db, job)))
            elif key.startswith("job:"):
                self.select_job(int(key.split(":", 1)[1]))
            elif key.startswith("session:"):
                self.session_actions(job, key.split(":", 1)[1])

        def edit_notes(self, job: dict) -> None:
            def done(text: str | None) -> None:
                if text is not None:
                    db = load_db()
                    next(j for j in db["jobs"] if j["id"] == job["id"])["notes"] = text
                    save_db(db)
                    self.db = db
                    self.show_jobs_detail()
                    self.call_after_refresh(self.focus_panel, "notes")

            self.push_screen(NotesForm(job.get("notes", "")), done)

        def session_actions(self, job: dict, key: str) -> None:
            item = summary.session_target(self.db, job, key)
            if not item:
                return

            def done(choice: str | None) -> None:
                if choice == "restart":
                    self.pick = str(item["id"])
                    self.exit()
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
                self.show_board_detail()

        def on_data_table_row_selected(self, event) -> None:
            if event.data_table.id == "jobs-table":
                self.enter_column()
            else:
                self.resume_item(self.table_item())

        def restart_job(self, job: dict | None) -> None:
            item = job_resume_item(self.db, job) if job else None
            if not job:
                return
            if not item:
                self.notify("This job has no session to restart", severity="warning")
                return

            def done(yes: bool | None) -> None:
                if yes:
                    self.pick = str(item["id"])
                    self.exit()

            self.push_screen(Confirm(f"Restart session?\n{item['agent']} · {item['summary']}"), done)

        def resume_item(self, item: dict | None) -> None:
            if item and resume_cmd(item):
                self.pick = str(item["id"])
                self.exit()
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
            self.col = None
            cols = COLUMNS if self.view == "board" else JOB_COLUMNS_UI
            # the Board opens on the column it is sorted by; Jobs on the first column
            self.header = (
                next((n for n, (c, _) in enumerate(cols) if c == self.sort[0]), 0) if self.view == "board" else 0
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

        # ---- column mode (Jobs): Enter on a row picks a whole column to search
        def enter_column(self) -> None:
            if self.current_job() is None:
                return
            self.col = self.col if self.col is not None else JOB_COLUMNS_UI.index(("title", "Title"))
            self.refresh_view()

        def leave_column(self) -> None:
            self.col = None
            self.refresh_view()

        def column_move(self, step: int) -> None:
            self.col = max(0, min(len(JOB_COLUMNS_UI) - 1, self.col + step))
            self.refresh_view()

        def column_search(self, typed: str = "") -> None:
            """Search the highlighted column. Plain Enter starts from the highlighted row's own value, so
            Enter, Enter shows every job that shares it (every child of a parent, say)."""
            job = self.current_job()
            if self.col is None or job is None:
                return
            col = JOB_COLUMNS_UI[self.col][0]
            row = next(r for r in job_rows(self.db) if r["job"]["id"] == job["id"])
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
            last = (len(COLUMNS) if self.view == "board" else len(JOB_COLUMNS_UI)) - 1
            if self.view == "board" and self.header + step < 0:
                self.action_view("jobs")  # swipe left past the first header onto Jobs
            elif self.view == "jobs" and self.header + step > last:
                self.action_view("board")  # swipe right past the last header onto the Board
            else:
                self.header = max(0, min(last, self.header + step))
                self.refresh_view()

        def header_enter(self) -> None:
            if self.view == "board":
                self.sort_by_header()
            else:
                self.filter_by_header()

        def header_x(self, n: int) -> int:
            """Where header n starts, so a popup can sit under it."""
            table = self.query_one("#jobs-table", DataTable)
            try:
                return 2 + sum(c.get_render_width(table) for c in list(table.columns.values())[:n])
            except Exception:  # noqa: BLE001 - placement is cosmetic; fall back to the left edge
                return 2

        def set_jfilter(self, col: str, value: dict | None) -> None:
            if value:
                self.jfilters[col] = value
            else:
                self.jfilters.pop(col, None)
            self.refresh_jobs()
            self.update_chrome()

        def filter_by_header(self, typed: str = "") -> None:
            self.filter_column(self.header, typed)

        def filter_column(self, n: int, typed: str = "", start: date | None = None) -> None:
            """Open column n's filter: a search list (text, with `typed` already in the box), the kind
            list, or the date picker."""
            col, label = JOB_COLUMNS_UI[n]
            saved = self.jfilters.get(col)
            x = self.header_x(n)
            if col in DATE_COLUMNS:
                start = start or (
                    date.fromisoformat(saved["from"]) if saved and saved["from"] == saved["to"] else date.today()
                )

                def picked(v: dict | None) -> None:
                    if v is not None:
                        self.set_jfilter(col, None if v.get("clear") else v)

                self.push_screen(DatePick(label, start, x), picked)
                return
            others = {k: v for k, v in self.jfilters.items() if k != col}
            rows = filter_jobs(job_rows(self.db), others)

            def picked_text(v: str | None) -> None:
                self.set_jfilter(col, saved if v is None else ({"text": v} if v else None))

            self.push_screen(
                Suggest(
                    label,
                    lambda q: suggestions(rows, col, q),
                    typed or (saved["text"] if saved and "text" in saved else ""),
                    lambda value: self.set_jfilter(col, {"text": value} if value else None),
                    x,
                ),
                picked_text,
            )

        def job_filter_chips(self) -> str:
            labels = dict(JOB_COLUMNS_UI)
            return " · ".join(
                f"{labels[c]}: " + (f"“{escape(f['text'])}”" if "text" in f else escape(f["label"]))
                for c, f in self.jfilters.items()
            )

        def sort_by_header(self) -> None:
            col = COLUMNS[self.header][0]
            self.sort = (col, not self.sort[1]) if self.sort[0] == col else (col, False)
            self.refresh_view()

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
                    self.pick = v["restart"]
                    self.exit()

            self.push_screen(SessionChoice(choices), chosen)

        def new_session(self, job: dict) -> None:
            """Ask how to start a session for the job, then exit so the CLI can run it."""
            items = sorted(
                (i for i in self.db["items"] if i.get("job_id") == job["id"] and i.get("cwd")),
                key=lambda i: (i["last_worked"], i["id"]),
                reverse=True,
            )
            last = items[0] if items else None

            def started(v: dict | None) -> None:
                if v:
                    db = load_db()
                    fresh = next(j for j in db["jobs"] if j["id"] == job["id"])
                    prompt = launch.full_prompt(db, fresh, v["include"], v["prompt"])
                    self.launch = {"job_id": job["id"], "agent": v["agent"], "cwd": v["cwd"], "prompt": prompt}
                    self.exit()

            self.push_screen(
                NewSession(self.db, job, last["agent"] if last else AGENTS[0], last["cwd"] if last else os.getcwd()),
                started,
            )

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
                            )
                        except SystemExit as err:  # core reports bad ids and parents by exiting
                            self.notify(str(err.code), severity="error")
                            return
                        save_db(db)
                        self.reload()

                self.push_screen(JobForm("New job", {"kind": DEFAULT_KIND}), job_done)
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
                        target.update(name=v["name"], kind=v["kind"], ext_id=v["ext_id"], description=v["description"])
                        save_db(db)
                        self.reload()

                parent = next((j for j in self.db["jobs"] if j["id"] == job["parent_id"]), None)
                values = {**job, "parent": job_label(parent) if parent else ""}
                self.push_screen(JobForm(f"Edit {job_label(job)}", values), job_done)

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
            if self.header is not None:
                self.leave_header()
            elif self.col is not None and not self.jfilters:
                self.leave_column()
            elif self.view == "jobs" and self.jfilters:
                self.jfilters = {}
                self.reload()
            elif self.view == "board" and self.filters:
                self.filters = {}
                self.reload()

    return Board()


def run_tui() -> "str | dict | None":
    """Run the board; returns the id to resume, or a spec for a new session, if the user picked one."""
    app = build_app()
    app.run()
    return app.launch or app.pick
