"""Reports browser screen."""

from pathlib import Path
from textual.screen import Screen, ModalScreen
from textual.containers import Container, Horizontal, Vertical
from textual.widgets import Static, ListView, ListItem, Label, Input
from textual.binding import Binding
from config import ConfigManager, ReportManager
from tui.utils import format_bytes


class ReportListItem(ListItem):
    """A single report entry."""

    def __init__(self, report: dict, **kwargs):
        super().__init__(**kwargs)
        self.report = report

    def compose(self):
        timestamp = self.report["timestamp"].strftime("%Y-%m-%d %H:%M") if self.report.get("timestamp") else "unknown"
        yield Label(f"{timestamp}  {self.report['name']}")


class ReportList(Container):
    """Bordered report list panel."""

    DEFAULT_CSS = """
    ReportList {
        width: 1fr;
        height: 1fr;
        border: solid $primary;
        border-title-color: $text;
        border-title-style: bold;
        padding: 0;
    }

    ReportList ListView {
        width: 1fr;
        height: 1fr;
        background: $surface;
    }

    ReportList ListView > ListItem {
        padding: 0 1;
        height: 1;
        background: $surface;
    }

    ReportList ListView > ListItem.--highlight {
        background: $primary 30%;
    }

    ReportList ListView:focus > ListItem.--highlight {
        background: $primary 50%;
    }

    ReportList ListView > ListItem.--highlight Label {
        color: $text;
        text-style: bold;
    }
    """

    def __init__(self, reports: list[dict], filter_text: str = ""):
        super().__init__()
        self.reports = reports
        self.border_title = "[1] Reports" + (f"  [dim]/{filter_text}[/dim]" if filter_text else "")

    def compose(self):
        if self.reports:
            yield ListView(*[ReportListItem(report) for report in self.reports], id="report-listview")
        else:
            yield Static(" No reports found\n\n Run a profile to generate one", id="empty-state")


class ReportDetail(Container):
    """Details for the selected report."""

    DEFAULT_CSS = """
    ReportDetail {
        width: 1fr;
        height: 1fr;
        border: solid $primary;
        border-title-color: $text;
        border-title-style: bold;
        padding: 1 2;
    }

    ReportDetail #detail-content {
        width: 1fr;
        height: 1fr;
        overflow-y: auto;
    }
    """

    def __init__(self):
        super().__init__()
        self.border_title = "[2] Details"
        self._content = Static("Select a report to view details", id="detail-content")

    def compose(self):
        yield self._content

    def update_detail(self, report: dict | None) -> None:
        if report is None:
            self._content.update("[dim]Select a report to view details[/dim]")
            return
        path: Path = report["path"]
        timestamp = report["timestamp"].strftime("%Y-%m-%d %H:%M:%S") if report.get("timestamp") else "unknown"
        lines = [
            f"[bold dim]{'Name:':<12}[/bold dim] {report['name']}",
            f"[bold dim]{'File:':<12}[/bold dim] {report['filename']}",
            f"[bold dim]{'Date:':<12}[/bold dim] {timestamp}",
            f"[bold dim]{'Size:':<12}[/bold dim] {format_bytes(report['size'])}",
            "",
        ]
        try:
            text = path.read_text(encoding="utf-8")
            lines.extend(_summarize_report_text(text))
        except OSError as err:
            lines.append(f"[red]Could not read report: {err}[/red]")
        self._content.update("\n".join(lines))


class ReportActionBar(Container):
    """Action bar for reports."""

    DEFAULT_CSS = """
    ReportActionBar {
        width: 1fr;
        height: 3;
        border: solid $primary;
        border-title-color: $text;
        border-title-style: bold;
        padding: 0 1;
        align: left middle;
    }
    """

    def __init__(self):
        super().__init__()
        self.border_title = "[3] Actions"

    def compose(self):
        yield Static(
            "[bold cyan]/[/bold cyan]: Search  [bold green]v[/bold green]/[bold green]Enter[/bold green]: View  "
            "[bold red]d[/bold red]: Delete  [bold yellow]p[/bold yellow]: Prune  [bold dim]Esc[/bold dim]: Back"
        )


class TextViewerModal(ModalScreen[None]):
    """Scrollable text viewer modal."""

    BINDINGS = [Binding("escape", "close", "Close", show=False)]

    DEFAULT_CSS = """
    TextViewerModal {
        align: center middle;
    }

    TextViewerModal #viewer-container {
        width: 90%;
        height: 90%;
        border: solid $primary;
        border-title-color: $text;
        border-title-style: bold;
        background: $surface;
        padding: 1 2;
    }

    TextViewerModal #viewer-content {
        width: 1fr;
        height: 1fr;
        overflow-y: auto;
    }
    """

    def __init__(self, title: str, content: str):
        super().__init__()
        self._title = title
        self._content = content

    def compose(self):
        with Container(id="viewer-container") as container:
            container.border_title = self._title
            yield Static(self._content, id="viewer-content")

    def action_close(self) -> None:
        self.dismiss(None)


