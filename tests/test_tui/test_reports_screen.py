"""Reports screen standards-compliance tests."""

from config import ConfigManager
from tui.screens.reports import ReportActionBar, ReportDetail, ReportList, ReportsScreen
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

    def exit(self):
        self.exited = True

    def pop_screen(self):
        self.popped = True


def _bindings():
    return {binding.key: binding for binding in ReportsScreen.BINDINGS}


def test_reports_screen_has_standard_bindings():
    bindings = _bindings()

    for key in [
        "ctrl+c", "escape", "q",
        "ctrl+1", "ctrl+2", "ctrl+3",
        "alt+1", "alt+2", "alt+3",
        "f1", "f2", "f3",
        "/", "enter", "v", "d", "p",
    ]:
        assert key in bindings


def test_reports_ctrl_c_routes_to_force_quit():
    assert _bindings()["ctrl+c"].action == "force_quit"


def test_reports_section_bindings_are_hidden_and_focus_only():
    bindings = _bindings()

    for key, action in SECTION_KEYS.items():
        assert bindings[key].action == action
        assert bindings[key].show is False


def test_reports_focus_methods_are_safe_when_unmounted():
    screen = ReportsScreen(ConfigManager())
    status = _StatusRecorder()
    screen._status_bar = status

    assert screen._focus_widget("#missing", Container) is False
    screen.action_focus_section_1()
    screen.action_focus_section_2()
    screen.action_focus_section_3()

    assert status.message == "[dim]Actions section not focusable right now[/dim]"
    assert screen._pending_delete_path is None


def test_reports_action_back_closes_search_before_popping(monkeypatch):
    screen = ReportsScreen(ConfigManager())
    events = []

    class _SearchInput:
        display = True
        value = "profile"

    search = _SearchInput()
    screen._filter = "profile"
    monkeypatch.setattr(screen, "query_one", lambda *_args, **_kwargs: search)
    monkeypatch.setattr(screen, "_refresh_list", lambda: events.append("refresh"))

    screen.action_back()

    assert search.display is False
    assert search.value == ""
    assert screen._filter == ""
    assert events == ["refresh"]


def test_reports_sections_have_focus_targets():
    assert ReportList([]).id == "report-list"
    assert ReportList([]).can_focus is True
    assert ReportDetail().id == "report-detail"
    assert ReportDetail().can_focus is True
    assert ReportActionBar().id == "report-actions"
    assert ReportActionBar().can_focus is True


def test_reports_back_pops_screen_when_search_hidden(monkeypatch):
    screen = ReportsScreen(ConfigManager())
    app = _FakeApp()

    class _SearchInput:
        display = False
        value = ""

    monkeypatch.setattr(ReportsScreen, "app", property(lambda _self: app))
    monkeypatch.setattr(screen, "query_one", lambda *_args, **_kwargs: _SearchInput())

    screen.action_back()

    assert app.popped is True


def test_reports_force_quit_calls_exit(monkeypatch):
    screen = ReportsScreen(ConfigManager())
    app = _FakeApp()
    monkeypatch.setattr(ReportsScreen, "app", property(lambda _self: app))

    screen.action_force_quit()

    assert app.exited is True