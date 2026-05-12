"""
TUI screen tests.
"""

import pytest
from tui.screens.suites import ManageProfilesScreen, SuiteActionBar, SuitesScreen
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

        class _OldPanel:
            def __init__(self, panel_id: str):
                self.id = panel_id

            def remove(self):
                events.append(("remove", self.id))

        class _DummyRow:
            def mount(self, widget):
                mounted.append(widget)

        class _NewPanel:
            def __init__(self):
                self.id = None

        screen._in_panel = _OldPanel("in-suite-panel")
        screen._available_panel = _OldPanel("available-panel")
        monkeypatch.setattr(screen, "query_one", lambda *_a, **_k: _DummyRow())
        monkeypatch.setattr(screen, "_build_in_panel", lambda: _NewPanel())
        monkeypatch.setattr(screen, "_build_available_panel", lambda: _NewPanel())
        monkeypatch.setattr(screen, "_sync_active_panel_classes", lambda: None)
        monkeypatch.setattr(screen, "_focus_active_list", lambda: None)

        screen._refresh()

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
