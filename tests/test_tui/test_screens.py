"""
TUI screen tests.
"""

import asyncio

import pytest
from textual.app import App
from tui.app import MCRecipeApp
from tui.screens import backups as backups_module
from tui.screens import reports as reports_module
from tui.screens.backups import (
    ConfirmModal as BackupConfirmModal,
    PruneBackupsModal,
    TextViewerModal as BackupTextViewerModal,
    BackupsScreen,
)
from tui.screens.config import (
    ConfirmModal as ConfigConfirmModal,
    ConfigScreen,
    ResetAllModal,
    TextViewerModal as ConfigTextViewerModal,
)
from tui.screens.reports import (
    ConfirmModal as ReportConfirmModal,
    PruneReportsModal,
    ReportsScreen,
    TextViewerModal as ReportTextViewerModal,
)
from tui.screens.suites import (
    ConfirmModal,
    ManageProfilesScreen,
    SuiteActionBar,
    SuiteFormModal,
    SuitesScreen,
)
from tui.screens.home import HomeScreen


class _DummySuitesConfigManager:
    def list_suites(self):
        return []

    def list_profiles(self):
        return []

    def get_profile(self, _name):
        return None

    def get_suite(self, _name):
        return None


class _DummyPanelsRow:
    def __init__(self, events):
        self._events = events

    def mount(self, _widget, before=None):
        self._events.append(("mount", before))


class _FakeApp:
    def __init__(self):
        self.exited = False
        self.popped = False

    def exit(self):
        self.exited = True

    def pop_screen(self):
        self.popped = True


class _GlobalQuitHost(App):
    BINDINGS = MCRecipeApp.BINDINGS

    def __init__(self, screen):
        super().__init__()
        self._initial_screen = screen

    def on_mount(self):
        self.push_screen(self._initial_screen)


class TestSuitesScreenBindings:
    """SuitesScreen must meet TUI screen-standards keybinding policy."""

    def _keys(self):
        return {b.key for b in SuitesScreen.BINDINGS}

    def test_has_ctrl_c_quit(self):
        assert "ctrl+c" in self._keys()

    def test_has_q_back(self):
        assert "q" in self._keys()

    def test_has_no_section_navigation_bindings(self):
        keys = self._keys()
        blocked = {
            "ctrl+1", "ctrl+2", "ctrl+3",
            "alt+1", "alt+2", "alt+3",
            "f1", "f2", "f3",
        }
        assert blocked.isdisjoint(keys)

    def test_ctrl_c_routes_to_force_quit(self):
        actions = {b.key: b.action for b in SuitesScreen.BINDINGS}
        assert actions["ctrl+c"] == "force_quit"

    def test_suites_force_quit_calls_exit(self, monkeypatch):
        screen = SuitesScreen(_DummySuitesConfigManager())
        app = _FakeApp()
        monkeypatch.setattr(SuitesScreen, "app", property(lambda _self: app))

        screen.action_force_quit()

        assert app.exited is True

    def test_suites_back_calls_pop_screen(self, monkeypatch):
        screen = SuitesScreen(_DummySuitesConfigManager())
        app = _FakeApp()
        monkeypatch.setattr(SuitesScreen, "app", property(lambda _self: app))

        screen.action_back()

        assert app.popped is True

    def test_focus_section_actions_not_exposed(self):
        """SuitesScreen intentionally disables section-to-section key navigation."""
        screen = SuitesScreen(_DummySuitesConfigManager())

        assert not hasattr(screen, "action_focus_section_1")
        assert not hasattr(screen, "action_focus_section_2")
        assert not hasattr(screen, "action_focus_section_3")

    def test_initial_focus_falls_back_when_listview_unavailable(self, monkeypatch):
        """Entering suites screen should still assign focus without requiring a click."""
        screen = SuitesScreen(_DummySuitesConfigManager())
        calls: list[str] = []

        def _focus(selector, _widget_type):
            calls.append(selector)
            return selector == "#suite-detail-panel"

        monkeypatch.setattr(screen, "_focus_widget", _focus)
        monkeypatch.setattr(screen, "_focus_suite_panel", lambda: False)

        screen._ensure_initial_focus()

        assert calls == ["#suite-listview"]

    def test_suite_action_bar_can_be_assigned_id(self):
        """Regression: action bar should be instantiated without kwargs and assigned id later."""
        action_bar = SuiteActionBar()
        action_bar.id = "suite-actions-panel"

        assert action_bar.id == "suite-actions-panel"

    def test_refresh_list_removes_old_panel_before_mount(self, monkeypatch):
        """Regression: refresh should remove old suite panel before mounting replacement."""
        events: list[tuple[str, object]] = []
        screen = SuitesScreen(_DummySuitesConfigManager())

        class _OldSuiteList:
            def __init__(self):
                self.id = "suite-list-panel"

            def remove(self):
                events.append(("remove", self.id))

        class _DummyDetailPanel:
            def update_detail(self, _suite):
                return None

        old_panel = _OldSuiteList()
        screen._suite_list = old_panel
        screen._detail_panel = _DummyDetailPanel()

        monkeypatch.setattr(screen, "query_one", lambda *_a, **_k: _DummyPanelsRow(events))
        monkeypatch.setattr(screen, "_get_selected_suite_name", lambda: None)
        monkeypatch.setattr(screen, "call_after_refresh", lambda _cb: None)
        monkeypatch.setattr(screen, "_show_suite", lambda _idx: None)

        screen._refresh_list()

        assert old_panel.id == "suite-list-panel"
        assert events[0] == ("remove", "suite-list-panel")


