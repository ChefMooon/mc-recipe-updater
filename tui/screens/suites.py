"""
Suite management screen.

Lazygit-inspired panel layout with suite CRUD and ordered profile management.
"""

from textual.screen import Screen, ModalScreen
from textual.containers import Container, Horizontal, Vertical
from textual.widgets import Static, ListView, ListItem, Label, Input
from textual.binding import Binding
from config import ConfigManager


class SuiteFormModal(ModalScreen[dict | None]):
    """Modal form for creating or editing a suite."""

    BINDINGS = [Binding("escape", "cancel", "Cancel", show=False)]

    DEFAULT_CSS = """
    SuiteFormModal {
        align: center middle;
    }

    SuiteFormModal #suite-form-container {
        width: 80;
        height: auto;
        border: solid $primary;
        border-title-color: $text;
        border-title-style: bold;
        background: $surface;
        padding: 1 2;
    }

    SuiteFormModal .form-label {
        width: 1fr;
        height: 1;
        margin: 1 0 0 0;
        color: $text;
    }

    SuiteFormModal .form-label-first {
        width: 1fr;
        height: 1;
        color: $text;
    }

    SuiteFormModal .form-input {
        width: 1fr;
        height: 3;
    }

    SuiteFormModal #form-error {
        width: 1fr;
        height: 1;
        color: $error;
    }

    SuiteFormModal #form-actions {
        width: 1fr;
        height: 1;
        margin: 1 0 0 0;
    }
    """

    def __init__(self, suite: dict | None = None):
        super().__init__()
        self._suite = suite

    def compose(self):
        with Container(id="suite-form-container") as form:
            form.border_title = "Edit Suite" if self._suite else "Add Suite"
            yield Static("[bold]Name[/bold] [dim](required)[/dim]", classes="form-label-first")
            yield Input(placeholder="full-sync", id="input-name", classes="form-input")
            yield Static("[bold]Description[/bold] [dim](optional)[/dim]", classes="form-label")
            yield Input(placeholder="Profiles to run together", id="input-desc", classes="form-input")
            yield Static("", id="form-error")
            yield Static(
                "[bold green]Enter[/bold green]: Save  [bold dim]Esc[/bold dim]: Cancel",
                id="form-actions",
            )

    def on_mount(self) -> None:
        if self._suite:
            self.query_one("#input-name", Input).value = self._suite.get("name", "")
            self.query_one("#input-desc", Input).value = self._suite.get("description", "")
        self.query_one("#input-name", Input).focus()

    def key_enter(self) -> None:
        name = self.query_one("#input-name", Input).value.strip()
        description = self.query_one("#input-desc", Input).value.strip()
        error = self.query_one("#form-error", Static)
        if not name:
            error.update("[bold red]Name is required[/bold red]")
            self.query_one("#input-name", Input).focus()
            return
        self.dismiss({
            "name": name,
            "description": description,
            "original_name": self._suite.get("name") if self._suite else None,
        })

    def action_cancel(self) -> None:
        self.dismiss(None)


class ConfirmModal(ModalScreen[bool]):
    """Small y/n confirmation modal."""

    BINDINGS = [Binding("escape", "cancel", "Cancel", show=False)]

    DEFAULT_CSS = """
    ConfirmModal {
        align: center middle;
    }

    ConfirmModal #confirm-container {
        width: 60;
        height: auto;
        border: solid $error;
        border-title-color: $error;
        border-title-style: bold;
        background: $surface;
        padding: 1 2;
    }

    ConfirmModal #confirm-title {
        width: 1fr;
        height: 1;
        text-style: bold;
    }

    ConfirmModal #confirm-message {
        width: 1fr;
        height: auto;
        margin: 1 0 0 0;
        color: $text-muted;
    }

    ConfirmModal #confirm-actions {
        width: 1fr;
        height: 1;
        margin: 1 0 0 0;
    }
    """

    def __init__(self, title: str, message: str):
        super().__init__()
        self._title = title
        self._message = message

    def compose(self):
        with Container(id="confirm-container") as container:
            container.border_title = self._title
            yield Static(self._title, id="confirm-title")
            yield Static(self._message, id="confirm-message")
            yield Static(
                "[bold green]y[/bold green] / [bold green]Enter[/bold green]: Confirm  "
                "[bold dim]n[/bold dim] / [bold dim]Esc[/bold dim]: Cancel",
                id="confirm-actions",
            )

    def key_y(self) -> None:
        self.dismiss(True)

    def key_enter(self) -> None:
        self.dismiss(True)

    def key_n(self) -> None:
        self.dismiss(False)

    def action_cancel(self) -> None:
        self.dismiss(False)


