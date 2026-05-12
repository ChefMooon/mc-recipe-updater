"""Backups screen standards-compliance tests."""

from config import ConfigManager
from tui.screens.backups import BackupActionBar, BackupDetail, BackupList, BackupsScreen
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
    return {binding.key: binding for binding in BackupsScreen.BINDINGS}


def test_backups_screen_has_standard_bindings():
    bindings = _bindings()

    for key in [
        "ctrl+c", "escape", "q",
        "ctrl+1", "ctrl+2", "ctrl+3",
        "alt+1", "alt+2", "alt+3",
        "f1", "f2", "f3",
        "v", "r", "p", "d", "shift+p",
    ]:
        assert key in bindings


def test_backups_ctrl_c_routes_to_force_quit():
    assert _bindings()["ctrl+c"].action == "force_quit"


def test_backups_section_bindings_are_hidden_and_focus_only():
    bindings = _bindings()

    for key, action in SECTION_KEYS.items():
        assert bindings[key].action == action
        assert bindings[key].show is False


def test_backups_focus_methods_are_safe_when_unmounted(monkeypatch):
    screen = BackupsScreen(ConfigManager())
    status = _StatusRecorder()
    screen._status_bar = status

    for action_name in [
        "action_view_backup",
        "action_restore_backup",
        "action_toggle_pin",
        "action_delete_backup",
        "action_prune_backups",
    ]:
        monkeypatch.setattr(screen, action_name, lambda: (_ for _ in ()).throw(AssertionError(action_name)))

    assert screen._focus_widget("#missing", Container) is False
    screen.action_focus_section_1()
    screen.action_focus_section_2()
    screen.action_focus_section_3()

    assert status.message == "[dim]Actions section not focusable right now[/dim]"
    assert screen._pending_backup_id is None
    assert screen._pending_force_delete is False


def test_backups_sections_have_focus_targets():
    assert BackupList([]).id == "backup-list"
    assert BackupList([]).can_focus is True
    detail = BackupDetail(BackupsScreen(ConfigManager()).backup_manager)
    assert detail.id == "backup-detail"
    assert detail.can_focus is True
    assert BackupActionBar().id == "backup-actions"
    assert BackupActionBar().can_focus is True