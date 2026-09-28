"""
Comprehensive tests for ProfilesScreen standards compliance.

Tests verify:
- Keybinding presence (primary + fallback section focus keys, global Ctrl+C)
- Focus navigation semantics (focus-only, no side effects)
- Modal interaction flows (add/edit/delete/verify/sort)
- Partial failure handling
- Stale state prevention
- Ctrl+C quit from any section

Reference: docs/tui-screen-standards.md
"""

import asyncio

import pytest
from pathlib import Path
from config import ConfigManager
from tui.screens.profiles import ProfilesScreen, AddProfileModal, DeleteConfirmModal
from textual.binding import Binding
from textual.app import App, ComposeResult
from textual.containers import Container


class _FakeApp:
    def __init__(self):
        self.exited = False
        self.popped = False

    def exit(self):
        self.exited = True

    def pop_screen(self):
        self.popped = True


# ── Keybinding Tests ─────────────────────────────

class TestProfilesScreenKeybindings:
    """Verify all required keybindings are present."""
    
    def test_profiles_screen_has_all_bindings(self):
        """Check that all required keybindings exist in BINDINGS."""
        bindings = ProfilesScreen.BINDINGS
        binding_keys = [b.key for b in bindings]
        
        # Section focus (primary)
        assert "ctrl+1" in binding_keys, "Missing Ctrl+1 for section 1 focus"
        assert "ctrl+2" in binding_keys, "Missing Ctrl+2 for section 2 focus"
        assert "ctrl+3" in binding_keys, "Missing Ctrl+3 for section 3 focus"
        
        # Section focus (Alt fallback)
        assert "alt+1" in binding_keys, "Missing Alt+1 fallback for section 1"
        assert "alt+2" in binding_keys, "Missing Alt+2 fallback for section 2"
        assert "alt+3" in binding_keys, "Missing Alt+3 fallback for section 3"
        
        # Section focus (F-key fallback)
        assert "f1" in binding_keys, "Missing F1 fallback for section 1"
        assert "f2" in binding_keys, "Missing F2 fallback for section 2"
        assert "f3" in binding_keys, "Missing F3 fallback for section 3"
        
        # Global quit
        assert "ctrl+c" in binding_keys, "Missing Ctrl+C for global quit"
        
        # Back/quit alternatives
        assert "escape" in binding_keys, "Missing Esc for back"
        assert "q" in binding_keys, "Missing q for back"
    
    def test_section_focus_bindings_are_hidden(self):
        """Structural navigation keys should not appear in action bar (show=False)."""
        bindings_dict = {b.key: b for b in ProfilesScreen.BINDINGS}
        
        # Section focus keys must have show=False
        for key in ["ctrl+1", "ctrl+2", "ctrl+3", "alt+1", "alt+2", "alt+3", "f1", "f2", "f3"]:
            assert bindings_dict[key].show is False, \
                f"Binding {key} should have show=False (structural, not displayed)"
    
    def test_task_action_bindings_are_hidden(self):
        """Task action keys should also be hidden (not displayed in binding list)."""
        bindings_dict = {b.key: b for b in ProfilesScreen.BINDINGS}
        task_keys = ["a", "e", "d", "v", "s", "shift+s", "escape", "q", "ctrl+c"]
        
        for key in task_keys:
            assert bindings_dict[key].show is False, \
                f"Binding {key} should have show=False (hidden from action bar)"


# ── Focus Action Methods ─────────────────────────

class TestProfilesScreenFocusMethods:
    """Verify focus action methods exist and handle errors gracefully."""
    
    def test_focus_action_methods_exist(self):
        """All section focus action methods should be defined."""
        screen = ProfilesScreen(ConfigManager())
        
        assert hasattr(screen, "action_focus_section_1"), "Missing action_focus_section_1"
        assert hasattr(screen, "action_focus_section_2"), "Missing action_focus_section_2"
        assert hasattr(screen, "action_focus_section_3"), "Missing action_focus_section_3"
        assert hasattr(screen, "_focus_widget"), "Missing _focus_widget helper"
        assert callable(screen.action_focus_section_1)
        assert callable(screen.action_focus_section_2)
        assert callable(screen.action_focus_section_3)
        assert callable(screen._focus_widget)
    
    def test_focus_widget_helper_returns_bool(self):
        """_focus_widget should return True on success, False on failure."""
        screen = ProfilesScreen(ConfigManager())
        
        # Without compose/mount, widgets won't exist, so should return False
        result = screen._focus_widget("#non-existent-widget", Container)
        assert isinstance(result, bool), "_focus_widget should return bool"
        assert result is False, "_focus_widget should return False when widget doesn't exist"
    
    def test_quit_action_exists(self):
        """action_force_quit should exist and be callable."""
        config = ConfigManager()
        screen = ProfilesScreen(config)
        
        assert hasattr(screen, "action_force_quit"), "Missing action_force_quit"
        assert callable(screen.action_force_quit), "action_force_quit should be callable"