class SuiteListItem(ListItem):
    """A single suite entry."""

    def __init__(self, suite_name: str, **kwargs):
        super().__init__(**kwargs)
        self.suite_name = suite_name

    def compose(self):
        yield Label(self.suite_name)


class SuiteList(Container):
    """Bordered suite list panel."""

    can_focus = True

    DEFAULT_CSS = """
    SuiteList {
        width: 1fr;
        height: 1fr;
        border: solid $primary;
        border-title-color: $text;
        border-title-style: bold;
        padding: 0;
    }

    SuiteList ListView {
        width: 1fr;
        height: 1fr;
        background: $surface;
    }

    SuiteList ListView > ListItem {
        padding: 0 1;
        height: 1;
        background: $surface;
    }

    SuiteList ListView > ListItem.--highlight {
        background: $primary 30%;
    }

    SuiteList ListView:focus > ListItem.--highlight {
        background: $primary 50%;
    }

    SuiteList ListView > ListItem.--highlight Label {
        color: $text;
        text-style: bold;
    }
    """

    def __init__(self, suites: list[dict]):
        super().__init__()
        self.border_title = "Suites"
        self.suites = suites

    def compose(self):
        if self.suites:
            yield ListView(*[SuiteListItem(s["name"]) for s in self.suites], id="suite-listview")
        else:
            yield Static(" No suites found\n\n Press [bold]a[/bold] to add one", id="empty-state")


class SuiteDetail(Container):
    """Bordered detail panel for selected suite."""

    DEFAULT_CSS = """
    SuiteDetail {
        width: 1fr;
        height: 1fr;
        border: solid $primary;
        border-title-color: $text;
        border-title-style: bold;
        padding: 1 2;
    }

    SuiteDetail #detail-content {
        width: 1fr;
        height: 1fr;
    }
    """

    def __init__(self, config_manager: ConfigManager):
        super().__init__()
        self.config_manager = config_manager
        self.border_title = "Details"
        self._content = Static("Select a suite to view details", id="detail-content")

    def compose(self):
        yield self._content

    def update_detail(self, suite: dict | None) -> None:
        if suite is None:
            self._content.update("[dim]Select a suite to view details[/dim]")
            return

        profiles = suite.get("profiles", [])
        lines = [
            f"[bold dim]{'Name:':<14}[/bold dim] [bold]{suite.get('name', '')}[/bold]",
            f"[bold dim]{'Description:':<14}[/bold dim] {suite.get('description') or '[dim]none[/dim]'}",
            f"[bold dim]{'Profiles:':<14}[/bold dim] {len(profiles)}",
            f"[bold dim]{'Created:':<14}[/bold dim] {suite.get('created_at') or '[dim]unknown[/dim]'}",
            "",
            "[bold]Ordered profiles[/bold]",
        ]
        if not profiles:
            lines.append("[dim](no profiles)[/dim]")
        else:
            for index, profile_name in enumerate(profiles, 1):
                missing = self.config_manager.get_profile(profile_name) is None
                suffix = "  [red]missing[/red]" if missing else ""
                lines.append(f"{index:>2}. {profile_name}{suffix}")
        self._content.update("\n".join(lines))


class SuiteActionBar(Container):
    """Action bar for suite list screen."""

    DEFAULT_CSS = """
    SuiteActionBar {
        width: 1fr;
        height: 3;
        border: solid $primary;
        border-title-color: $text;
        border-title-style: bold;
        padding: 0 1;
        align: left middle;
    }

    SuiteActionBar #action-keys {
        width: 1fr;
        height: 1;
    }
    """

    def __init__(self):
        super().__init__()
        self.border_title = "Actions"

    def compose(self):
        yield Static(
            "  ".join([
                "[bold green]a[/bold green]: Add",
                "[bold yellow]e[/bold yellow]: Edit",
                "[bold red]d[/bold red]: Delete",
                "[bold cyan]m[/bold cyan]: Manage profiles",
                "[bold dim]Esc[/bold dim]: Back",
            ]),
            id="action-keys",
        )