class TestManageProfilesScreenBindings:
    """ManageProfilesScreen must meet TUI screen-standards keybinding policy."""

    def _keys(self):
        return {b.key for b in ManageProfilesScreen.BINDINGS}

    def test_has_ctrl_c_quit(self):
        assert "ctrl+c" in self._keys()

    def test_has_q_back(self):
        assert "q" in self._keys()

    def test_has_primary_section_bindings(self):
        keys = self._keys()
        assert "ctrl+1" in keys
        assert "ctrl+2" in keys
        assert "ctrl+3" in keys

    def test_has_alt_fallback_bindings(self):
        keys = self._keys()
        assert "alt+1" in keys
        assert "alt+2" in keys
        assert "alt+3" in keys

    def test_has_f_key_fallback_bindings(self):
        keys = self._keys()
        assert "f1" in keys
        assert "f2" in keys
        assert "f3" in keys

    def test_ctrl_c_routes_to_force_quit(self):
        actions = {b.key: b.action for b in ManageProfilesScreen.BINDINGS}
        assert actions["ctrl+c"] == "force_quit"

    def test_manage_profiles_force_quit_calls_exit(self, monkeypatch):
        screen = ManageProfilesScreen(_DummySuitesConfigManager(), "demo")
        app = _FakeApp()
        monkeypatch.setattr(ManageProfilesScreen, "app", property(lambda _self: app))

        screen.action_force_quit()

        assert app.exited is True

    def test_manage_profiles_back_calls_pop_screen(self, monkeypatch):
        screen = ManageProfilesScreen(_DummySuitesConfigManager(), "demo")
        app = _FakeApp()
        monkeypatch.setattr(ManageProfilesScreen, "app", property(lambda _self: app))

        screen.action_back()

        assert app.popped is True

    def test_section_keys_are_focus_only(self):
        """Section focus keys must not map to destructive actions."""
        section_keys = {
            "ctrl+1", "ctrl+2", "ctrl+3",
            "alt+1", "alt+2", "alt+3",
            "f1", "f2", "f3",
        }
        for binding in ManageProfilesScreen.BINDINGS:
            if binding.key in section_keys:
                assert "focus_section" in binding.action, (
                    f"Key {binding.key!r} maps to {binding.action!r}; expected a focus_section action"
                )

    def test_action_bar_reorder_keys_escape_brackets(self):
        """Reorder key hints must render literal [ and ] without malformed rich tags."""
        text = ManageProfilesScreen.ACTIONS_TEXT
        assert "\\[" in text
        assert "\\]" in text
        assert "[bold cyan][[/bold cyan]/[bold cyan]][/bold cyan]" not in text

    def test_refresh_replaces_panels_without_fixed_dynamic_ids(self, monkeypatch):
        """Refresh should rebuild dynamic panels without reusing fixed IDs."""
        screen = ManageProfilesScreen(_DummySuitesConfigManager(), "test-suite")
        events: list[tuple[str, object]] = []
        mounted: list[object] = []
        callbacks = []

        class _OldPanel:
            def __init__(self, panel_id: str):
                self.id = panel_id
                self.listview = None

            def remove(self):
                events.append(("remove", self.id))

                async def wait_for_removal():
                    return None

                return wait_for_removal()

        class _DummyRow:
            async def mount(self, widget):
                mounted.append(widget)

        class _NewPanel:
            def __init__(self):
                self.id = None
                self.listview = None
                self.profile_names = []

        screen._in_panel = _OldPanel("in-suite-panel")
        screen._available_panel = _OldPanel("available-panel")
        monkeypatch.setattr(screen, "query_one", lambda *_a, **_k: _DummyRow())
        monkeypatch.setattr(screen, "_build_in_panel", lambda: _NewPanel())
        monkeypatch.setattr(screen, "_build_available_panel", lambda: _NewPanel())
        monkeypatch.setattr(screen, "_sync_active_panel_classes", lambda: None)
        monkeypatch.setattr(screen, "_focus_panel", lambda *_a, **_k: None)
        monkeypatch.setattr(screen, "call_after_refresh", callbacks.append)

        screen._refresh()
        asyncio.run(callbacks[0]())

        assert events == [
            ("remove", "in-suite-panel"),
            ("remove", "available-panel"),
        ]
        assert len(mounted) == 2
        assert all(getattr(widget, "id", object()) is None for widget in mounted)


