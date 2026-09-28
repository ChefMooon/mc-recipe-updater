"""Backups screen standards-compliance tests."""

from config import ConfigManager
from backup import BackupEntry
from tui.screens.backups import BackupActionBar, BackupDetail, BackupList, BackupListItem, BackupsScreen
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


class _FakeApp:
    def __init__(self):
        self.exited = False
        self.popped = False
        self.pushed = []

    def exit(self):
        self.exited = True

    def pop_screen(self):
        self.popped = True

    def push_screen(self, screen, callback=None):
        self.pushed.append((screen, callback))


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


def test_backups_back_calls_pop_screen(monkeypatch):
    screen = BackupsScreen(ConfigManager())
    app = _FakeApp()
    monkeypatch.setattr(BackupsScreen, "app", property(lambda _self: app))

    screen.action_back()

    assert app.popped is True


def test_backups_force_quit_calls_exit(monkeypatch):
    screen = BackupsScreen(ConfigManager())
    app = _FakeApp()
    monkeypatch.setattr(BackupsScreen, "app", property(lambda _self: app))

    screen.action_force_quit()

    assert app.exited is True


def _entry(backup_id="backup-id", pinned=False, created_at="2026-01-01T00:00:00"):
    return BackupEntry(backup_id, f"{backup_id}.zip", "profile", "target", created_at, "success", pinned)


def test_backup_rows_include_unambiguous_backup_id():
    item = BackupListItem(_entry("backup-profile-unique"))
    label = next(item.compose())
    assert "backup-profile-unique" in label.render().plain


def test_view_restore_and_pin_failures_are_visible(monkeypatch):
    screen = BackupsScreen(ConfigManager())
    status = _StatusRecorder()
    app = _FakeApp()
    screen._status_bar = status
    monkeypatch.setattr(BackupsScreen, "app", property(lambda _self: app))
    monkeypatch.setattr(screen, "_selected_backup", lambda: _entry())

    class _BrokenManager:
        def view_backup_contents(self, _backup_id):
            raise OSError("zip unavailable")

        def pin_backup(self, _backup_id):
            raise OSError("registry read-only")

    screen.backup_manager = _BrokenManager()
    screen.action_view_backup()
    assert "zip unavailable" in status.message
    screen.action_restore_backup()
    assert "zip unavailable" in status.message
    screen.action_toggle_pin()
    assert "registry read-only" in status.message


def test_restore_confirmation_uses_selected_backup_id_and_reports_failure(monkeypatch):
    screen = BackupsScreen(ConfigManager())
    status = _StatusRecorder()
    app = _FakeApp()
    entry = _entry("restore-this")
    screen._status_bar = status
    monkeypatch.setattr(BackupsScreen, "app", property(lambda _self: app))
    monkeypatch.setattr(screen, "_selected_backup", lambda: entry)

    class _Manager:
        def view_backup_contents(self, backup_id):
            assert backup_id == entry.id
            return [("a.txt", 1)]

        def restore_backup(self, backup_id):
            assert backup_id == entry.id
            raise OSError("target is read-only")

    screen.backup_manager = _Manager()
    screen.action_restore_backup()
    modal, callback = app.pushed[-1]
    assert entry.id in modal._message
    callback(True)
    assert "target is read-only" in status.message


def test_delete_confirmation_uses_selected_id_force_flag_and_reports_failure(monkeypatch):
    screen = BackupsScreen(ConfigManager())
    status = _StatusRecorder()
    app = _FakeApp()
    entry = _entry("pinned-id", pinned=True)
    screen._status_bar = status
    monkeypatch.setattr(BackupsScreen, "app", property(lambda _self: app))
    monkeypatch.setattr(screen, "_selected_backup", lambda: entry)

    class _Manager:
        def delete_backup(self, backup_id, force=False):
            assert backup_id == entry.id
            assert force is True
            raise OSError("delete denied")

    screen.backup_manager = _Manager()
    screen.action_delete_backup()
    modal, callback = app.pushed[-1]
    assert entry.id in modal._message
    callback(True)
    assert "delete denied" in status.message


def test_prune_confirmation_aborts_when_candidate_set_changes(monkeypatch):
    screen = BackupsScreen(ConfigManager())
    status = _StatusRecorder()
    app = _FakeApp()
    entries = [
        _entry("old", created_at="2026-01-01T00:00:00"),
        _entry("new", created_at="2026-01-02T00:00:00"),
    ]
    screen._status_bar = status
    monkeypatch.setattr(BackupsScreen, "app", property(lambda _self: app))

    class _Manager:
        def list_backups(self):
            return entries

        def prune_backups(self, keep, include_pinned, expected_ids):
            assert expected_ids == {"old"}
            raise RuntimeError("Backup candidates changed after preview")

    screen.backup_manager = _Manager()
    screen._preview_prune({"keep": 1, "include_pinned": False})
    modal, callback = app.pushed[-1]
    assert "old" in modal._message
    callback(True)
    assert "changed after preview" in status.message