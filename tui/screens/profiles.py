"""
Profile management screen.

Lazygit-inspired panel layout with profile list, detail view,
and clearly visible keybindings.
"""

from pathlib import Path
from textual.screen import Screen, ModalScreen
from textual.containers import Container, Horizontal, Vertical
from textual.widgets import Static, ListView, ListItem, Label, Input, Checkbox, Select
from textual.binding import Binding
from config import ConfigManager
from registry import list_parsers
from typing import Any


# ── Helpers ──────────────────────────────────────

def _available_mapping_presets() -> list[str]:
    """Read mapping preset names from the mapping-presets.json file."""
    import json
    from config import DEFAULT_MAPPING_FILE
    try:
        data = json.loads(DEFAULT_MAPPING_FILE.read_text())
        return sorted(data.get("presets", {}).keys())
    except Exception:
        return []


# ── Add Profile Modal ────────────────────────────

class AddProfileModal(ModalScreen[dict | None]):
    """Modal form for creating a new profile."""

    BINDINGS = [
        Binding("escape", "cancel", "Cancel", show=False),
    ]

    DEFAULT_CSS = """
    AddProfileModal {
        align: center middle;
    }

    AddProfileModal #add-form-container {
        width: 100;
        height: auto;
        max-height: 90%;
        border: solid $primary;
        border-title-color: $text;
        border-title-style: bold;
        background: $surface;
        padding: 1 2;
    }

    AddProfileModal .form-label {
        width: 1fr;
        height: 1;
        margin: 1 0 0 0;
        color: $text;
    }

    AddProfileModal .form-label-first {
        width: 1fr;
        height: 1;
        color: $text;
    }

    AddProfileModal .form-input {
        width: 1fr;
        height: 3;
    }

    AddProfileModal .form-select {
        width: 1fr;
        height: 3;
    }

    AddProfileModal #parsers-row {
        width: 1fr;
        height: auto;
        layout: horizontal;
    }

    AddProfileModal .parser-checkbox {
        width: auto;
        height: auto;
        margin: 0 2 0 0;
    }

    AddProfileModal #form-actions {
        width: 1fr;
        height: 1;
        margin: 1 0 0 0;
    }

    AddProfileModal #form-error {
        width: 1fr;
        height: 1;
        color: $error;
    }
    """

    def __init__(self, profile: dict | None = None):
        super().__init__()
        self._edit_profile = profile
        self._parser_names = list_parsers()
        self._preset_names = _available_mapping_presets()

    def compose(self):
        with Container(id="add-form-container") as form:
            form.border_title = "Edit Profile" if self._edit_profile else "Add Profile"

            yield Static("[bold]Name[/bold] [dim](required)[/dim]", classes="form-label-first")
            yield Input(placeholder="my-project", id="input-name", classes="form-input")

            yield Static("[bold]Source path[/bold] [dim](required)[/dim]", classes="form-label")
            yield Input(placeholder="/path/to/source", id="input-source", classes="form-input")

            yield Static("[bold]Target path[/bold] [dim](required)[/dim]", classes="form-label")
            yield Input(placeholder="/path/to/target", id="input-target")

            yield Static("[bold]Description[/bold] [dim](optional)[/dim]", classes="form-label")
            yield Input(placeholder="Short description", id="input-desc")

            yield Static("[bold]Parsers[/bold]", classes="form-label")
            with Horizontal(id="parsers-row"):
                for parser_name in self._parser_names:
                    yield Checkbox(parser_name, id=f"parser-{parser_name}", classes="parser-checkbox")

            yield Static("[bold]Mapping preset[/bold] [dim](optional)[/dim]", classes="form-label")
            preset_options = [(name, name) for name in self._preset_names]
            yield Select(
                [("(none)", "")] + preset_options,
                value="",
                id="input-mapping",
                classes="form-select",
            )

            yield Checkbox("Enable target changelog", id="input-changelog", classes="parser-checkbox")

            yield Static("", id="form-error")
            yield Static(
                "[bold green]Enter[/bold green]: Save  [bold dim]Esc[/bold dim]: Cancel",
                id="form-actions",
            )

    def on_mount(self) -> None:
        if self._edit_profile:
            # Pre-populate all fields from the existing profile
            self.query_one("#input-name", Input).value = self._edit_profile["name"]
            self.query_one("#input-source", Input).value = self._edit_profile["source"]
            self.query_one("#input-target", Input).value = self._edit_profile["target"]
            self.query_one("#input-desc", Input).value = self._edit_profile.get("description", "")
            
            # Pre-select parsers
            profile_parsers = self._edit_profile.get("parsers", [])
            for parser_name in self._parser_names:
                cb = self.query_one(f"#parser-{parser_name}", Checkbox)
                cb.value = parser_name in profile_parsers
            
            # Pre-select mapping preset
            preset_value = self._edit_profile.get("mapping_preset", "")
            self.query_one("#input-mapping", Select).value = preset_value if preset_value else ""
            
            # Pre-set changelog checkbox
            self.query_one("#input-changelog", Checkbox).value = self._edit_profile.get("target_changelog", False)
            
            self.query_one("#input-name", Input).focus()
        else:
            # Add mode: focus on name field
            self.query_one("#input-name", Input).focus()

    def key_enter(self) -> None:
        """Validate and submit the form."""
        name = self.query_one("#input-name", Input).value.strip()

        source = self.query_one("#input-source", Input).value.strip()
        target = self.query_one("#input-target", Input).value.strip()
        desc = self.query_one("#input-desc", Input).value.strip()

        # Validation
        error_widget = self.query_one("#form-error", Static)
        if not name:
            error_widget.update("[bold red]Name is required[/bold red]")
            self.query_one("#input-name", Input).focus()
            return
        if not source:
            error_widget.update("[bold red]Source path is required[/bold red]")
            self.query_one("#input-source", Input).focus()
            return
        if not target:
            error_widget.update("[bold red]Target path is required[/bold red]")
            self.query_one("#input-target", Input).focus()
            return

        # Collect parsers
        selected_parsers = []
        for parser_name in self._parser_names:
            cb = self.query_one(f"#parser-{parser_name}", Checkbox)
            if cb.value:
                selected_parsers.append(parser_name)

        # Mapping preset
        mapping_select = self.query_one("#input-mapping", Select)
        mapping = mapping_select.value if mapping_select.value else None

        # Changelog
        changelog = self.query_one("#input-changelog", Checkbox).value

        self.dismiss({
            "name": name,
            "original_name": self._edit_profile["name"] if self._edit_profile else None,
            "source": source,
            "target": target,
            "description": desc,
            "parsers": selected_parsers,
            "mapping_preset": mapping,
            "target_changelog": changelog,
        })

    def action_cancel(self) -> None:
        self.dismiss(None)