def test_home_screen_exists():
    """Placeholder test - home screen should be importable."""
    from tui.screens.home import HomeScreen
    assert HomeScreen is not None


def test_home_force_quit_calls_exit(monkeypatch):
    screen = HomeScreen(_DummySuitesConfigManager())
    app = _FakeApp()
    monkeypatch.setattr(HomeScreen, "app", property(lambda _self: app))

    screen.action_force_quit()

    assert app.exited is True


def test_profiles_screen_exists():
    """Placeholder test - profiles screen should be importable."""
    from tui.screens.profiles import ProfilesScreen
    assert ProfilesScreen is not None


def test_remaining_screens_exist():
    """Remaining TUI screens should be importable."""
    from tui.screens.backups import BackupsScreen
    from tui.screens.config import ConfigScreen
    from tui.screens.reports import ReportsScreen
    from tui.screens.run_profile import RunProfileScreen
    from tui.screens.suites import SuitesScreen

    assert BackupsScreen is not None
    assert ConfigScreen is not None
    assert ReportsScreen is not None
    assert RunProfileScreen is not None
    assert SuitesScreen is not None


@pytest.mark.parametrize(
    "screen_name,modal_name",
    [
        ("reports", None),
        ("reports", "viewer"),
        ("reports", "confirm"),
        ("reports", "prune"),
        ("backups", None),
        ("backups", "viewer"),
        ("backups", "confirm"),
        ("backups", "prune"),
        ("config", None),
        ("config", "viewer"),
        ("config", "confirm"),
        ("config", "reset"),
    ],
)
def test_global_ctrl_c_exits_from_data_screens_and_modals(screen_name, modal_name, monkeypatch):
    if screen_name == "reports":
        class _EmptyReportManager:
            def list_reports(self, **_kwargs):
                return []

        monkeypatch.setattr(reports_module, "ReportManager", _EmptyReportManager)
        screen = ReportsScreen(object())
        modals = {
            "viewer": lambda: ReportTextViewerModal("Report", "content"),
            "confirm": lambda: ReportConfirmModal("Delete", "Confirm?"),
            "prune": PruneReportsModal,
        }
    elif screen_name == "backups":
        class _EmptyBackupManager:
            def list_backups(self):
                return []

        monkeypatch.setattr(backups_module, "BackupManager", _EmptyBackupManager)
        screen = BackupsScreen(object())
        modals = {
            "viewer": lambda: BackupTextViewerModal("Backup", "content"),
            "confirm": lambda: BackupConfirmModal("Delete", "Confirm?"),
            "prune": PruneBackupsModal,
        }
    else:
        monkeypatch.setattr(ConfigScreen, "_refresh", lambda _self: None)
        screen = ConfigScreen(object())
        modals = {
            "viewer": lambda: ConfigTextViewerModal("Presets", "content"),
            "confirm": lambda: ConfigConfirmModal("Reset", "Confirm?"),
            "reset": ResetAllModal,
        }

    app = _GlobalQuitHost(screen)

    async def exercise():
        async with app.run_test() as pilot:
            await pilot.pause()
            if modal_name:
                app.push_screen(modals[modal_name]())
                await pilot.pause()
            await pilot.press("ctrl+c")
            await pilot.pause()
            assert not pilot.app.is_running

    asyncio.run(exercise())