class ManageProfileItem(ListItem):
    """Profile item used in suite profile management."""

    def __init__(self, profile_name: str, missing: bool = False, **kwargs):
        super().__init__(**kwargs)
        self.profile_name = profile_name
        self.missing = missing

    def compose(self):
        label = f"{self.profile_name}  missing" if self.missing else self.profile_name
        yield Label(label)


class InSuitePanel(Container):
    """Panel listing profiles currently in a suite."""

    def __init__(self, config_manager: ConfigManager, profile_names: list[str]):
        super().__init__(classes="manage-panel")
        self.config_manager = config_manager
        self.profile_names = profile_names
        self.listview: ListView | None = None
        self.border_title = "[1] In Suite"

    def compose(self):
        if self.profile_names:
            self.listview = ListView(
                *[
                    ManageProfileItem(name, self.config_manager.get_profile(name) is None)
                    for name in self.profile_names
                ]
            )
            yield self.listview
        else:
            self.listview = None
            yield Static(" (no profiles)")


class AvailablePanel(Container):
    """Panel listing profiles not currently in a suite."""

    def __init__(self, profile_names: list[str]):
        super().__init__(classes="manage-panel")
        self.profile_names = profile_names
        self.listview: ListView | None = None
        self.border_title = "[2] Available"

    def compose(self):
        if self.profile_names:
            self.listview = ListView(*[ManageProfileItem(name) for name in self.profile_names])
            yield self.listview
        else:
            self.listview = None
            yield Static(" (no available profiles)")