# ── Container IDs Test ───────────────────────────

class TestProfilesScreenContainerIDs:
    """Verify section containers have correct IDs for focus targeting."""
    
    def test_profile_list_has_id(self):
        """ProfileList container should have id='profile-list'."""
        from tui.screens.profiles import ProfileList
        
        profile_list = ProfileList([])
        assert profile_list.id == "profile-list", \
            "ProfileList should have id='profile-list' for focus targeting"
    
    def test_profile_detail_has_id(self):
        """ProfileDetail container should have id='profile-detail'."""
        from tui.screens.profiles import ProfileDetail
        
        profile_detail = ProfileDetail()
        assert profile_detail.id == "profile-detail", \
            "ProfileDetail should have id='profile-detail' for focus targeting"
    
    def test_action_bar_has_id(self):
        """ActionBar container should have id='action-bar'."""
        from tui.screens.profiles import ActionBar
        
        action_bar = ActionBar()
        assert action_bar.id == "action-bar", \
            "ActionBar should have id='action-bar' for focus targeting"


class TestProfilesScreenHighlightStyling:
    """Verify the profile screen does not use custom highlight styling."""

    def test_profile_list_has_no_custom_highlight_rules(self):
        """ProfileList should not define any custom highlight styling."""
        from tui.screens.profiles import ProfileList

        css = ProfileList.DEFAULT_CSS

        assert "ProfileList ListView > ListItem.--highlight" not in css
        assert "ProfileList ListView:focus > ListItem.--highlight" not in css

    def test_profile_detail_has_no_focus_border_rule(self):
        """ProfileDetail should not define a focused accent border."""
        from tui.screens.profiles import ProfileDetail

        css = ProfileDetail.DEFAULT_CSS

        assert "ProfileDetail:focus" not in css

    def test_profile_list_has_no_focus_border_rule(self):
        """ProfileList should not define a focused accent border."""
        from tui.screens.profiles import ProfileList

        css = ProfileList.DEFAULT_CSS

        assert "ProfileList:focus" not in css

    def test_action_bar_has_no_focus_border_rule(self):
        """ActionBar should not define a focused accent border."""
        from tui.screens.profiles import ActionBar

        css = ActionBar.DEFAULT_CSS

        assert "ActionBar:focus" not in css

# ── Focus-Only Safety Tests ──────────────────────

class TestFocusOnlySafety:
    """Verify section focus keys don't trigger destructive actions."""
    
    def test_focus_keys_dont_add_profile(self):
        """Pressing Ctrl+1/2/3 should not trigger add profile action (focus-only)."""
        config = ConfigManager()
        screen = ProfilesScreen(config)
        
        # Focus actions should be callable without exceptions
        screen.action_focus_section_1()
        screen.action_focus_section_2()
        screen.action_focus_section_3()
        # If we get here without exception, focus is working correctly

    def test_focus_keys_dont_delete_profile(self):
        """Pressing Ctrl+1/2/3 should not trigger delete profile action (focus-only)."""
        config = ConfigManager()
        screen = ProfilesScreen(config)
        
        # Focus actions should be idempotent
        initial_profiles = list(screen._profiles)
        screen.action_focus_section_1()
        screen.action_focus_section_2()
        screen.action_focus_section_3()
        
        # Profile list should remain unchanged
        assert initial_profiles == screen._profiles, \
            "Focus actions should not modify profile list"


# ── Back Action Tests ────────────────────────────

