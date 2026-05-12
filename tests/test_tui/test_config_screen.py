"""Config screen standards-compliance tests."""

from config import ConfigManager
from tui.screens.config import ConfigActionBar, ConfigActionsPanel, ConfigScreen, PathsPanel
from textual.containers import Container


SECTION_KEYS = {
    "ctrl+1": "focus_section_1",
    "ctrl+2": "focus_section_2",
    "ctrl+3": "focus_section_3",
    "alt+1": "focus_section_1",
    "alt+2": "focus_section_2",
    "alt+3": "focus_section_3",
    "f1": "focus_section_1",
    "f2": "focus_section_2",
    "f3": "focus_section_3",
}


class _StatusRecorder:
    def __init__(self):
        self.message = ""

    def update(self, message):
        self.message = message


def _bindings():
    return {binding.key: binding for binding in ConfigScreen.BINDINGS}


def test_config_screen_has_standard_bindings():
    bindings = _bindings()

    for key in [
        "ctrl+c", "escape", "q",
        "ctrl+1", "ctrl+2", "ctrl+3",
        "alt+1", "alt+2", "alt+3",
        "f1", "f2", "f3",
        "o", "v", "r", "shift+r",
    ]:
        assert key in bindings


def test_config_ctrl_c_routes_to_force_quit():
    assert _bindings()["ctrl+c"].action == "force_quit"


def test_config_section_bindings_are_hidden_and_focus_only():
    bindings = _bindings()

    for key, action in SECTION_KEYS.items():
        assert bindings[key].action == action
        assert bindings[key].show is False


def test_config_focus_methods_are_safe_when_unmounted(monkeypatch):
    screen = ConfigScreen(ConfigManager())
    status = _StatusRecorder()
    screen._status_bar = status

    for action_name in [
        "action_open_config_dir",
        "action_view_presets",
        "action_reset_presets",
        "action_reset_all",
    ]:
        monkeypatch.setattr(screen, action_name, lambda: (_ for _ in ()).throw(AssertionError(action_name)))

    assert screen._focus_widget("#missing", Container) is False
    screen.action_focus_section_1()
    assert status.message == "[dim]Paths section not focusable right now[/dim]"
    screen.action_focus_section_2()
    assert status.message == "[dim]Settings/actions section not focusable right now[/dim]"
    screen.action_focus_section_3()
    assert status.message == "[dim]Actions section not focusable right now[/dim]"


def test_config_sections_have_focus_targets():
    assert PathsPanel().id == "config-paths"
    assert PathsPanel().can_focus is True
    assert ConfigActionsPanel().id == "config-actions"
    assert ConfigActionsPanel().can_focus is True
    assert ConfigActionBar().id == "config-action-bar"
    assert ConfigActionBar().can_focus is True