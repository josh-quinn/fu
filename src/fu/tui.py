"""The interactive board (Textual). Imported lazily so plain CLI calls stay fast."""

import os

from fu.core import (
    AGENTS,
    DEFAULT_KIND,
    KIND_GLYPH,
    KINDS,
    STATUSES,
    age,
    by_session,
    check_ext_id,
    clip,
    create_job,
    heat,
    idle_days,
    job_by_ref,
    job_label,
    job_name,
    jobs_ordered,
    load_db,
    matches,
    new_item,
    resume_cmd,
    save_db,
    session_label,
    set_parent,
    skey,
    sort_items,
    today,
    update,
)

# -------------------------------------------------------------------- TUI

HELP = """\
[b]Views[/]
  [b]1[/]  Board   every follow-up in one list, filterable
  [b]2[/]  Jobs    a folder tree: Jobs (job > session > tasks) and Sessions (session > tasks)

[b]Moving and resuming[/]
  [b]↑ ↓[/]     move
  [b]enter[/]   Board: resume the highlighted session (runs its restart command and exits)
          Jobs: on a task, resume it; on a job or session, open its tasks in the Board
  [b]→[/]       Jobs: open the folder one level (job > sessions > tasks); again to step inside
  [b]←[/]       Jobs: close the folder, or step back up to its parent

[b]Working on a task[/]
  [b]a[/]  add a task (in the Jobs view: add a job)
  [b]e[/]  edit the task or job (summary, why, job, folder, agent, session)
  [b]s[/]  cycle status: todo > doing > done
  [b]d[/]  mark done (kept until you delete it)
  [b]t[/]  set last worked to today
  [b]y[/]  copy the restart command
  [b]x[/]  delete the task (or job: its tasks are kept, unassigned)
  [b]k[/]  Jobs: cycle the selected job's kind (epic > story > bug > spike > idea > btw > guide)

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
        Select,
        Static,
        Tree,
    )

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

    class FolderTree(Tree):
        """Right opens a folder (then steps into it); left closes it (then steps out)."""

        auto_expand = False
        BINDINGS = [Binding("right", "open_node", show=False), Binding("left", "close_node", show=False)]

        def action_open_node(self) -> None:
            node = self.cursor_node
            if node is None or not node.allow_expand:
                return
            if not node.is_expanded:
                node.expand()
            elif node.children:
                self.move_cursor(node.children[0])

        def action_close_node(self) -> None:
            node = self.cursor_node
            if node is None:
                return
            if node.allow_expand and node.is_expanded:
                node.collapse()
            elif node.parent is not None and node.parent is not self.root:
                self.move_cursor(node.parent)

    class Board(App):
        TITLE = "follow-ups"
        BINDINGS = [
            Binding("1", "view('board')", "Board"),
            Binding("2", "view('jobs')", "Jobs"),
            Binding("a", "add", "Add"),
            Binding("e", "edit", "Edit"),
            Binding("s", "advance", "Status"),
            Binding("d", "done", "Done"),
            Binding("t", "touch", "Worked today"),
            Binding("y", "copy", "Copy restart"),
            Binding("x", "delete", "Delete"),
            Binding("k", "kind", "Kind"),
            Binding("f", "filter", "Filter"),
            Binding("slash", "filter", "Filter", show=False),
            Binding("c", "clear_filters", "Clear", show=False),
            Binding("escape", "clear_filters", "Clear", show=False),
            Binding("full_stop", "toggle_done", "Show done"),
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
        #table, #tree { width: 5fr; height: 1fr; background: $background; }
        #tree { padding-left: 1; }
        .detail { width: 3fr; height: 1fr; margin-left: 2; padding: 1 2; border-left: solid $primary 40%; }
        ModalScreen { align: center middle; }
        .dialog { width: 76; height: auto; max-height: 90%; padding: 1 2; background: $surface;
                  border: round $primary; }
        .dialog.wide { width: 100; }
        .field { margin-top: 1; color: $text-muted; }
        .dialog Input { height: 1; border: none; padding: 0 1; background: $boost; }
        .dialog Select { height: 1; }
        .dialog Select > SelectCurrent { border: none; height: 1; padding: 0 1; background: $boost; }
        .row { height: 1; padding: 0 1; background: $boost; }
        .row:focus { background: $primary 35%; text-style: bold; }
        .row.ro { background: transparent; color: $text-disabled; }
        """

        def __init__(self) -> None:
            super().__init__()
            self.db: dict = {"items": [], "jobs": []}
            self.view = "board"
            self.show_done = False
            self.filters: dict = {}
            self.expanded: set[tuple] = {("jobs",), ("sessions",)}
            self.nodes: dict[tuple, object] = {}
            self.pick: str | None = None

        # ---- layout
        def compose(self) -> ComposeResult:
            yield Header()
            yield Static(id="tabs")
            yield Static(id="bar")
            with ContentSwitcher(initial="board", id="views"):
                with Horizontal(id="board"):
                    yield DataTable(id="table", cursor_type="row", zebra_stripes=False)
                    yield Static(id="board-detail", classes="detail")
                with Horizontal(id="jobs"):
                    yield FolderTree("root", id="tree")
                    yield Static(id="jobs-detail", classes="detail")
            yield Footer()

        def on_mount(self) -> None:
            self.query_one(DataTable).add_columns("ID", "Status", "Job", "Summary", "Added", "Last worked")
            tree = self.query_one(FolderTree)
            tree.show_root = False
            tree.guide_depth = 3
            self.reload()
            self.query_one(DataTable).focus()

        OWN_ACTIONS = {
            "view",
            "add",
            "edit",
            "advance",
            "done",
            "touch",
            "copy",
            "delete",
            "kind",
            "filter",
            "clear_filters",
            "toggle_done",
            "help",
            "quit",
        }

        def check_action(self, action: str, parameters: tuple) -> bool | None:
            if action not in self.OWN_ACTIONS:
                return True  # Textual's own actions (Tab focus, quit, palette) must keep working in dialogs
            if isinstance(self.screen, ModalScreen):
                return False  # our keys belong to the dialog
            if action in ("filter", "clear_filters") and self.view != "board":
                return False
            return not (action == "kind" and self.view != "jobs")

        # ---- state
        def reload(self, keep=None) -> None:
            self.db = load_db()
            self.refresh_table(keep if isinstance(keep, str) else None)
            self.refresh_tree()
            self.update_chrome()

        def effective_filters(self) -> dict:
            return {**self.filters, "all": self.show_done}

        def visible_items(self) -> list[dict]:
            return sort_items([i for i in self.db["items"] if matches(i, self.effective_filters())])

        def table_item(self) -> dict | None:
            table = self.query_one(DataTable)
            if not table.row_count:
                return None
            key = table.coordinate_to_cell_key(table.cursor_coordinate).row_key.value
            return next((i for i in self.db["items"] if str(i["id"]) == key), None)

        def node_data(self) -> tuple | None:
            node = self.query_one(FolderTree).cursor_node
            return node.data if node is not None else None

        def current_item(self) -> dict | None:
            if self.view == "board":
                return self.table_item()
            data = self.node_data()
            if data and data[0] == "item":
                return next((i for i in self.db["items"] if i["id"] == data[1]), None)
            return None

        def current_job(self) -> dict | None:
            data = self.node_data()
            if self.view == "jobs" and data and data[0] in ("job", "jobsess") and data[1] is not None:
                return next((j for j in self.db["jobs"] if j["id"] == data[1]), None)
            return None

        def update_chrome(self) -> None:
            tabs = [("board", "1 Board"), ("jobs", "2 Jobs")]
            self.query_one("#tabs", Static).update(
                "   ".join(f"[reverse b] {t} [/]" if v == self.view else f"[dim] {t} [/]" for v, t in tabs)
            )
            items = self.db["items"]
            n = {s: sum(i["status"] == s for i in items) for s in STATUSES}
            chips = self.filter_chips()
            self.query_one("#bar", Static).update(
                f"{n['doing']} doing · {n['todo']} todo · {n['done']} done"
                + ("" if self.show_done or not n["done"] else "  [dim](done hidden: . to show)[/]")
                + (f"   [b]filter:[/] {chips}  [dim](c clears)[/]" if chips and self.view == "board" else "")
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
            table.clear()
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
        def task_label(self, i: dict) -> Text:
            badge, colour = BADGE[i["status"]]
            t = Text(f"{badge}  ", style=colour)
            t.append(i["summary"], style="dim" if i["status"] == "done" else "bold")
            t.append(f"   {age(i['last_worked'])}", style=heat(idle_days(i)))
            return t

        def folder_label(self, glyph: str, name: str, items: list[dict], extra: str = "") -> Text:
            t = Text(f"{glyph} ")
            t.append(name, style="bold")
            open_n = sum(i["status"] != "done" for i in items)
            t.append(f"   {extra}{open_n} open", style="dim")
            if len(items) - open_n:
                t.append(f" · {len(items) - open_n} done", style="dim")
            return t

        def refresh_tree(self) -> None:
            tree = self.query_one(FolderTree)
            cursor = self.node_data()
            tree.clear()
            self.nodes = {}
            items = [i for i in self.db["items"] if self.show_done or i["status"] != "done"]

            def folder(parent, key, label):
                node = parent.add(label, data=key, expand=key in self.expanded)
                self.nodes[key] = node
                return node

            def leaves(parent, group, ctx):
                for i in sort_items(group):
                    key = ("item", i["id"], ctx)
                    self.nodes[key] = parent.add_leaf(self.task_label(i), data=key)

            jobs_root = folder(tree.root, ("jobs",), Text("Jobs", style="bold"))
            for job in [*jobs_ordered(self.db), None]:
                jid = job["id"] if job else None
                its = [i for i in items if i.get("job_id") == jid]
                if job is None and not its:
                    continue
                sessions = by_session(its)
                label = self.folder_label(
                    KIND_GLYPH[job["kind"]] if job else "·",
                    job["name"] if job else "(no job)",
                    its,
                    f"{job['kind']} · " if job else "",
                )
                node = folder(jobs_root, ("job", jid), label)
                if len(sessions) > 1:  # a job spread over sessions shows each session before its tasks
                    for sk, group in sessions.items():
                        snode = folder(
                            node, ("jobsess", jid, sk), self.folder_label("⌁", session_label(sk, group), group)
                        )
                        leaves(snode, group, f"j{jid}:{sk}")
                else:
                    leaves(node, its, f"j{jid}")
            sess_root = folder(tree.root, ("sessions",), Text("Sessions", style="bold"))
            for sk, group in by_session(items).items():
                snode = folder(sess_root, ("sess", sk), self.folder_label("⌁", session_label(sk, group), group))
                leaves(snode, group, f"s{sk}")
            if cursor is not None:
                node = self.nodes.get(cursor)
                if node is not None:
                    self.call_after_refresh(lambda: tree.move_cursor(node))
            self.show_jobs_detail()

        def show_jobs_detail(self) -> None:
            data, panel = self.node_data(), self.query_one("#jobs-detail", Static)
            if not data:
                panel.update("[dim]No tasks yet.[/]")
            elif data[0] == "item":
                item = self.current_item()
                panel.update(self.item_detail(item) if item else "")
            elif data[0] in ("job", "jobsess") and data[1] is not None:
                job = next(j for j in self.db["jobs"] if j["id"] == data[1])
                its = [i for i in self.db["items"] if i.get("job_id") == data[1]]
                sessions = by_session(its)
                panel.update(
                    f"[b]{KIND_GLYPH[job['kind']]} {escape(job['name'])}[/]  [dim]{job['kind']}[/]\n\n"
                    f"{escape(job['description']) or '[dim]No description. Press e to add one.[/]'}\n\n"
                    f"[dim]Tasks[/]  {len(its)}   [dim]Sessions[/]  {len(sessions)}\n"
                    + "".join(f"  ⌁ {escape(session_label(k, g))} ({len(g)})\n" for k, g in sessions.items())
                    + "\n[dim]enter opens its tasks in the Board · → expands · k changes kind[/]"
                )
            elif data[0] in ("sess", "jobsess"):
                key = data[1] if data[0] == "sess" else data[2]
                its = [i for i in self.db["items"] if skey(i) == key]
                cmd = resume_cmd(its[0]) if its and key else None
                jobs = sorted({job_name(self.db, i) for i in its if job_name(self.db, i)})
                panel.update(
                    f"[b]⌁ {escape(session_label(key, its))}[/]\n\n[dim]Tasks[/]  {len(its)}\n"
                    f"[dim]Jobs[/]  {escape(', '.join(jobs)) or '-'}\n\n[dim]Restart[/]\n"
                    f"{escape(cmd) if cmd else '[dim]no session id captured[/]'}\n\n[dim]enter opens its tasks in the Board[/]"
                )
            else:
                panel.update(
                    "[dim]→ opens this folder. h for help.[/]"
                    if data[0] in ("jobs", "sessions")
                    else "[dim]This job has no tasks yet.[/]"
                )

        # ---- events
        def on_data_table_row_highlighted(self, event) -> None:
            self.show_board_detail()

        def on_data_table_row_selected(self, event) -> None:
            self.resume_item(self.table_item())

        def on_tree_node_highlighted(self, event) -> None:
            self.show_jobs_detail()
            self.refresh_bindings()

        def on_tree_node_expanded(self, event) -> None:
            self.expanded.add(event.node.data)

        def on_tree_node_collapsed(self, event) -> None:
            self.expanded.discard(event.node.data)

        def on_tree_node_selected(self, event) -> None:
            data = event.node.data
            if data[0] == "item":
                self.resume_item(self.current_item())
            elif data[0] in ("jobs", "sessions"):
                event.node.toggle()
            else:
                f: dict = {}
                if data[0] in ("job", "jobsess"):
                    f["job"] = data[1] if data[1] is not None else "none"
                if data[0] == "jobsess":
                    f["session"] = data[2] or "none"
                if data[0] == "sess":
                    f["session"] = data[1] or "none"
                self.filters = f
                self.action_view("board")

        def resume_item(self, item: dict | None) -> None:
            if item and resume_cmd(item):
                self.pick = str(item["id"])
                self.exit()
            elif item:
                self.notify("No session id stored for this item", severity="warning")

        # ---- actions
        def action_view(self, name: str) -> None:
            self.view = name
            self.query_one(ContentSwitcher).current = name
            self.query_one(DataTable if name == "board" else FolderTree).focus()
            self.update_chrome()
            self.show_jobs_detail() if name == "jobs" else self.refresh_table(None)

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

        def action_toggle_done(self) -> None:
            self.show_done = not self.show_done
            self.reload()

        def action_copy(self) -> None:
            import subprocess

            item = self.current_item()
            cmd = resume_cmd(item) if item else None
            if not cmd:
                self.notify("Nothing to copy", severity="warning")
                return
            subprocess.run(["pbcopy"], input=cmd.encode(), check=False)
            self.notify("Restart command copied")

        def action_kind(self) -> None:
            job = self.current_job()
            if job:
                db = load_db()
                target = next(j for j in db["jobs"] if j["id"] == job["id"])
                target["kind"] = KINDS[(KINDS.index(target["kind"]) + 1) % len(KINDS)]
                save_db(db)
                self.reload()

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
                        for i in db["items"]:
                            if i.get("job_id") == job["id"]:
                                i["job_id"] = None
                        db["jobs"] = [j for j in db["jobs"] if j["id"] != job["id"]]
                        save_db(db)
                        self.reload()

                self.push_screen(Confirm(f"Delete job '{job['name']}'? Its tasks are kept, unassigned."), job_done)

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
            if self.filters:
                self.filters = {}
                self.reload()

    return Board()


def run_tui() -> str | None:
    """Run the board; returns the id to resume, if the user picked one."""
    app = build_app()
    app.run()
    return app.pick