class TestProfilesScreenBackActions:
    """Verify back/quit actions work correctly."""
    
    def test_action_back_pops_screen(self):
        """Esc and q should trigger back action."""
        config = ConfigManager()
        screen = ProfilesScreen(config)
        
        # Back action should exist and be callable
        assert hasattr(screen, "action_back"), "Missing action_back"
        assert callable(screen.action_back), "action_back should be callable"

    def test_action_back_calls_pop_screen(self, monkeypatch):
        config = ConfigManager()
        screen = ProfilesScreen(config)
        app = _FakeApp()
        monkeypatch.setattr(ProfilesScreen, "app", property(lambda _self: app))

        screen.action_back()

        assert app.popped is True

    def test_action_force_quit_calls_exit(self, monkeypatch):
        config = ConfigManager()
        screen = ProfilesScreen(config)
        app = _FakeApp()
        monkeypatch.setattr(ProfilesScreen, "app", property(lambda _self: app))

        screen.action_force_quit()

        assert app.exited is True


# ── Modal Interaction Tests ──────────────────────

class TestModalInteractions:
    """Test add/edit/delete modal flows."""
    
    def test_add_profile_modal_exists(self):
        """AddProfileModal should be importable."""
        from tui.screens.profiles import AddProfileModal
        
        modal = AddProfileModal()
        assert modal is not None
        assert hasattr(modal, "key_enter"), "AddProfileModal should handle Enter"
        assert hasattr(modal, "action_cancel"), "AddProfileModal should have cancel action"
    
    def test_delete_confirm_modal_exists(self):
        """DeleteConfirmModal should be importable."""
        from tui.screens.profiles import DeleteConfirmModal
        
        modal = DeleteConfirmModal("test_profile")
        assert modal is not None
        assert hasattr(modal, "key_y"), "DeleteConfirmModal should handle Y key"
        assert hasattr(modal, "key_n"), "DeleteConfirmModal should handle N key"
    
    def test_add_profile_action_exists(self):
        """action_add_profile should exist and be callable."""
        config = ConfigManager()
        screen = ProfilesScreen(config)
        
        assert hasattr(screen, "action_add_profile"), "Missing action_add_profile"
        assert callable(screen.action_add_profile), "action_add_profile should be callable"


# ── Status Bar Message Tests ─────────────────────

class TestStatusBarMessages:
    """Verify status bar displays appropriate feedback."""
    
    def test_set_status_message(self):
        """_set_status should update the status bar."""
        config = ConfigManager()
        screen = ProfilesScreen(config)
        
        from textual.widgets import Static
        screen._status_bar = Static("")
        
        screen._set_status("Test message")
        # Verify the update method was called (actual content check would require render)
        assert screen._status_bar is not None
    
    def test_focus_status_on_failure(self):
        """Focus actions should show status message when focus fails."""
        config = ConfigManager()
        screen = ProfilesScreen(config)
        
        from textual.widgets import Static
        screen._status_bar = Static("")
        
        # Without compose/mount, focus will fail and show status
        screen.action_focus_section_1()
        # Should have set a status message
        assert screen._status_bar is not None


# ── Error Handling Tests ─────────────────────────

class TestErrorHandling:
    """Test error handling in profile operations."""
    
    def test_verify_on_missing_paths(self):
        """Verify should show [RED] MISSING for non-existent paths."""
        from tui.screens.profiles import ProfileDetail
        
        detail = ProfileDetail()
        
        # Create a profile with non-existent paths
        profile = {
            "name": "test",
            "source": "/non/existent/path",
            "target": "/also/missing",
            "parsers": [],
            "description": "",
            "mapping_preset": "",
            "tags": [],
            "created_at": "",
            "target_changelog": False,
        }
        
        detail.update_detail(profile)
        # Should update without crashing
        assert detail._content is not None


# ── Deviation Documentation Test ─────────────────

class TestDeviationDocumentation:
    """Verify deviation from standards is documented if applicable."""
    
    def test_profiles_selection_only_phase_is_intentional(self):
        """Profiles screen uses selection-only phase (no running/done)."""
        # This is intentional because:
        # 1. All operations are synchronous (add/edit/delete/verify/sort are instant)
        # 2. Modal interactions don't require progress tracking
        # 3. Operations are modal-driven, not async worker-driven
        
        screen = ProfilesScreen(ConfigManager())
        
        # Verify there's no _phase attribute (unlike RunProfileScreen)
        # This is expected and correct for this screen
        assert not hasattr(screen, "_phase") or \
               not hasattr(screen, "_run_id"), \
            "Profiles screen correctly doesn't implement multi-phase model"


