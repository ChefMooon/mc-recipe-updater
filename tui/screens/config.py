"""Configuration and settings screen."""

import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any
from textual.screen import Screen, ModalScreen
from textual.containers import Container, Horizontal, Vertical
from textual.widgets import Static, Input
from textual.binding import Binding
from config import (
    BUNDLED_MAPPING_FILE,
    CONFIG_DIR,
    CONFIG_FILE,
    DEFAULT_MAPPING_FILE,
    GLOBAL_CONFIG_FILE,
    REPORTS_DIR,
    SUITES_FILE,
    ConfigManager,
    GlobalConfig,
)
from backup import BACKUPS_DIR, BACKUPS_REGISTRY


class PathsPanel(Container):
    """Panel showing config path health."""

    DEFAULT_CSS = """
    PathsPanel {
        width: 1fr;
        height: 1fr;
        border: solid $primary;
        border-title-color: $text;
        border-title-style: bold;
        padding: 1 2;
    }

    PathsPanel #paths-content {
        width: 1fr;
        height: 1fr;
        overflow-y: auto;
    }
    """

    def __init__(self):
        super().__init__(id="config-paths")
        self.can_focus = True
        self.border_title = "[1] Paths"
        self._content = Static("", id="paths-content")

    def compose(self):
        yield self._content

    def refresh_paths(self) -> None:
        paths = [
            ("Config dir", CONFIG_DIR),
            ("Profiles", CONFIG_FILE),
            ("Suites", SUITES_FILE),
            ("Mapping presets", DEFAULT_MAPPING_FILE),
            ("Reports dir", REPORTS_DIR),
            ("Global config", GLOBAL_CONFIG_FILE),
            ("Backups dir", BACKUPS_DIR),
            ("Backups registry", BACKUPS_REGISTRY),
        ]
        lines = []
        for label, path in paths:
            status = "[green]OK[/green]" if path.exists() else "[red]MISSING[/red]"
            lines.append(f"[bold dim]{label + ':':<18}[/bold dim] {path}  {status}")
        self._content.update("\n".join(lines))


class ConfigActionsPanel(Container):
    """Panel showing current settings and available actions."""

    DEFAULT_CSS = """
    ConfigActionsPanel {
        width: 1fr;
        height: 1fr;
        border: solid $primary;
        border-title-color: $text;
        border-title-style: bold;
        padding: 1 2;
    }
    """

    def __init__(self):
        super().__init__(id="config-actions")
        self.can_focus = True
        self.border_title = "[2] Actions"
        self._content = Static("", id="actions-content")

    def compose(self):
        yield self._content

    def refresh_settings(self) -> None:
        config = GlobalConfig().load()
        backup = config.get("backup", {})
        lines = [
            "[bold]Current settings[/bold]",
            f"[bold dim]{'backup.enabled:':<20}[/bold dim] {backup.get('enabled', True)}",
            f"[bold dim]{'backup.max_backups:':<20}[/bold dim] {backup.get('max_backups', 10)}",
            "",
            "[bold]Quick actions[/bold]",
            "o  Open config directory",
            "v  View mapping presets",
            "r  Reset mapping presets from bundled defaults",
            "R  Reset all ~/.mcru data",
        ]
        self._content.update("\n".join(lines))