# ── Delete Confirm Modal ────────────────────────

class DeleteConfirmModal(ModalScreen[bool]):
    """Confirmation modal for deleting a profile."""

    BINDINGS = [
        Binding("escape", "cancel", "Cancel", show=False),
    ]

    DEFAULT_CSS = """
    DeleteConfirmModal {
        align: center middle;
    }

    DeleteConfirmModal #confirm-container {
        width: 50;
        height: auto;
        border: solid $error;
        border-title-color: $error;
        border-title-style: bold;
        background: $surface;
        padding: 1 2;
    }

    DeleteConfirmModal #confirm-profile-name {
        width: 1fr;
        height: 1;
        text-style: bold;
    }

    DeleteConfirmModal #confirm-prompt {
        width: 1fr;
        height: 1;
        margin: 1 0 0 0;
        color: $text-muted;
    }

    DeleteConfirmModal #confirm-actions {
        width: 1fr;
        height: 1;
        margin: 1 0 0 0;
    }
    """

    def __init__(self, profile_name: str):
        super().__init__()
        self._profile_name = profile_name

    def compose(self):
        with Container(id="confirm-container") as container:
            container.border_title = "Delete Profile"
            yield Static(
                f"[bold red]{self._profile_name}[/bold red]",
                id="confirm-profile-name",
            )
            yield Static(
                "This profile will be permanently deleted.",
                id="confirm-prompt",
            )
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


# ── Profile List Widgets ─────────────────────────

class ProfileListItem(ListItem):
    """A single profile entry in the list."""

    def __init__(self, profile_name: str, **kwargs):
        super().__init__(**kwargs)
        self.profile_name = profile_name

    def compose(self):
        yield Label(self.profile_name)