class _HomePilotApp(App):
    def __init__(self):
        super().__init__()
        self.home = None
        self.routes = []

    def on_mount(self):
        self.home = HomeScreen(_DummySuitesConfigManager())
        self.push_screen(self.home)

    def push_profile_screen(self):
        self.routes.append("profile")

    def push_suite_screen(self):
        self.routes.append("suite")

    def push_run_screen(self):
        self.routes.append("run")

    def push_reports_screen(self):
        self.routes.append("reports")

    def push_backups_screen(self):
        self.routes.append("backups")

    def push_config_screen(self):
        self.routes.append("config")


def test_home_shortcut_works_with_input_focus_without_consuming_command_entry():
    app = _HomePilotApp()

    async def exercise():
        async with app.run_test() as pilot:
            await pilot.pause()
            assert app.screen.focused is app.home.command_input

            await pilot.press("p")
            assert app.home.command_input.value == "p"
            assert app.routes == []

            app.home.command_input.value = ""
            await pilot.press("alt+p")
            await pilot.pause()
            assert app.routes == ["profile"]

            app.routes.clear()
            await pilot.press(*tuple("profile"), "enter")
            await pilot.pause()
            assert app.routes == ["profile"]

    asyncio.run(exercise())


def test_home_unknown_command_is_reported_and_retained():
    app = _HomePilotApp()

    async def exercise():
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.press(*tuple("not-a-command"), "enter")
            await pilot.pause()

            assert app.home.command_input.value == "not-a-command"
            assert "Unknown command" in str(app.home.query_one("#home-status").render())

    asyncio.run(exercise())


def test_home_all_alt_shortcuts_route_with_initial_input_focus():
    app = _HomePilotApp()
    shortcuts = (
        ("alt+p", "profile"),
        ("alt+s", "suite"),
        ("alt+r", "run"),
        ("alt+h", "reports"),
        ("alt+b", "backups"),
        ("alt+c", "config"),
    )

    async def exercise():
        async with app.run_test() as pilot:
            await pilot.pause()
            for key, command in shortcuts:
                assert app.screen.focused is app.home.command_input
                await pilot.press(key)
                assert app.routes.pop() == command

    asyncio.run(exercise())


def test_home_arrow_navigation_and_enter_work_from_initial_input_focus():
    app = _HomePilotApp()

    async def exercise():
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.press("down")
            assert app.home.command_list.selected_index == 1
            await pilot.press("enter")
            assert app.routes == ["suite"]

    asyncio.run(exercise())


def test_home_tab_completes_a_command_from_focused_input():
    app = _HomePilotApp()

    async def exercise():
        async with app.run_test() as pilot:
            await pilot.pause()
            app.home.command_input.value = "prof"
            await pilot.press("tab")
            assert app.home.command_input.value == "profile"

    asyncio.run(exercise())


@pytest.mark.parametrize("key", ["ctrl+c", "alt+q"])
def test_home_quit_shortcuts_exit_from_focused_command_input(key):
    app = _HomePilotApp()

    async def exercise():
        async with app.run_test() as pilot:
            await pilot.pause()
            assert app.screen.focused is app.home.command_input
            await pilot.press(key)
            await pilot.pause()
            assert not pilot.app.is_running

    asyncio.run(exercise())


class _MemorySuitesConfigManager:
    def __init__(self, profiles=None, suites=None):
        self.profiles = [dict(profile) for profile in (profiles or [])]
        self.suites = [dict(suite) for suite in (suites or [])]
        self.failures = set()

    def _fail_if_requested(self, operation):
        if operation in self.failures:
            raise OSError(f"{operation} failed")

    def list_profiles(self):
        return [dict(profile) for profile in self.profiles]

    def get_profile(self, name):
        return next((dict(profile) for profile in self.profiles if profile["name"] == name), None)

    def list_suites(self):
        return [dict(suite) for suite in self.suites]

    def get_suite(self, name):
        suite = next((suite for suite in self.suites if suite["name"] == name), None)
        return dict(suite) if suite else None

    def save_suite(self, name, description="", profiles=None):
        self._fail_if_requested("save_suite")
        existing = self.get_suite(name)
        created_at = existing.get("created_at", "2026-09-28T00:00:00") if existing else "2026-09-28T00:00:00"
        current_profiles = existing.get("profiles", []) if existing else []
        self.suites = [suite for suite in self.suites if suite["name"] != name]
        self.suites.append({
            "name": name,
            "description": description,
            "created_at": created_at,
            "profiles": list(profiles if profiles is not None else current_profiles),
        })

    def delete_suite(self, name):
        self._fail_if_requested("delete_suite")
        self.suites = [suite for suite in self.suites if suite["name"] != name]

    def add_profile_to_suite(self, suite_name, profile_name):
        self._fail_if_requested("add_profile_to_suite")
        suite = next(suite for suite in self.suites if suite["name"] == suite_name)
        if self.get_profile(profile_name) is None:
            raise ValueError(f"Profile '{profile_name}' not found.")
        suite["profiles"].append(profile_name)

    def remove_profile_from_suite(self, suite_name, profile_name):
        self._fail_if_requested("remove_profile_from_suite")
        suite = next(suite for suite in self.suites if suite["name"] == suite_name)
        suite["profiles"].remove(profile_name)

    def reorder_profile_in_suite(self, suite_name, profile_name, position):
        self._fail_if_requested("reorder_profile_in_suite")
        suite = next(suite for suite in self.suites if suite["name"] == suite_name)
        suite["profiles"].remove(profile_name)
        suite["profiles"].insert(max(0, min(position - 1, len(suite["profiles"]))), profile_name)