class ManageProfilesScreen(Screen):
    """Manage ordered profiles inside a suite."""

    ACTIONS_TEXT = (
        "[bold green]a[/bold green]: Add  [bold red]d[/bold red]: Remove  "
        "[bold cyan]\\[[/bold cyan]/[bold cyan]\\][/bold cyan]: Reorder  "
        "[bold cyan]Tab[/bold cyan]: Switch panel  [bold dim]Esc[/bold dim]: Back"
    )

    BINDINGS = [
        Binding("escape", "back", "Back", show=False),
        Binding("q", "back", "Back", show=False),
        Binding("ctrl+c", "force_quit", "Quit", show=False),
        Binding("ctrl+1", "focus_section_1", "Section 1", show=False),
        Binding("ctrl+2", "focus_section_2", "Section 2", show=False),
        Binding("ctrl+3", "focus_section_3", "Section 3", show=False),
        Binding("alt+1", "focus_section_1", "Section 1", show=False),
        Binding("alt+2", "focus_section_2", "Section 2", show=False),
        Binding("alt+3", "focus_section_3", "Section 3", show=False),
        Binding("f1", "focus_section_1", "Section 1", show=False),
        Binding("f2", "focus_section_2", "Section 2", show=False),
        Binding("f3", "focus_section_3", "Section 3", show=False),
        Binding("tab", "toggle_panel", "Switch", show=False),
        Binding("a", "add_profile", "Add", show=False),
        Binding("d", "remove_profile", "Remove", show=False),
        Binding("[", "move_up", "Move Up", show=False),
        Binding("]", "move_down", "Move Down", show=False),
    ]

    DEFAULT_CSS = """
    ManageProfilesScreen {
        background: $surface;
    }

    ManageProfilesScreen #manage-layout {
        width: 1fr;
        height: 1fr;
    }

    ManageProfilesScreen #manage-row {
        width: 1fr;
        height: 1fr;
    }

    ManageProfilesScreen .manage-panel {
        width: 1fr;
        height: 1fr;
        border: solid $primary;
        border-title-color: $text;
        border-title-style: bold;
        padding: 0;
    }

    ManageProfilesScreen .manage-panel-active {
        border: heavy $primary;
    }

    ManageProfilesScreen ListView {
        width: 1fr;
        height: 1fr;
        background: $surface;
    }

    ManageProfilesScreen ListView > ListItem {
        padding: 0 1;
        height: 1;
        background: $surface;
    }

    ManageProfilesScreen ListView > ListItem.--highlight {
        background: $primary 30%;
    }

    ManageProfilesScreen ListView:focus > ListItem.--highlight {
        background: $primary 50%;
    }

    ManageProfilesScreen #manage-actions {
        width: 1fr;
        height: 3;
        border: solid $primary;
        border-title-color: $text;
        border-title-style: bold;
        padding: 0 1;
        align: left middle;
    }

    ManageProfilesScreen #status-bar {
        width: 1fr;
        height: 1;
        background: $surface;
        color: $text-muted;
        padding: 0 1;
        dock: bottom;
    }
    """

    def __init__(self, config_manager: ConfigManager, suite_name: str):
        super().__init__()
        self.config_manager = config_manager
        self.suite_name = suite_name
        self._active_panel = "in"
        self._status_bar: Static | None = None
        self._in_panel: InSuitePanel | None = None
        self._available_panel: AvailablePanel | None = None

    def compose(self):
        with Vertical(id="manage-layout"):
            with Horizontal(id="manage-row"):
                self._in_panel = self._build_in_panel()
                yield self._in_panel
                self._available_panel = self._build_available_panel()
                yield self._available_panel
            with Container(id="manage-actions") as actions:
                actions.border_title = "[3] Actions"
                yield Static(self.ACTIONS_TEXT)
        self._status_bar = Static("", id="status-bar")
        yield self._status_bar

    def on_mount(self) -> None:
        self._focus_active_list()

    def _build_in_panel(self) -> Container:
        suite = self.config_manager.get_suite(self.suite_name) or {"profiles": []}
        return InSuitePanel(self.config_manager, suite.get("profiles", []))

    def _build_available_panel(self) -> Container:
        suite = self.config_manager.get_suite(self.suite_name) or {"profiles": []}
        in_suite = set(suite.get("profiles", []))
        available = [p["name"] for p in self.config_manager.list_profiles() if p["name"] not in in_suite]
        return AvailablePanel(available)

    def _refresh(self) -> None:
        if self._in_panel:
            self._in_panel.remove()
            self._in_panel = None
        if self._available_panel:
            self._available_panel.remove()
            self._available_panel = None
        row = self.query_one("#manage-row", Horizontal)
        self._in_panel = self._build_in_panel()
        self._available_panel = self._build_available_panel()
        row.mount(self._in_panel)
        row.mount(self._available_panel)
        self._sync_active_panel_classes()
        self._focus_active_list()

    def _sync_active_panel_classes(self) -> None:
        panels: list[tuple[Container, str]] = []
        if self._in_panel is not None:
            panels.append((self._in_panel, "in"))
        if self._available_panel is not None:
            panels.append((self._available_panel, "available"))
        for panel, active_name in panels:
            panel.remove_class("manage-panel-active")
            if self._active_panel == active_name:
                panel.add_class("manage-panel-active")

    def _focus_active_list(self) -> None:
        self._sync_active_panel_classes()
        listview = self._current_listview()
        if listview is None:
            return
        try:
            listview.focus()
        except Exception:
            pass

    def _current_listview(self) -> ListView | None:
        if self._active_panel == "in":
            return self._in_panel.listview if self._in_panel else None
        return self._available_panel.listview if self._available_panel else None

    def _selected_from(self, listview: ListView | None) -> str | None:
        if listview is None:
            return None
        item = listview.highlighted_child
        if isinstance(item, ManageProfileItem):
            return item.profile_name
        return None

    def _set_status(self, message: str) -> None:
        if self._status_bar:
            self._status_bar.update(message)

    def action_toggle_panel(self) -> None:
        self._active_panel = "available" if self._active_panel == "in" else "in"
        self._focus_active_list()

    def action_add_profile(self) -> None:
        profile_name = self._selected_from(self._available_panel.listview if self._available_panel else None)
        if not profile_name:
            self._set_status("No available profile selected.")
            return
        try:
            self.config_manager.add_profile_to_suite(self.suite_name, profile_name)
            self._set_status(f"Added profile '{profile_name}'.")
            self._active_panel = "in"
            self._refresh()
        except ValueError as err:
            self._set_status(str(err))

    def action_remove_profile(self) -> None:
        profile_name = self._selected_from(self._in_panel.listview if self._in_panel else None)
        if not profile_name:
            self._set_status("No suite profile selected.")
            return
        try:
            self.config_manager.remove_profile_from_suite(self.suite_name, profile_name)
            self._set_status(f"Removed profile '{profile_name}'.")
            self._refresh()
        except ValueError as err:
            self._set_status(str(err))

    def action_move_up(self) -> None:
        self._move_selected(-1)

    def action_move_down(self) -> None:
        self._move_selected(1)

    def _move_selected(self, delta: int) -> None:
        profile_name = self._selected_from(self._in_panel.listview if self._in_panel else None)
        if not profile_name:
            self._set_status("No suite profile selected.")
            return
        suite = self.config_manager.get_suite(self.suite_name)
        if not suite:
            self._set_status("Suite no longer exists.")
            return
        profiles = suite.get("profiles", [])
        if len(profiles) <= 1:
            self._set_status("Only one profile in suite; reorder has no effect.")
            return
        current = profiles.index(profile_name)
        target = max(0, min(len(profiles) - 1, current + delta))
        if target == current:
            self._set_status("Profile is already at the edge of the order.")
            return
        self.config_manager.reorder_profile_in_suite(self.suite_name, profile_name, target + 1)
        self._set_status(f"Moved '{profile_name}' to position {target + 1}.")
        self._refresh()

    def action_force_quit(self) -> None:
        """Immediately exit the app on Ctrl+C."""
        self.app.exit()

    def _focus_widget(self, selector: str, widget_type: type) -> bool:
        try:
            self.query_one(selector, widget_type).focus()
            return True
        except Exception:
            return False

    def action_focus_section_1(self) -> None:
        self._active_panel = "in"
        self._sync_active_panel_classes()
        listview = self._in_panel.listview if self._in_panel else None
        if listview is None:
            self._set_status("In-suite list is not focusable right now.")
            return
        try:
            listview.focus()
        except Exception:
            self._set_status("In-suite list is not focusable right now.")

    def action_focus_section_2(self) -> None:
        self._active_panel = "available"
        self._sync_active_panel_classes()
        listview = self._available_panel.listview if self._available_panel else None
        if listview is None:
            self._set_status("Available list is not focusable right now.")
            return
        try:
            listview.focus()
        except Exception:
            self._set_status("Available list is not focusable right now.")

    def action_focus_section_3(self) -> None:
        self._set_status("Actions section is not focusable.")

    def action_back(self) -> None:
        self.app.pop_screen()