class ProfileList(Container):
    """Bordered panel containing the profile list."""

    DEFAULT_CSS = """
    ProfileList {
        width: 1fr;
        height: 1fr;
        border: solid $primary;
        border-title-color: $text;
        border-title-style: bold;
        padding: 0;
    }

    ProfileList:focus {
        border: heavy $accent;
    }

    ProfileList ListView {
        width: 1fr;
        height: 1fr;
        background: $surface;
    }

    ProfileList ListView > ListItem {
        padding: 0 1;
        height: 1;
        background: $surface;
    }

    ProfileList ListView > ListItem.--highlight {
        background: $primary 30%;
    }

    ProfileList ListView:focus > ListItem.--highlight {
        background: $primary 50%;
    }

    ProfileList ListView > ListItem.--highlight Label {
        color: $text;
        text-style: bold;
    }
    """

    def __init__(self, profiles: list, mode_label: str = ""):
        super().__init__(id="profile-list")
        self.can_focus = True
        title = "[1] Profiles"
        if mode_label:
            title += f"  [dim]{mode_label}[/dim]"
        self.border_title = title
        self.profiles = profiles

    def compose(self):
        if self.profiles:
            items = [ProfileListItem(p["name"]) for p in self.profiles]
            yield ListView(*items, id="profile-listview")
        else:
            yield Static(
                " No profiles found\n\n Press [bold]a[/bold] to add one",
                id="empty-state",
            )


class ProfileDetail(Container):
    """Bordered panel showing details of the selected profile."""

    DEFAULT_CSS = """
    ProfileDetail {
        width: 1fr;
        height: 1fr;
        border: solid $primary;
        border-title-color: $text;
        border-title-style: bold;
        padding: 1 2;
    }

    ProfileDetail:focus {
        border: heavy $accent;
    }

    ProfileDetail #detail-content {
        width: 1fr;
        height: 1fr;
    }
    """

    def __init__(self):
        super().__init__(id="profile-detail")
        self.can_focus = True
        self.border_title = "[2] Details"
        self._content = Static("Select a profile to view details", id="detail-content")

    def compose(self):
        yield self._content

    def update_detail(self, profile: dict | None) -> None:
        """Update the detail panel content for the given profile."""
        if profile is None:
            self._content.update("[dim]Select a profile to view details[/dim]")
            return

        name = profile.get("name", "")
        source = profile.get("source", "")
        target = profile.get("target", "")
        parsers = profile.get("parsers", [])
        desc = profile.get("description", "")
        mapping = profile.get("mapping_preset", "")
        tags = profile.get("tags", [])
        created = profile.get("created_at", "")
        changelog = profile.get("target_changelog", False)

        source_exists = Path(source).exists() if source else False
        target_exists = Path(target).exists() if target else False

        rows = [
            ("Name", f"[bold]{name}[/bold]"),
            ("Description", desc or "[dim]none[/dim]"),
            ("", ""),
            ("Source", self._path_markup(source, source_exists)),
            ("Target", self._path_markup(target, target_exists)),
            ("", ""),
            ("Parsers", ", ".join(parsers) if parsers else "[dim]none[/dim]"),
            ("Mapping", mapping or "[dim]none[/dim]"),
            ("Tags", ", ".join(tags) if tags else "[dim]none[/dim]"),
            ("Changelog", "enabled" if changelog else "[dim]disabled[/dim]"),
            ("", ""),
            ("Created", created or "[dim]unknown[/dim]"),
        ]

        lines = []
        for label, value in rows:
            if label == "" and value == "":
                lines.append("")
            else:
                lines.append(f"[bold dim]{label + ':':<14}[/bold dim] {value}")

        self._content.update("\n".join(lines))

    @staticmethod
    def _path_markup(path: str, exists: bool) -> str:
        if not path:
            return "[dim]not set[/dim]"
        status = "[green]OK[/green]" if exists else "[red]MISSING[/red]"
        return f"{path}  {status}"