class _MountedSuitesApp(App):
    def __init__(self, screen):
        super().__init__()
        self._initial_screen = screen

    def on_mount(self):
        self.push_screen(self._initial_screen)


def _suite(name="demo", profiles=None, description=""):
    return {
        "name": name,
        "description": description,
        "created_at": "2026-09-28T00:00:00",
        "profiles": list(profiles or []),
    }


def _suite_profile(name):
    return {"name": name, "source": "source", "target": "target"}


def _suite_status(screen):
    return screen.query_one("#status-bar").render().plain


def test_suites_add_edit_delete_workflows_are_mounted_and_report_status():
    config = _MemorySuitesConfigManager()
    screen = SuitesScreen(config)
    app = _MountedSuitesApp(screen)

    async def exercise():
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.press("a")
            await pilot.pause()
            assert isinstance(app.screen, SuiteFormModal)
            app.screen.query_one("#input-name").value = "full"
            app.screen.query_one("#input-desc").value = "all profiles"
            await pilot.press("enter")
            await pilot.pause()
            assert config.get_suite("full")["description"] == "all profiles"
            assert "added" in _suite_status(screen).lower()

            await pilot.press("e")
            await pilot.pause()
            assert isinstance(app.screen, SuiteFormModal)
            app.screen.query_one("#input-desc").value = "updated"
            await pilot.press("enter")
            await pilot.pause()
            assert config.get_suite("full")["description"] == "updated"
            assert "saved" in _suite_status(screen).lower()

            await pilot.press("d")
            await pilot.pause()
            assert isinstance(app.screen, ConfirmModal)
            await pilot.press("y")
            await pilot.pause()
            assert config.get_suite("full") is None
            assert "deleted" in _suite_status(screen).lower()

    asyncio.run(exercise())


def test_suite_profile_membership_handles_empty_and_missing_profiles():
    config = _MemorySuitesConfigManager(
        profiles=[_suite_profile("available")],
        suites=[_suite("empty")],
    )
    screen = SuitesScreen(config)
    app = _MountedSuitesApp(screen)

    async def exercise():
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.press("m")
            await pilot.pause()
            manage = app.screen
            assert isinstance(manage, ManageProfilesScreen)
            assert manage._in_panel.listview is None
            await pilot.press("tab")
            await pilot.pause()
            await pilot.press("a")
            await pilot.pause()
            assert config.get_suite("empty")["profiles"] == ["available"]

    asyncio.run(exercise())


def test_missing_suite_profile_is_marked_and_removable():
    config = _MemorySuitesConfigManager(
        profiles=[_suite_profile("available")],
        suites=[_suite("demo", ["missing"])],
    )
    screen = SuitesScreen(config)
    app = _MountedSuitesApp(screen)

    async def exercise():
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.press("m")
            await pilot.pause()
            manage = app.screen
            missing_item = manage._in_panel.listview.highlighted_child
            assert missing_item.missing is True
            await pilot.press("d")
            await pilot.pause()
            assert config.get_suite("demo")["profiles"] == []

    asyncio.run(exercise())