class ConfigActionBar(Container):
    """Config screen key bar."""

    DEFAULT_CSS = """
    ConfigActionBar {
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
        super().__init__(id="config-action-bar")
        self.can_focus = True
        self.border_title = "[3] Keys"

    def compose(self):
        yield Static(
            "[bold green]o[/bold green]: Open dir  [bold cyan]v[/bold cyan]: View presets  "
            "[bold yellow]r[/bold yellow]: Reset presets  [bold red]R[/bold red]: Reset all  "
            "[bold dim]Esc[/bold dim]: Back"
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


class ResetAllModal(ModalScreen[bool]):
    """Typed confirmation for full config reset."""

    BINDINGS = [Binding("escape", "cancel", "Cancel", show=False)]

    DEFAULT_CSS = """
    ResetAllModal {
        align: center middle;
    }

    ResetAllModal #reset-container {
        width: 72;
        height: auto;
        border: solid $error;
        border-title-color: $error;
        border-title-style: bold;
        background: $surface;
        padding: 1 2;
    }

    ResetAllModal #form-error {
        color: $error;
    }
    """

    def compose(self):
        with Container(id="reset-container") as container:
            container.border_title = "Reset All"
            yield Static("This deletes profiles, suites, reports, presets, backups, and global settings under ~/.mcru.")
            yield Static("Type RESET to confirm.")
            yield Input(placeholder="RESET", id="confirm-text")
            yield Static("", id="form-error")

    def on_mount(self) -> None:
        self.query_one("#confirm-text", Input).focus()

    def key_enter(self) -> None:
        if self.query_one("#confirm-text", Input).value.strip() == "RESET":
            self.dismiss(True)
        else:
            self.query_one("#form-error", Static).update("[bold red]Confirmation text does not match.[/bold red]")

    def action_cancel(self) -> None:
        self.dismiss(False)


class ConfigScreen(Screen):
    """Configuration and settings screen."""

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
        Binding("o", "open_config_dir", "Open", show=False),
        Binding("v", "view_presets", "View", show=False),
        Binding("r", "reset_presets", "Reset Presets", show=False),
        Binding("shift+r", "reset_all", "Reset All", show=False),
    ]

    DEFAULT_CSS = """
    ConfigScreen {
        background: $surface;
    }

    ConfigScreen #config-layout {
        width: 1fr;
        height: 1fr;
    }

    ConfigScreen #panels-row {
        width: 1fr;
        height: 1fr;
    }

    ConfigScreen #status-bar {
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
        self._paths_panel: PathsPanel | None = None
        self._actions_panel: ConfigActionsPanel | None = None
        self._status_bar: Static | None = None

    def compose(self):
        with Vertical(id="config-layout"):
            with Horizontal(id="panels-row"):
                self._paths_panel = PathsPanel()
                yield self._paths_panel
                self._actions_panel = ConfigActionsPanel()
                yield self._actions_panel
            yield ConfigActionBar()
        self._status_bar = Static("", id="status-bar")
        yield self._status_bar

    def on_mount(self) -> None:
        self._refresh()

    def _refresh(self) -> None:
        if self._paths_panel:
            self._paths_panel.refresh_paths()
        if self._actions_panel:
            self._actions_panel.refresh_settings()

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
        if not self._focus_widget("#config-paths", Container):
            self._set_status("[dim]Paths section not focusable right now[/dim]")

    def action_focus_section_2(self) -> None:
        if not self._focus_widget("#config-actions", Container):
            self._set_status("[dim]Settings/actions section not focusable right now[/dim]")

    def action_focus_section_3(self) -> None:
        if not self._focus_widget("#config-action-bar", Container):
            self._set_status("[dim]Actions section not focusable right now[/dim]")

    def action_open_config_dir(self) -> None:
        if not CONFIG_DIR.exists():
            self._set_status("Config directory does not exist yet.")
            return
        try:
            if sys.platform == "win32":
                subprocess.Popen(["explorer", str(CONFIG_DIR)])
            elif sys.platform == "darwin":
                subprocess.Popen(["open", str(CONFIG_DIR)])
            else:
                subprocess.Popen(["xdg-open", str(CONFIG_DIR)])
            self._set_status(f"Opened {CONFIG_DIR}.")
        except OSError as err:
            self._set_status(f"Open failed: {err}")

    def action_view_presets(self) -> None:
        try:
            data = json.loads(DEFAULT_MAPPING_FILE.read_text(encoding="utf-8"))
            content = json.dumps(data, indent=2)
        except json.JSONDecodeError as err:
            content = f"Mapping presets file is invalid JSON:\n\n{err}"
        except OSError as err:
            content = f"Could not read mapping presets:\n\n{err}"
        self.app.push_screen(TextViewerModal("Mapping Presets", content))

    def action_reset_presets(self) -> None:
        self.app.push_screen(
            ConfirmModal("Reset Presets", f"Replace {DEFAULT_MAPPING_FILE} with bundled defaults?"),
            callback=self._on_reset_presets_confirmed,
        )

    def _on_reset_presets_confirmed(self, confirmed: bool) -> None:
        if not confirmed:
            self._set_status("Reset presets cancelled.")
            return
        try:
            if DEFAULT_MAPPING_FILE.exists():
                DEFAULT_MAPPING_FILE.unlink()
            if BUNDLED_MAPPING_FILE.exists():
                shutil.copy2(BUNDLED_MAPPING_FILE, DEFAULT_MAPPING_FILE)
                self._set_status("Mapping presets reset.")
            else:
                self._set_status(f"Bundled presets missing: {BUNDLED_MAPPING_FILE}")
        except OSError as err:
            self._set_status(f"Reset presets failed: {err}")
        self._refresh()

    def action_reset_all(self) -> None:
        self.app.push_screen(ResetAllModal(), callback=self._on_reset_all_confirmed)

    def _on_reset_all_confirmed(self, confirmed: bool) -> None:
        if not confirmed:
            self._set_status("Reset all cancelled.")
            return
        try:
            if CONFIG_DIR.exists():
                shutil.rmtree(CONFIG_DIR)
            CONFIG_DIR.mkdir(parents=True, exist_ok=True)
            CONFIG_FILE.write_text(json.dumps({"profiles": []}, indent=2), encoding="utf-8")
            SUITES_FILE.write_text(json.dumps({"suites": []}, indent=2), encoding="utf-8")
            if BUNDLED_MAPPING_FILE.exists():
                shutil.copy2(BUNDLED_MAPPING_FILE, DEFAULT_MAPPING_FILE)
            GlobalConfig()
            self.config_manager = ConfigManager()
            if hasattr(self.app, "config_manager"):
                self.app.config_manager = self.config_manager
            self._set_status("All mcru configuration reset.")
        except OSError as err:
            self._set_status(f"Reset all failed: {err}")
        self._refresh()

    def action_back(self) -> None:
        self.app.pop_screen()