class ActionBar(Container):
    """Bottom bar showing available keybindings."""

    DEFAULT_CSS = """
    ActionBar {
        width: 1fr;
        height: 3;
        border: solid $primary;
        border-title-color: $text;
        border-title-style: bold;
        padding: 0 1;
        align: left middle;
    }

    ActionBar:focus {
        border: heavy $accent;
    }

    ActionBar #action-keys {
        width: 1fr;
        height: 1;
    }
    """

    def __init__(self):
        super().__init__(id="action-bar")
        self.can_focus = True
        self.border_title = "[3] Actions"

    def compose(self):
        keys = [
            ("[bold green]a[/bold green]: Add"),
            ("[bold yellow]e[/bold yellow]: Edit"),
            ("[bold red]d[/bold red]: Delete"),
            ("[bold cyan]v[/bold cyan]: Verify"),
            ("[bold cyan]s[/bold cyan]: Sort"),
            ("[bold cyan]S[/bold cyan]: Save sort"),
            ("[bold dim]Esc[/bold dim]: Back"),
        ]
        yield Static("  ".join(keys), id="action-keys")


# ── Main Screen ──────────────────────────────────

class ProfilesScreen(Screen):
    """Profile management screen with lazygit-style panel layout."""

    # Sort modes: (sort_by, order) or None for saved order
    # Cycle: saved → name asc → name desc → date desc → date asc → (repeat)
    SORT_MODES = (
        None,
        ("name", "asc"),
        ("name", "desc"),
        ("created_at", "desc"),
        ("created_at", "asc"),
    )

    SORT_MODE_LABELS = {
        ("name", "asc"): "name A→Z",
        ("name", "desc"): "name Z→A",
        ("created_at", "desc"): "newest first",
        ("created_at", "asc"): "oldest first",
    }

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
        Binding("a", "add_profile", "Add", show=False),
        Binding("e", "edit_profile", "Edit", show=False),
        Binding("d", "delete_profile", "Delete", show=False),
        Binding("v", "verify_profile", "Verify", show=False),
        Binding("s", "cycle_sort", "Sort", show=False),
        Binding("shift+s", "persist_sort", "Save Sort", show=False),
    ]

    DEFAULT_CSS = """
    ProfilesScreen {
        background: $surface;
    }

    ProfilesScreen #profiles-layout {
        width: 1fr;
        height: 1fr;
    }

    ProfilesScreen #panels-row {
        width: 1fr;
        height: 1fr;
    }

    ProfilesScreen #status-bar {
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
        self._profiles: list[dict] = []
        self._detail_panel: ProfileDetail | None = None
        self._profile_list: ProfileList | None = None
        self._status_bar: Static | None = None
        self._original_profiles: list[dict] = []
        self._sort_mode_index: int = 0
        self._pending_delete_name: str | None = None

    def compose(self):
        self._original_profiles = self.config_manager.list_profiles()
        self._profiles = self._apply_sort(self._original_profiles)
        mode_label = self._get_sort_mode_label()
        with Vertical(id="profiles-layout"):
            with Horizontal(id="panels-row"):
                self._profile_list = ProfileList(self._profiles, mode_label)
                yield self._profile_list
                self._detail_panel = ProfileDetail()
                yield self._detail_panel
            yield ActionBar()
        self._status_bar = Static("", id="status-bar")
        yield self._status_bar

    def on_mount(self) -> None:
        """Select the first profile on mount if any exist."""
        if self._profiles:
            self._show_profile(0)
            try:
                listview = self.query_one("#profile-listview", ListView)
                listview.focus()
            except Exception:
                pass

    def on_list_view_highlighted(self, event: ListView.Highlighted) -> None:
        """Update detail panel when list selection changes."""
        if event.item is not None and isinstance(event.item, ProfileListItem):
            profile = self.config_manager.get_profile(event.item.profile_name)
            if self._detail_panel:
                self._detail_panel.update_detail(profile)

    def _show_profile(self, index: int) -> None:
        """Show profile at given index in detail panel."""
        if 0 <= index < len(self._profiles):
            profile = self._profiles[index]
            full = self.config_manager.get_profile(profile["name"])
            if self._detail_panel:
                self._detail_panel.update_detail(full)

    def _get_selected_profile_name(self) -> str | None:
        """Get the name of the currently highlighted profile."""
        try:
            listview = self.query_one("#profile-listview", ListView)
        except Exception:
            return None
        if listview.highlighted_child and isinstance(listview.highlighted_child, ProfileListItem):
            return listview.highlighted_child.profile_name
        return None

    def _set_status(self, message: str) -> None:
        """Update the bottom status bar message."""
        if self._status_bar:
            self._status_bar.update(message)

    def _refresh_list(self) -> None:
        """Reload profiles and rebuild the list panel."""
        self._original_profiles = self.config_manager.list_profiles()
        self._profiles = self._apply_sort(self._original_profiles)
        if self._profile_list:
            self._profile_list.remove()

        panels_row = self.query_one("#panels-row", Horizontal)
        mode_label = self._get_sort_mode_label()
        new_list = ProfileList(self._profiles, mode_label)
        panels_row.mount(new_list, before=self._detail_panel)
        self._profile_list = new_list

        if self._profiles:
            self._show_profile(0)
        elif self._detail_panel:
            self._detail_panel.update_detail(None)

    # ── Actions ──────────────────────────────────

    def action_back(self) -> None:
        """Return to home screen."""
        self.app.pop_screen()

    def action_force_quit(self) -> None:
        """Immediately quit the TUI on Ctrl+C."""
        self.app.exit()

    def action_focus_section_1(self) -> None:
        """Focus the profile list (section 1)."""
        # Try to focus the ListView inside the ProfileList first
        if not self._focus_widget("#profile-listview", ListView):
            # Fall back to focusing the ProfileList container itself
            if not self._focus_widget("#profile-list", Container):
                self._set_status("[dim]Profile list not focusable right now[/dim]")

    def action_focus_section_2(self) -> None:
        """Focus the profile detail panel (section 2)."""
        if not self._focus_widget("#profile-detail", Container):
            self._set_status("[dim]Detail panel not focusable right now[/dim]")

    def action_focus_section_3(self) -> None:
        """Focus the action bar (section 3)."""
        if not self._focus_widget("#action-bar", Container):
            self._set_status("[dim]Action bar not focusable right now[/dim]")  

    def _focus_widget(self, selector: str, widget_type: type[Any]) -> bool:
        """Try to focus a widget by selector and type. Returns True if successful."""
        try:
            self.query_one(selector, widget_type).focus()
            return True
        except Exception:
            return False

    def action_add_profile(self) -> None:
        """Open add profile modal."""
        self.app.push_screen(AddProfileModal(), callback=self._on_add_profile_result)

    def _on_add_profile_result(self, result: dict | None) -> None:
        """Handle result from add profile modal."""
        if result is None:
            self._set_status("Add cancelled")
            return

        # Check for duplicate name
        existing = self.config_manager.get_profile(result["name"])
        if existing:
            self._set_status(f"[bold red]Profile '{result['name']}' already exists — use edit instead[/bold red]")
            return

        try:
            self.config_manager.add_profile(
                name=result["name"],
                source=result["source"],
                target=result["target"],
                parsers=result["parsers"],
                description=result["description"],
                mapping_preset=result["mapping_preset"],
                target_changelog=result["target_changelog"],
            )
            self._refresh_list()
            self._set_status(f"[green]Profile '{result['name']}' added[/green]")
        except Exception as e:
            self._set_status(f"[bold red]Error: {e}[/bold red]")

    def action_edit_profile(self) -> None:
        """Open edit profile modal for the selected profile."""
        name = self._get_selected_profile_name()
        if not name:
            self._set_status("No profile selected")
            return

        profile = self.config_manager.get_profile(name)
        if not profile:
            self._set_status(f"Profile '{name}' not found")
            return

        self.app.push_screen(AddProfileModal(profile=profile), callback=self._on_edit_profile_result)

    def _on_edit_profile_result(self, result: dict | None) -> None:
        """Handle result from edit profile modal."""
        if result is None:
            self._set_status("Edit cancelled")
            return

        original_name = result.get("original_name") or result["name"]
        name = result["name"]
        try:
            if name != original_name:
                self.config_manager.rename_profile(original_name, name)

            # Update each editable field
            self.config_manager.update_profile_field(name, "source", result["source"])
            self.config_manager.update_profile_field(name, "target", result["target"])
            self.config_manager.update_profile_field(name, "description", result["description"])
            self.config_manager.update_profile_field(name, "parsers", result["parsers"])
            self.config_manager.update_profile_field(name, "mapping_preset", result["mapping_preset"])
            self.config_manager.update_profile_field(name, "target_changelog", result["target_changelog"])

            # Refresh the list to reflect changes
            self._refresh_list()

            # Re-select and display the edited profile
            for idx, profile in enumerate(self._profiles):
                if profile["name"] == name:
                    listview = self.query_one("#profile-listview", ListView)
                    listview.index = idx
                    self._show_profile(idx)
                    break

            if name != original_name:
                self._set_status(f"[green]Profile renamed '{original_name}' -> '{name}' and updated[/green]")
            else:
                self._set_status(f"[green]Profile '{name}' updated[/green]")
        except Exception as e:
            self._set_status(f"[bold red]Error: {e}[/bold red]")

    def action_delete_profile(self) -> None:
        """Open delete confirmation modal for the selected profile."""
        name = self._get_selected_profile_name()
        if not name:
            self._set_status("No profile selected")
            return
        self._pending_delete_name = name
        self.app.push_screen(DeleteConfirmModal(name), callback=self._on_delete_profile_result)

    def _on_delete_profile_result(self, confirmed: bool) -> None:
        """Handle result from delete confirmation modal."""
        name = self._pending_delete_name
        self._pending_delete_name = None
        if not confirmed:
            self._set_status("Delete cancelled")
            return
        try:
            self.config_manager.remove_profile(name)
            self._refresh_list()
            self._set_status(f"[green]Deleted '{name}'[/green]")
        except ValueError as e:
            self._set_status(f"[bold red]Error: {e}[/bold red]")

    def action_verify_profile(self) -> None:
        """Verify source/target paths exist for the selected profile."""
        name = self._get_selected_profile_name()
        if not name:
            self._set_status("No profile selected")
            return

        profile = self.config_manager.get_profile(name)
        if not profile:
            self._set_status(f"Profile '{name}' not found")
            return

        source_ok = Path(profile["source"]).exists()
        target_ok = Path(profile["target"]).exists()

        src_status = "[green]OK[/green]" if source_ok else "[red]MISSING[/red]"
        tgt_status = "[green]OK[/green]" if target_ok else "[red]MISSING[/red]"
        self._set_status(f"Verify '{name}': Source {src_status}  Target {tgt_status}")

    def _apply_sort(self, profiles: list) -> list:
        """Apply current sort mode to profiles list. Returns sorted shallow copy or unchanged copy."""
        mode = self.SORT_MODES[self._sort_mode_index]
        if mode is None:
            return list(profiles)
        sort_by, order = mode
        reverse = order == "desc"
        def sort_key(p):
            if sort_by == "created_at":
                return p.get("created_at") or ""
            return p.get("name", "").lower()
        return sorted(profiles, key=sort_key, reverse=reverse)

    def _get_sort_mode_label(self) -> str:
        """Get the display label for the current sort mode."""
        mode = self.SORT_MODES[self._sort_mode_index]
        if mode is None:
            return ""
        return self.SORT_MODE_LABELS.get(mode, "")

    def action_cycle_sort(self) -> None:
        """Cycle through sort modes and refresh list."""
        self._sort_mode_index = (self._sort_mode_index + 1) % len(self.SORT_MODES)
        self._refresh_list()
        mode_label = self._get_sort_mode_label()
        if mode_label:
            self._set_status(f"Sort: {mode_label}")
        else:
            self._set_status("Sort: saved order")

    def action_persist_sort(self) -> None:
        """Save current sort order to profiles.json."""
        mode = self.SORT_MODES[self._sort_mode_index]
        if mode is None:
            self._set_status("[dim]No sort active—nothing to persist[/dim]")
            return
        sort_by, order = mode
        try:
            result = self.config_manager.sort_profiles(sort_by=sort_by, order=order, dry_run=False)
            self._original_profiles = result["profiles"]
            self._profiles = self._apply_sort(self._original_profiles)
            self._set_status(f"[green]Sort saved: {self._get_sort_mode_label()}[/green]")
        except Exception as e:
            self._set_status(f"[bold red]Error saving sort: {e}[/bold red]")