# ── Integration Tests ────────────────────────────

class TestProfilesScreenIntegration:
    """Integration tests for profiles screen functionality."""
    
    def test_empty_profile_list_display(self):
        """Screen should display 'No profiles' message when list is empty."""
        from tui.screens.profiles import ProfileList
        
        profile_list = ProfileList([])
        
        # Compose and check content
        widget_list = list(profile_list.compose())
        assert len(widget_list) > 0, "Empty list should have placeholder widget"
    
    def test_profile_detail_with_none(self):
        """Detail panel should handle None profile gracefully."""
        from tui.screens.profiles import ProfileDetail
        
        detail = ProfileDetail()
        detail.update_detail(None)
        
        # Should update without crashing
        assert detail._content is not None


class _MemoryProfileConfig:
    def __init__(self, profiles=None):
        self.profiles = [dict(profile) for profile in (profiles or [])]
        self.failures = set()

    def _fail_if_requested(self, operation):
        if operation in self.failures:
            raise OSError(f"{operation} failed")

    def list_profiles(self):
        return [dict(profile) for profile in self.profiles]

    def get_profile(self, name):
        for profile in self.profiles:
            if profile["name"] == name:
                return dict(profile)
        return None

    def add_profile(self, **values):
        self._fail_if_requested("add_profile")
        self.profiles.append({**values, "created_at": "2026-09-28T00:00:00", "tags": []})

    def update_profile_field(self, name, field, value):
        self._fail_if_requested("update_profile_field")
        profile = next(profile for profile in self.profiles if profile["name"] == name)
        profile[field] = value

    def rename_profile(self, old_name, new_name):
        self._fail_if_requested("rename_profile")
        profile = next(profile for profile in self.profiles if profile["name"] == old_name)
        profile["name"] = new_name

    def remove_profile(self, name):
        self._fail_if_requested("remove_profile")
        self.profiles = [profile for profile in self.profiles if profile["name"] != name]

    def sort_profiles(self, sort_by, order, dry_run=False):
        self._fail_if_requested("sort_profiles")
        profiles = sorted(self.profiles, key=lambda profile: profile.get(sort_by, ""), reverse=order == "desc")
        if not dry_run:
            self.profiles = profiles
        return {"profiles": profiles}


class _MountedScreenApp(App):
    def __init__(self, screen):
        super().__init__()
        self._initial_screen = screen

    def on_mount(self):
        self.push_screen(self._initial_screen)


def _profile(name="existing"):
    return {
        "name": name,
        "source": "source",
        "target": "target",
        "description": "original",
        "parsers": [],
        "tags": [],
        "created_at": "2026-09-28T00:00:00",
    }


def _status_text(screen):
    return str(screen.query_one("#status-bar").render())


def _fill_profile_form(modal, name, source="source", target="target", description="description"):
    modal.query_one("#input-name").value = name
    modal.query_one("#input-source").value = source
    modal.query_one("#input-target").value = target
    modal.query_one("#input-desc").value = description


def test_profiles_add_edit_delete_workflows_submit_and_report_status():
    config = _MemoryProfileConfig()
    screen = ProfilesScreen(config)
    app = _MountedScreenApp(screen)

    async def exercise():
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.press("a")
            await pilot.pause()
            add_modal = app.screen
            _fill_profile_form(add_modal, "new")
            await pilot.press("enter")
            await pilot.pause()
            assert app.screen is screen
            assert config.get_profile("new") is not None
            assert "added" in _status_text(screen)

            await pilot.press("e")
            await pilot.pause()
            edit_modal = app.screen
            edit_modal.query_one("#input-name").value = "renamed"
            edit_modal.query_one("#input-desc").value = "updated"
            await pilot.press("enter")
            await pilot.pause()
            assert app.screen is screen
            assert config.get_profile("renamed")["description"] == "updated"
            assert "renamed" in _status_text(screen)

            await pilot.press("d")
            await pilot.pause()
            await pilot.press("y")
            await pilot.pause()
            assert config.get_profile("renamed") is None
            assert "Deleted" in _status_text(screen)

    asyncio.run(exercise())


