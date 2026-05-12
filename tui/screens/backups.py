"""Backup management screen."""

from pathlib import Path
from typing import Any
from textual.screen import Screen, ModalScreen
from textual.containers import Container, Horizontal, Vertical
from textual.widgets import Static, ListView, ListItem, Label, Input, Checkbox
from textual.binding import Binding
from config import ConfigManager
from backup import BackupEntry, BackupManager, BACKUPS_DIR
from tui.utils import format_bytes


class BackupListItem(ListItem):
    """A single backup entry."""

    def __init__(self, entry: BackupEntry, **kwargs):
        super().__init__(**kwargs)
        self.entry = entry

    def compose(self):
        pinned = " P" if self.entry.pinned else ""
        created = self.entry.created_at[:16] if self.entry.created_at else "unknown"
        yield Label(f"{created}  {self.entry.profile}{pinned}")


class BackupList(Container):
    """Bordered backup list panel."""

    DEFAULT_CSS = """
    BackupList {
        width: 1fr;
        height: 1fr;
        border: solid $primary;
        border-title-color: $text;
        border-title-style: bold;
        padding: 0;
    }

    BackupList ListView {
        width: 1fr;
        height: 1fr;
        background: $surface;
    }

    BackupList ListView > ListItem {
        padding: 0 1;
        height: 1;
        background: $surface;
    }

    BackupList ListView > ListItem.--highlight {
        background: $primary 30%;
    }

    BackupList ListView:focus > ListItem.--highlight {
        background: $primary 50%;
    }

    BackupList ListView > ListItem.--highlight Label {
        color: $text;
        text-style: bold;
    }
    """

    def __init__(self, backups: list[BackupEntry]):
        super().__init__(id="backup-list")
        self.can_focus = True
        self.backups = backups
        self.border_title = "[1] Backups"

    def compose(self):
        if self.backups:
            yield ListView(*[BackupListItem(entry) for entry in self.backups], id="backup-listview")
        else:
            yield Static(" No backups found\n\n Run a live profile to create one", id="empty-state")


class BackupDetail(Container):
    """Details for the selected backup."""

    DEFAULT_CSS = """
    BackupDetail {
        width: 1fr;
        height: 1fr;
        border: solid $primary;
        border-title-color: $text;
        border-title-style: bold;
        padding: 1 2;
    }

    BackupDetail #detail-content {
        width: 1fr;
        height: 1fr;
        overflow-y: auto;
    }
    """

    def __init__(self, backup_manager: BackupManager):
        super().__init__(id="backup-detail")
        self.can_focus = True
        self.backup_manager = backup_manager
        self.border_title = "[2] Details"
        self._content = Static("Select a backup to view details", id="detail-content")

    def compose(self):
        yield self._content

    def update_detail(self, entry: BackupEntry | None) -> None:
        if entry is None:
            self._content.update("[dim]Select a backup to view details[/dim]")
            return
        backup_file = BACKUPS_DIR / entry.filename
        exists = backup_file.exists()
        file_count = "unknown"
        total_size = "unknown"
        try:
            contents = self.backup_manager.view_backup_contents(entry.id)
            file_count = str(len(contents))
            total_size = format_bytes(sum(size for _, size in contents))
        except Exception:
            pass
        lines = [
            f"[bold dim]{'ID:':<12}[/bold dim] {entry.id}",
            f"[bold dim]{'Profile:':<12}[/bold dim] {entry.profile}",
            f"[bold dim]{'Created:':<12}[/bold dim] {entry.created_at}",
            f"[bold dim]{'Result:':<12}[/bold dim] {entry.run_result}",
            f"[bold dim]{'Pinned:':<12}[/bold dim] {'yes' if entry.pinned else 'no'}",
            f"[bold dim]{'Note:':<12}[/bold dim] {entry.note or '[dim]none[/dim]'}",
            "",
            f"[bold dim]{'Target:':<12}[/bold dim] {entry.target}",
            f"[bold dim]{'Zip:':<12}[/bold dim] {backup_file}  {'[green]OK[/green]' if exists else '[red]MISSING[/red]'}",
            f"[bold dim]{'Files:':<12}[/bold dim] {file_count}",
            f"[bold dim]{'Size:':<12}[/bold dim] {total_size}",
        ]
        self._content.update("\n".join(lines))