class SuitesScreen(Screen):
    """Suite management screen with lazygit-style panel layout."""

    BINDINGS = [
        Binding("escape", "back", "Back", show=False),
        Binding("q", "back", "Back", show=False),
        Binding("ctrl+c", "force_quit", "Quit", show=False),
        Binding("a", "add_suite", "Add", show=False),
        Binding("e", "edit_suite", "Edit", show=False),
        Binding("d", "delete_suite", "Delete", show=False),
        Binding("m", "manage_profiles", "Manage", show=False),
    ]

    DEFAULT_CSS = """
    SuitesScreen {
        background: $surface;
    }

    SuitesScreen #suites-layout {
        width: 1fr;
        height: 1fr;
    }

    SuitesScreen #panels-row {
        width: 1fr;
        height: 1fr;
    }

    SuitesScreen #status-bar {
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
        self._suites: list[dict] = []
        self._suite_list: SuiteList | None = None
        self._detail_panel: SuiteDetail | None = None
        self._status_bar: Static | None = None
        self._pending_delete_name: str | None = None

    def compose(self):
        self._suites = self.config_manager.list_suites()
        with Vertical(id="suites-layout"):
            with Horizontal(id="panels-row"):
                self._suite_list = SuiteList(self._suites)
                yield self._suite_list
                self._detail_panel = SuiteDetail(self.config_manager)
                self._detail_panel.id = "suite-detail-panel"
                yield self._detail_panel
            action_bar = SuiteActionBar()
            action_bar.id = "suite-actions-panel"
            yield action_bar
        self._status_bar = Static("", id="status-bar")
        yield self._status_bar

    def on_mount(self) -> None:
        if self._suites:
            self._show_suite(0)
        # Ensure focus is set after first render; avoids requiring a mouse click
        # before keybindings become responsive on some terminals/platforms.
        self.call_after_refresh(self._ensure_initial_focus)

    def on_screen_resume(self) -> None:
        self._refresh_list()

    def _ensure_initial_focus(self) -> None:
        if self._focus_widget("#suite-listview", ListView):
            return
        self._focus_suite_panel()

    def _focus_suite_panel(self) -> bool:
        if self._suite_list is None:
            return False
        try:
            self._suite_list.focus()
            return True
        except Exception:
            return False

    def on_list_view_highlighted(self, event: ListView.Highlighted) -> None:
        if event.item is not None and isinstance(event.item, SuiteListItem):
            suite = self.config_manager.get_suite(event.item.suite_name)
            if self._detail_panel:
                self._detail_panel.update_detail(suite)

    def _show_suite(self, index: int) -> None:
        if 0 <= index < len(self._suites):
            suite = self.config_manager.get_suite(self._suites[index]["name"])
            if self._detail_panel:
                self._detail_panel.update_detail(suite)

    def _get_selected_suite_name(self) -> str | None:
        try:
            listview = self.query_one("#suite-listview", ListView)
        except Exception:
            return None
        if listview.highlighted_child and isinstance(listview.highlighted_child, SuiteListItem):
            return listview.highlighted_child.suite_name
        return None

    def _set_status(self, message: str) -> None:
        if self._status_bar:
            self._status_bar.update(message)

    def _refresh_list(self) -> None:
        self._suites = self.config_manager.list_suites()
        if self._suite_list:
            self._suite_list.remove()
        panels_row = self.query_one("#panels-row", Horizontal)
        new_list = SuiteList(self._suites)
        panels_row.mount(new_list, before=self._detail_panel)
        self._suite_list = new_list
        if self._suites:
            self._show_suite(0)
        elif self._detail_panel:
            self._detail_panel.update_detail(None)
        self.call_after_refresh(self._ensure_initial_focus)

    def action_add_suite(self) -> None:
        self.app.push_screen(SuiteFormModal(), callback=self._on_add_suite)

    def _on_add_suite(self, result: dict | None) -> None:
        if result is None:
            self._set_status("Add cancelled.")
            return
        if self.config_manager.get_suite(result["name"]):
            self._set_status(f"Suite '{result['name']}' already exists.")
            return
        self.config_manager.save_suite(result["name"], description=result["description"])
        self._refresh_list()
        self._set_status(f"Suite '{result['name']}' added.")

    def action_edit_suite(self) -> None:
        suite_name = self._get_selected_suite_name()
        if not suite_name:
            self._set_status("No suite selected.")
            return
        suite = self.config_manager.get_suite(suite_name)
        self.app.push_screen(SuiteFormModal(suite), callback=self._on_edit_suite)

    def _on_edit_suite(self, result: dict | None) -> None:
        if result is None:
            self._set_status("Edit cancelled.")
            return
        original_name = result.get("original_name")
        new_name = result["name"]
        if original_name != new_name and self.config_manager.get_suite(new_name):
            self._set_status(f"Suite '{new_name}' already exists.")
            return
        original = self.config_manager.get_suite(original_name) if original_name else None
        profiles = original.get("profiles", []) if original else []
        if original_name and original_name != new_name:
            self.config_manager.delete_suite(original_name)
        self.config_manager.save_suite(new_name, description=result["description"], profiles=profiles)
        self._refresh_list()
        self._set_status(f"Suite '{new_name}' saved.")

    def action_delete_suite(self) -> None:
        suite_name = self._get_selected_suite_name()
        if not suite_name:
            self._set_status("No suite selected.")
            return
        self._pending_delete_name = suite_name
        self.app.push_screen(
            ConfirmModal("Delete Suite", f"Suite '{suite_name}' will be permanently deleted. Profiles are not deleted."),
            callback=self._on_delete_confirmed,
        )

    def _on_delete_confirmed(self, confirmed: bool) -> None:
        suite_name = self._pending_delete_name
        self._pending_delete_name = None
        if not confirmed or not suite_name:
            self._set_status("Delete cancelled.")
            return
        try:
            self.config_manager.delete_suite(suite_name)
            self._refresh_list()
            self._set_status(f"Suite '{suite_name}' deleted.")
        except ValueError as err:
            self._set_status(str(err))

    def action_manage_profiles(self) -> None:
        suite_name = self._get_selected_suite_name()
        if not suite_name:
            self._set_status("No suite selected.")
            return
        self.app.push_screen(ManageProfilesScreen(self.config_manager, suite_name))

    def action_force_quit(self) -> None:
        """Immediately exit the app on Ctrl+C."""
        self.app.exit()

    def _focus_widget(self, selector: str, widget_type: type) -> bool:
        try:
            self.query_one(selector, widget_type).focus()
            return True
        except Exception:
            return False

    def action_back(self) -> None:
        self.app.pop_screen()