class ConfirmModal(ModalScreen[bool]):
    """Confirmation modal."""

    BINDINGS = [Binding("escape", "cancel", "Cancel", show=False)]

    DEFAULT_CSS = """
    ConfirmModal {
        align: center middle;
    }

    ConfirmModal #confirm-container {
        width: 70;
        height: auto;
        border: solid $error;
        border-title-color: $error;
        border-title-style: bold;
        background: $surface;
        padding: 1 2;
    }
    """

    def __init__(self, title: str, message: str):
        super().__init__()
        self._title = title
        self._message = message

    def compose(self):
        with Container(id="confirm-container") as container:
            container.border_title = self._title
            yield Static(self._message)
            yield Static("[bold green]y[/bold green] / [bold green]Enter[/bold green]: Confirm  [bold dim]Esc[/bold dim]: Cancel")

    def key_y(self) -> None:
        self.dismiss(True)

    def key_enter(self) -> None:
        self.dismiss(True)

    def action_cancel(self) -> None:
        self.dismiss(False)


class PruneReportsModal(ModalScreen[int | None]):
    """Prompt for report prune keep count."""

    BINDINGS = [Binding("escape", "cancel", "Cancel", show=False)]

    DEFAULT_CSS = """
    PruneReportsModal {
        align: center middle;
    }

    PruneReportsModal #prune-container {
        width: 60;
        height: auto;
        border: solid $primary;
        border-title-color: $text;
        border-title-style: bold;
        background: $surface;
        padding: 1 2;
    }

    PruneReportsModal #form-error {
        color: $error;
    }
    """

    def compose(self):
        with Container(id="prune-container") as container:
            container.border_title = "Prune Reports"
            yield Static("Keep the most recent N reports.")
            yield Input(value="10", id="keep-count")
            yield Static("", id="form-error")
            yield Static("[bold green]Enter[/bold green]: Preview  [bold dim]Esc[/bold dim]: Cancel")

    def on_mount(self) -> None:
        self.query_one("#keep-count", Input).focus()

    def key_enter(self) -> None:
        value = self.query_one("#keep-count", Input).value.strip()
        try:
            keep_count = int(value)
            if keep_count < 0:
                raise ValueError
        except ValueError:
            self.query_one("#form-error", Static).update("[bold red]Enter a non-negative number.[/bold red]")
            return
        self.dismiss(keep_count)

    def action_cancel(self) -> None:
        self.dismiss(None)


def _summarize_report_text(text: str) -> list[str]:
    interesting_prefixes = (
        "Mode     :",
        "Profile  :",
        "Suite    :",
        "Profiles :",
        "Added ",
        "Updated ",
        "Removed ",
        "Unchanged ",
        "Dirs added ",
        "Dirs removed ",
        "Errors ",
    )
    lines = [line for line in text.splitlines() if line.startswith(interesting_prefixes)]
    return lines[:24] if lines else ["[dim]No summary lines found.[/dim]"]