class BackupActionBar(Container):
    """Action bar for backups."""

    DEFAULT_CSS = """
    BackupActionBar {
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
        super().__init__(id="backup-actions")
        self.can_focus = True
        self.border_title = "[3] Actions"

    def compose(self):
        yield Static(
            "[bold green]v[/bold green]: View  [bold yellow]r[/bold yellow]: Restore  "
            "[bold cyan]p[/bold cyan]: Pin/unpin  [bold red]d[/bold red]: Delete  "
            "[bold yellow]P[/bold yellow]: Prune  [bold dim]Esc[/bold dim]: Back"
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
        width: 72;
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


class PruneBackupsModal(ModalScreen[dict | None]):
    """Prompt for backup prune options."""

    BINDINGS = [Binding("escape", "cancel", "Cancel", show=False)]

    DEFAULT_CSS = """
    PruneBackupsModal {
        align: center middle;
    }

    PruneBackupsModal #prune-container {
        width: 64;
        height: auto;
        border: solid $primary;
        border-title-color: $text;
        border-title-style: bold;
        background: $surface;
        padding: 1 2;
    }

    PruneBackupsModal #form-error {
        color: $error;
    }
    """

    def compose(self):
        with Container(id="prune-container") as container:
            container.border_title = "Prune Backups"
            yield Static("Keep the most recent N backups.")
            yield Input(value="10", id="keep-count")
            yield Checkbox("Include pinned backups", id="include-pinned")
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
        self.dismiss({
            "keep": keep_count,
            "include_pinned": self.query_one("#include-pinned", Checkbox).value,
        })

    def action_cancel(self) -> None:
        self.dismiss(None)


class BackupsScreen(Screen):
    """Backup management screen."""

    BINDINGS = [
        Binding("ctrl+c", "force_quit", "Force Quit", show=False),
        Binding("escape", "back", "Back", show=False),
        Binding("q", "back", "Back", show=False),
        Binding("ctrl+1", "focus_section_1", "Section 1", show=False),
        Binding("ctrl+2", "focus_section_2", "Section 2", show=False),
        Binding("ctrl+3", "focus_section_3", "Section 3", show=False),
        Binding("alt+1", "focus_section_1", "Section 1", show=False),
        Binding("alt+2", "focus_section_2", "Section 2", show=False),
        Binding("alt+3", "focus_section_3", "Section 3", show=False),
        Binding("f1", "focus_section_1", "Section 1", show=False),
        Binding("f2", "focus_section_2", "Section 2", show=False),
        Binding("f3", "focus_section_3", "Section 3", show=False),
        Binding("v", "view_backup", "View", show=False),
        Binding("r", "restore_backup", "Restore", show=False),
        Binding("p", "toggle_pin", "Pin", show=False),
        Binding("d", "delete_backup", "Delete", show=False),
        Binding("shift+p", "prune_backups", "Prune", show=False),
    ]

    DEFAULT_CSS = """
    BackupsScreen {
        background: $surface;
    }

    BackupsScreen #backups-layout {
        width: 1fr;
        height: 1fr;
    }

    BackupsScreen #panels-row {
        width: 1fr;
        height: 1fr;
    }

    BackupsScreen #status-bar {
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
        self.backup_manager = BackupManager()
        self._backups: list[BackupEntry] = []
        self._backup_list: BackupList | None = None
        self._detail_panel: BackupDetail | None = None
        self._status_bar: Static | None = None
        self._pending_backup_id: str | None = None
        self._pending_force_delete = False

    def compose(self):
        self._backups = self.backup_manager.list_backups()
        with Vertical(id="backups-layout"):
            with Horizontal(id="panels-row"):
                self._backup_list = BackupList(self._backups)
                yield self._backup_list
                self._detail_panel = BackupDetail(self.backup_manager)
                yield self._detail_panel
            yield BackupActionBar()
        self._status_bar = Static("", id="status-bar")
        yield self._status_bar

    def on_mount(self) -> None:
        if self._backups:
            self._show_backup(0)
            self.query_one("#backup-listview", ListView).focus()

    def on_list_view_highlighted(self, event: ListView.Highlighted) -> None:
        if isinstance(event.item, BackupListItem) and self._detail_panel:
            self._detail_panel.update_detail(event.item.entry)

    def _show_backup(self, index: int) -> None:
        if 0 <= index < len(self._backups) and self._detail_panel:
            self._detail_panel.update_detail(self._backups[index])

    def _selected_backup(self) -> BackupEntry | None:
        try:
            item = self.query_one("#backup-listview", ListView).highlighted_child
        except Exception:
            return None
        return item.entry if isinstance(item, BackupListItem) else None

    def _refresh_list(self) -> None:
        self._backups = self.backup_manager.list_backups()
        if self._backup_list:
            self._backup_list.remove()
        row = self.query_one("#panels-row", Horizontal)
        self._backup_list = BackupList(self._backups)
        row.mount(self._backup_list, before=self._detail_panel)
        if self._backups:
            self._show_backup(0)
            try:
                self.query_one("#backup-listview", ListView).focus()
            except Exception:
                pass
        elif self._detail_panel:
            self._detail_panel.update_detail(None)

    def _set_status(self, message: str) -> None:
        if self._status_bar:
            self._status_bar.update(message)

    def _focus_widget(self, selector: str, widget_type: type[Any]) -> bool:
        try:
            self.query_one(selector, widget_type).focus()
            return True
        except Exception:
            return False

    def action_force_quit(self) -> None:
        self.app.exit()

    def action_focus_section_1(self) -> None:
        if not self._focus_widget("#backup-listview", ListView):
            if not self._focus_widget("#backup-list", Container):
                self._set_status("[dim]Backups list not focusable right now[/dim]")

    def action_focus_section_2(self) -> None:
        if not self._focus_widget("#backup-detail", Container):
            self._set_status("[dim]Details section not focusable right now[/dim]")

    def action_focus_section_3(self) -> None:
        if not self._focus_widget("#backup-actions", Container):
            self._set_status("[dim]Actions section not focusable right now[/dim]")

    def action_view_backup(self) -> None:
        entry = self._selected_backup()
        if not entry:
            self._set_status("No backup selected.")
            return
        try:
            contents = self.backup_manager.view_backup_contents(entry.id)
        except ValueError as err:
            self._set_status(str(err))
            return
        lines = [f"{path:<70} {format_bytes(size):>10}" for path, size in contents]
        if not lines:
            lines = ["(backup is empty)"]
        self.app.push_screen(TextViewerModal(entry.id, "\n".join(lines)))

    def action_restore_backup(self) -> None:
        entry = self._selected_backup()
        if not entry:
            self._set_status("No backup selected.")
            return
        try:
            count = len(self.backup_manager.view_backup_contents(entry.id))
        except ValueError as err:
            self._set_status(str(err))
            return
        self._pending_backup_id = entry.id
        message = (
            f"Restore backup '{entry.id}'?\n\n"
            f"Created: {entry.created_at}\n"
            f"Profile : {entry.profile}\n"
            f"Target  : {entry.target}\n"
            f"Files   : {count}\n\n"
            "Files at the target path may be overwritten."
        )
        self.app.push_screen(ConfirmModal("Restore Backup", message), callback=self._on_restore_confirmed)

    def _on_restore_confirmed(self, confirmed: bool) -> None:
        backup_id = self._pending_backup_id
        self._pending_backup_id = None
        if not confirmed or not backup_id:
            self._set_status("Restore cancelled.")
            return
        try:
            self.backup_manager.restore_backup(backup_id)
            self._set_status(f"Restored backup '{backup_id}'.")
        except (ValueError, OSError) as err:
            self._set_status(f"Restore failed: {err}")

    def action_toggle_pin(self) -> None:
        entry = self._selected_backup()
        if not entry:
            self._set_status("No backup selected.")
            return
        try:
            if entry.pinned:
                self.backup_manager.unpin_backup(entry.id)
                self._set_status(f"Unpinned backup '{entry.id}'.")
            else:
                self.backup_manager.pin_backup(entry.id)
                self._set_status(f"Pinned backup '{entry.id}'.")
            self._refresh_list()
        except ValueError as err:
            self._set_status(str(err))

    def action_delete_backup(self) -> None:
        entry = self._selected_backup()
        if not entry:
            self._set_status("No backup selected.")
            return
        self._pending_backup_id = entry.id
        self._pending_force_delete = entry.pinned
        note = "\n\nThis backup is pinned; confirming will force deletion." if entry.pinned else ""
        self.app.push_screen(
            ConfirmModal("Delete Backup", f"Delete backup '{entry.id}'?{note}"),
            callback=self._on_delete_confirmed,
        )

    def _on_delete_confirmed(self, confirmed: bool) -> None:
        backup_id = self._pending_backup_id
        force = self._pending_force_delete
        self._pending_backup_id = None
        self._pending_force_delete = False
        if not confirmed or not backup_id:
            self._set_status("Delete cancelled.")
            return
        try:
            self.backup_manager.delete_backup(backup_id, force=force)
            self._refresh_list()
            self._set_status(f"Deleted backup '{backup_id}'.")
        except ValueError as err:
            self._set_status(str(err))

    def action_prune_backups(self) -> None:
        self.app.push_screen(PruneBackupsModal(), callback=self._preview_prune)

    def _preview_prune(self, result: dict | None) -> None:
        if result is None:
            self._set_status("Prune cancelled.")
            return
        keep = result["keep"]
        include_pinned = result["include_pinned"]
        candidates = self.backup_manager.list_backups()
        if not include_pinned:
            candidates = [entry for entry in candidates if not entry.pinned]
        candidates.sort(key=lambda entry: entry.created_at, reverse=True)
        to_delete = candidates[keep:]
        if not to_delete:
            self._set_status(f"No backups to prune when keeping {keep}.")
            return
        names = "\n".join(f"  {entry.id}" for entry in to_delete[:20])
        if len(to_delete) > 20:
            names += f"\n  ... and {len(to_delete) - 20} more"
        self.app.push_screen(
            ConfirmModal("Confirm Prune", f"Delete {len(to_delete)} backup(s)?\n\n{names}"),
            callback=lambda confirmed: self._on_prune_confirmed(confirmed, keep, include_pinned),
        )

    def _on_prune_confirmed(self, confirmed: bool, keep: int, include_pinned: bool) -> None:
        if not confirmed:
            self._set_status("Prune cancelled.")
            return
        deleted = self.backup_manager.prune_backups(keep=keep, include_pinned=include_pinned)
        self._refresh_list()
        self._set_status(f"Pruned {deleted} backup(s).")

    def action_back(self) -> None:
        self.app.pop_screen()