def test_consecutive_suite_reorders_keep_the_moved_profile_selected():
    names = ["alpha", "bravo", "charlie", "delta"]
    config = _MemorySuitesConfigManager(
        profiles=[_suite_profile(name) for name in names],
        suites=[_suite("demo", names)],
    )
    screen = SuitesScreen(config)
    app = _MountedSuitesApp(screen)

    async def exercise():
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.press("m")
            await pilot.pause()
            manage = app.screen
            manage._in_panel.listview.index = 1

            await pilot.press("]")
            await pilot.pause()
            assert config.get_suite("demo")["profiles"] == ["alpha", "charlie", "bravo", "delta"]
            assert manage._selected_from(manage._in_panel.listview) == "bravo"

            await pilot.press("]")
            await pilot.pause()
            assert config.get_suite("demo")["profiles"] == ["alpha", "charlie", "delta", "bravo"]
            assert manage._selected_from(manage._in_panel.listview) == "bravo"

    asyncio.run(exercise())


def test_manage_panel_state_changes_only_after_successful_focus():
    config = _MemorySuitesConfigManager(
        profiles=[_suite_profile("available")],
        suites=[_suite("empty")],
    )
    screen = ManageProfilesScreen(config, "empty")
    app = _MountedSuitesApp(screen)

    async def exercise():
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.press("ctrl+2")
            await pilot.pause()
            assert screen._active_panel == "available"
            available_list = screen._available_panel.listview
            assert app.screen.focused is available_list

            for key in ("ctrl+1", "alt+1", "f1"):
                await pilot.press(key)
                await pilot.pause()
                assert screen._active_panel == "available"
                assert app.screen.focused is available_list

            await pilot.press("tab")
            await pilot.pause()
            assert screen._active_panel == "available"
            assert app.screen.focused is available_list

    asyncio.run(exercise())


@pytest.mark.parametrize("context", ["screen", "form", "confirmation", "manage"])
def test_suites_ctrl_c_exits_from_screen_and_mounted_modals(context):
    config = _MemorySuitesConfigManager(
        profiles=[_suite_profile("alpha")],
        suites=[_suite("demo", ["alpha"])],
    )
    screen = SuitesScreen(config)
    app = _MountedSuitesApp(screen)

    async def exercise():
        async with app.run_test() as pilot:
            await pilot.pause()
            if context != "screen":
                await pilot.press({"form": "e", "confirmation": "d", "manage": "m"}[context])
                await pilot.pause()
                expected = {
                    "form": SuiteFormModal,
                    "confirmation": ConfirmModal,
                    "manage": ManageProfilesScreen,
                }[context]
                assert isinstance(app.screen, expected)
            await pilot.press("ctrl+c")
            await pilot.pause()
            assert not pilot.app.is_running

    asyncio.run(exercise())


@pytest.mark.parametrize("operation", ["save_suite", "reorder_profile_in_suite"])
def test_suite_save_and_reorder_failures_are_reported_without_success(operation):
    profiles = [_suite_profile("alpha"), _suite_profile("bravo")]
    config = _MemorySuitesConfigManager(profiles=profiles, suites=[_suite("demo", ["alpha", "bravo"])])
    config.failures.add(operation)
    screen = SuitesScreen(config)
    app = _MountedSuitesApp(screen)

    async def exercise():
        async with app.run_test() as pilot:
            await pilot.pause()
            status_screen = screen
            if operation == "save_suite":
                await pilot.press("e")
                await pilot.pause()
                app.screen.query_one("#input-desc").value = "changed"
                await pilot.press("enter")
            else:
                await pilot.press("m")
                await pilot.pause()
                manage = app.screen
                status_screen = manage
                manage._in_panel.listview.index = 0
                await pilot.press("]")
            await pilot.pause()

            status = _suite_status(status_screen).lower()
            assert "error" in status or "failed" in status
            assert "saved" not in status and "moved" not in status
            assert config.get_suite("demo")["profiles"] == ["alpha", "bravo"]

    asyncio.run(exercise())


def test_suite_delete_failure_is_reported_without_claiming_success():
    config = _MemorySuitesConfigManager(suites=[_suite("demo")])
    config.failures.add("delete_suite")
    screen = SuitesScreen(config)
    app = _MountedSuitesApp(screen)

    async def exercise():
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.press("d")
            await pilot.pause()
            assert isinstance(app.screen, ConfirmModal)
            await pilot.press("y")
            await pilot.pause()

            status = _suite_status(screen).lower()
            assert "could not delete" in status or "error" in status
            assert "deleted" not in status
            assert config.get_suite("demo") is not None

    asyncio.run(exercise())