class ReportsScreen(Screen):
    """Report viewing and search screen."""

    BINDINGS = [
        Binding("escape", "back", "Back", show=False),
        Binding("/", "search", "Search", show=False),
        Binding("enter", "view_report", "View", show=False),
        Binding("v", "view_report", "View", show=False),
        Binding("d", "delete_report", "Delete", show=False),
        Binding("p", "prune_reports", "Prune", show=False),
    ]

    DEFAULT_CSS = """
    ReportsScreen {
        background: $surface;
    }

    ReportsScreen #reports-layout {
        width: 1fr;
        height: 1fr;
    }

    ReportsScreen #search-input {
        width: 1fr;
        height: 3;
    }

    ReportsScreen #panels-row {
        width: 1fr;
        height: 1fr;
    }

    ReportsScreen #status-bar {
        width: 1fr;
        height: 1;
        background: $surface;
        color: $text-muted;
        padding: 0 1;
        dock: bottom;
    }
    """

    def __init__(self, config_manager: ConfigManager):
        super().__init__()
        self.config_manager = config_manager
        self.report_manager = ReportManager()
        self._reports: list[dict] = []
        self._filter = ""
        self._report_list: ReportList | None = None
        self._detail_panel: ReportDetail | None = None
        self._status_bar: Static | None = None
        self._pending_delete_path: Path | None = None

    def compose(self):
        self._reports = self._load_reports()
        with Vertical(id="reports-layout"):
            yield Input(placeholder="Filter reports by profile or suite name", id="search-input")
            with Horizontal(id="panels-row"):
                self._report_list = ReportList(self._reports, self._filter)
                yield self._report_list
                self._detail_panel = ReportDetail()
                yield self._detail_panel
            yield ReportActionBar()
        self._status_bar = Static("", id="status-bar")
        yield self._status_bar

    def on_mount(self) -> None:
        self.query_one("#search-input", Input).display = False
        if self._reports:
            self._show_report(0)
            self.query_one("#report-listview", ListView).focus()

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id == "search-input":
            self._filter = event.value.strip()
            self._refresh_list()

    def on_list_view_highlighted(self, event: ListView.Highlighted) -> None:
        if isinstance(event.item, ReportListItem) and self._detail_panel:
            self._detail_panel.update_detail(event.item.report)

    def _load_reports(self) -> list[dict]:
        reports = self.report_manager.list_reports(sort_by="date")
        if self._filter:
            query = self._filter.lower()
            reports = [r for r in reports if query in (r.get("name") or "").lower()]
        return reports

    def _show_report(self, index: int) -> None:
        if 0 <= index < len(self._reports) and self._detail_panel:
            self._detail_panel.update_detail(self._reports[index])

    def _selected_report(self) -> dict | None:
        try:
            item = self.query_one("#report-listview", ListView).highlighted_child
        except Exception:
            return None
        return item.report if isinstance(item, ReportListItem) else None

    def _refresh_list(self) -> None:
        self._reports = self._load_reports()
        if self._report_list:
            self._report_list.remove()
        row = self.query_one("#panels-row", Horizontal)
        self._report_list = ReportList(self._reports, self._filter)
        row.mount(self._report_list, before=self._detail_panel)
        if self._reports:
            self._show_report(0)
            try:
                self.query_one("#report-listview", ListView).focus()
            except Exception:
                pass
        elif self._detail_panel:
            self._detail_panel.update_detail(None)

    def _set_status(self, message: str) -> None:
        if self._status_bar:
            self._status_bar.update(message)

    def action_search(self) -> None:
        search = self.query_one("#search-input", Input)
        search.display = True
        search.focus()

    def action_view_report(self) -> None:
        report = self._selected_report()
        if not report:
            self._set_status("No report selected.")
            return
        try:
            content = report["path"].read_text(encoding="utf-8")
        except OSError as err:
            self._set_status(f"Could not read report: {err}")
            return
        self.app.push_screen(TextViewerModal(report["filename"], content))

    def action_delete_report(self) -> None:
        report = self._selected_report()
        if not report:
            self._set_status("No report selected.")
            return
        self._pending_delete_path = report["path"]
        self.app.push_screen(
            ConfirmModal("Delete Report", f"Delete report '{report['filename']}'?"),
            callback=self._on_delete_confirmed,
        )

    def _on_delete_confirmed(self, confirmed: bool) -> None:
        path = self._pending_delete_path
        self._pending_delete_path = None
        if not confirmed or not path:
            self._set_status("Delete cancelled.")
            return
        try:
            self.report_manager.delete_report(path)
            self._set_status(f"Deleted report '{path.name}'.")
            self._refresh_list()
        except OSError as err:
            self._set_status(f"Delete failed: {err}")

    def action_prune_reports(self) -> None:
        self.app.push_screen(PruneReportsModal(), callback=self._preview_prune)

    def _preview_prune(self, keep_count: int | None) -> None:
        if keep_count is None:
            self._set_status("Prune cancelled.")
            return
        result = self.report_manager.prune_reports(keep_count=keep_count, dry_run=True)
        paths = result["deleted"]
        if not paths:
            self._set_status(f"No reports to prune when keeping {keep_count}.")
            return
        names = "\n".join(f"  {path.name}" for path in paths[:20])
        if len(paths) > 20:
            names += f"\n  ... and {len(paths) - 20} more"
        message = f"Delete {len(paths)} report(s), freeing {format_bytes(result['space_freed'])}?\n\n{names}"
        self.app.push_screen(
            ConfirmModal("Confirm Prune", message),
            callback=lambda confirmed: self._on_prune_confirmed(confirmed, keep_count),
        )

    def _on_prune_confirmed(self, confirmed: bool, keep_count: int) -> None:
        if not confirmed:
            self._set_status("Prune cancelled.")
            return
        result = self.report_manager.prune_reports(keep_count=keep_count, dry_run=False)
        self._refresh_list()
        self._set_status(f"Pruned {len(result['deleted'])} report(s).")

    def action_back(self) -> None:
        search = self.query_one("#search-input", Input)
        if search.display:
            search.display = False
            search.value = ""
            self._filter = ""
            self._refresh_list()
            return
        self.app.pop_screen()