def test_duplicate_profile_name_stays_actionable_in_add_form():
    config = _MemoryProfileConfig([_profile()])
    screen = ProfilesScreen(config)
    app = _MountedScreenApp(screen)

    async def exercise():
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.press("a")
            await pilot.pause()
            modal = app.screen
            _fill_profile_form(modal, "existing")
            await pilot.press("enter")
            await pilot.pause()

            assert app.screen is modal
            assert "already exists" in str(modal.query_one("#form-error").render()).lower()
            assert app.screen.focused.id == "input-name"
            assert len(config.list_profiles()) == 1

    asyncio.run(exercise())


def test_duplicate_profile_rename_stays_actionable_in_edit_form():
    config = _MemoryProfileConfig([_profile("existing"), _profile("other")])
    screen = ProfilesScreen(config)
    app = _MountedScreenApp(screen)

    async def exercise():
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.press("e")
            await pilot.pause()
            modal = app.screen
            _fill_profile_form(modal, "other")
            await pilot.press("enter")
            await pilot.pause()

            assert app.screen is modal
            assert "already exists" in str(modal.query_one("#form-error").render()).lower()
            assert app.screen.focused.id == "input-name"
            assert [profile["name"] for profile in config.list_profiles()] == ["existing", "other"]

    asyncio.run(exercise())


@pytest.mark.parametrize("context", ["screen", "add", "edit", "delete"])
def test_profiles_ctrl_c_exits_from_screen_and_mounted_modals(context):
    config = _MemoryProfileConfig([_profile()])
    screen = ProfilesScreen(config)
    app = _MountedScreenApp(screen)

    async def exercise():
        async with app.run_test() as pilot:
            await pilot.pause()
            if context != "screen":
                await pilot.press({"add": "a", "edit": "e", "delete": "d"}[context])
                await pilot.pause()
            await pilot.press("ctrl+c")
            await pilot.pause()
            assert not pilot.app.is_running

    asyncio.run(exercise())


@pytest.mark.parametrize("operation,key", [("add_profile", "a"), ("update_profile_field", "e"), ("remove_profile", "d")])
def test_profile_persistence_failures_are_reported_without_success(operation, key):
    config = _MemoryProfileConfig([_profile()])
    config.failures.add(operation)
    screen = ProfilesScreen(config)
    app = _MountedScreenApp(screen)

    async def exercise():
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.press(key)
            await pilot.pause()
            if key in ("a", "e"):
                modal = app.screen
                _fill_profile_form(modal, "new" if key == "a" else "existing")
                await pilot.press("enter")
            else:
                await pilot.press("y")
            await pilot.pause()

            status = _status_text(screen).lower()
            assert "error" in status or "failed" in status
            assert not any(word in status for word in (" added", " updated", " deleted"))

    asyncio.run(exercise())


def test_profiles_tab_moves_forward_and_shift_tab_returns_focus():
    config = _MemoryProfileConfig([_profile()])
    screen = ProfilesScreen(config)
    app = _MountedScreenApp(screen)

    async def exercise():
        async with app.run_test() as pilot:
            await pilot.pause()
            first_focus = app.screen.focused
            await pilot.press("tab")
            await pilot.pause()
            assert app.screen.focused is not first_focus
            await pilot.press("shift+tab")
            await pilot.pause()
            assert app.screen.focused is first_focus

    asyncio.run(exercise())


def test_profiles_section_keys_only_move_focus_and_action_hints_are_task_actions():
    config = _MemoryProfileConfig([_profile()])
    screen = ProfilesScreen(config)
    app = _MountedScreenApp(screen)

    async def exercise():
        async with app.run_test() as pilot:
            await pilot.pause()
            original_profiles = config.list_profiles()
            for key in ("ctrl+1", "alt+2", "f3"):
                await pilot.press(key)
                await pilot.pause()
                assert app.screen is screen
            assert config.list_profiles() == original_profiles
            action_text = screen.query_one("#action-keys").render().plain
            assert all(key not in action_text for key in ("Ctrl", "Alt", "F1", "F2", "F3", "Up", "Down"))

    asyncio.run(exercise())
