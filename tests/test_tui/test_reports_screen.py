"""Reports screen standards-compliance tests."""

import asyncio
import threading
from pathlib import Path

from textual.app import App

import config as config_module
from reporter import Reporter, SuiteReporter
from config import ConfigManager
from tui.screens.reports import ReportActionBar, ReportDetail, ReportList, ReportListItem, ReportsScreen, _report_metadata
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


class _ReportsHost(App):
    def __init__(self, screen):
        super().__init__()
        self.reports_screen = screen

    def on_mount(self):
        self.push_screen(self.reports_screen)


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


def test_report_metadata_filters_outcomes_counts_and_inclusive_date_boundaries(monkeypatch, tmp_path):
    reports_dir = tmp_path / "reports"
    reports_dir.mkdir()
    monkeypatch.setattr(config_module, "REPORTS_DIR", reports_dir)
    outcomes = ("success", "partial", "failed", "cancelled", None)
    for index, outcome in enumerate(outcomes):
        path = reports_dir / f"run{index}_2026010{index + 1}_120000.txt"
        content = (
            "Added (2):\nUpdated (3):\nRemoved (4):\nUnchanged (5):\n"
            "Dirs added (6):\nDirs removed (7):\nErrors (1):\n"
        )
        if outcome:
            content = f"Outcome  : {outcome}\n" + content
        path.write_text(content, encoding="utf-8")

    screen = ReportsScreen(ConfigManager())
    screen._date_from = "2026-01-02"
    screen._date_to = "2026-01-04"
    screen._outcome_filter = "partial"
    matching = screen._load_reports()
    assert [report["name"] for report in matching] == ["run1"]
    assert matching[0]["counts"] == {
        "added": 2, "updated": 3, "removed": 4, "unchanged": 5,
        "dirs added": 6, "dirs removed": 7, "errors": 1,
    }

    screen._date_from = "2026-01-05"
    screen._date_to = "2026-01-05"
    screen._outcome_filter = "unknown"
    unknown = screen._load_reports()
    assert len(unknown) == 1
    assert unknown[0]["outcome"] == "unknown"

    for outcome in outcomes[:-1]:
        screen._date_from = ""
        screen._date_to = ""
        screen._outcome_filter = outcome
        assert {report["outcome"] for report in screen._load_reports()} == {outcome}


def test_report_read_handles_missing_invalid_utf8_and_large_files(tmp_path):
    screen = ReportsScreen(ConfigManager())
    missing = tmp_path / "missing.txt"
    invalid = tmp_path / "invalid.txt"
    large = tmp_path / "large.txt"
    invalid.write_bytes(b"\xff\xfe")
    large.write_text("Added (0):\n" + "details\n" * 250_000, encoding="utf-8")

    assert screen._read_report(missing)[0] is None
    assert "No such file" in screen._read_report(missing)[1]
    assert screen._read_report(invalid)[0] is None
    assert "decode" in screen._read_report(invalid)[1].lower()
    assert len(screen._read_report(large)[0]) > 1_000_000

    detail = ReportDetail()
    detail.update_detail(
        {"path": invalid, "timestamp": None, "name": "broken", "filename": invalid.name, "size": 2},
        error="invalid UTF-8",
    )
    assert "Could not read report: invalid UTF-8" in str(detail._content.render())


def test_reporters_persist_all_selected_outcomes_without_inferring_legacy(tmp_path, monkeypatch):
    import reporter

    monkeypatch.setattr(reporter, "REPORTS_DIR", tmp_path)
    results = {key: [] for key in ("added", "updated", "removed", "unchanged", "errors")}
    results.update({"dirs_added": [], "dirs_removed": []})
    for index, outcome in enumerate(("success", "partial", "failed", "cancelled")):
        path = Reporter(f"profile{index}", {"source": "src", "target": "tgt"}, results, outcome=outcome).save_report()
        report_text = Path(path).read_text(encoding="utf-8")
        assert f"Outcome  : {outcome}" in report_text
        assert "Errors (0):" in report_text
    suite_path = SuiteReporter("suite", [], outcome="cancelled").save_report()
    suite_text = Path(suite_path).read_text(encoding="utf-8")
    assert "Outcome  : cancelled" in suite_text
    assert set(_report_metadata(suite_text)["counts"].values()) == {0}
    skipped_suite_path = SuiteReporter(
        "incomplete-suite",
        [],
        outcome="failed",
        skipped_members=[("missing-profile", "Profile not found")],
    ).save_report()
    skipped_suite_text = Path(skipped_suite_path).read_text(encoding="utf-8")
    assert "Outcome  : failed" in skipped_suite_text
    assert "Skipped profiles (1):" in skipped_suite_text
    assert "missing-profile: Profile not found" in skipped_suite_text
    legacy_path = tmp_path / "legacy_20260101_000000.txt"
    legacy_path.write_text("Added (0):\n", encoding="utf-8")
    monkeypatch.setattr(config_module, "REPORTS_DIR", tmp_path)
    legacy_screen = ReportsScreen(ConfigManager())
    legacy_screen._outcome_filter = "unknown"
    assert [item["filename"] for item in legacy_screen._load_reports()] == [legacy_path.name]


def test_stale_report_worker_does_not_replace_selection_and_ui_stays_responsive(monkeypatch, tmp_path):
    async def exercise():
        await _exercise_stale_report_worker(monkeypatch, tmp_path)

    asyncio.run(exercise())


async def _exercise_stale_report_worker(monkeypatch, tmp_path):
    reports_dir = tmp_path / "reports"
    reports_dir.mkdir()
    monkeypatch.setattr(config_module, "REPORTS_DIR", reports_dir)
    slow_path = reports_dir / "slow_20260102_120000.txt"
    current_path = reports_dir / "current_20260101_120000.txt"
    slow_path.write_text("Added (1): slow details", encoding="utf-8")
    current_path.write_text("Added (1): current details", encoding="utf-8")
    screen = ReportsScreen(ConfigManager())
    block_reads = threading.Event()
    read_started = threading.Event()
    release_read = threading.Event()
    read_report = screen._read_report

    def delayed_read(path):
        if block_reads.is_set() and path == slow_path:
            read_started.set()
            release_read.wait(3)
        return read_report(path)

    monkeypatch.setattr(screen, "_read_report", delayed_read)
    app = _ReportsHost(screen)
    try:
        async with app.run_test() as pilot:
            await pilot.pause(0.2)
            block_reads.set()
            slow_report = next(report for report in screen._reports if report["path"] == slow_path)
            current_report = next(report for report in screen._reports if report["path"] == current_path)
            stale_task = asyncio.create_task(
                screen.on_list_view_highlighted(type("Highlight", (), {"item": ReportListItem(slow_report)})())
            )
            assert await asyncio.to_thread(read_started.wait, 1)
            await screen.on_list_view_highlighted(
                type("Highlight", (), {"item": ReportListItem(current_report)})()
            )
            await pilot.press("ctrl+2")
            assert screen.app.focused is screen.query_one("#report-detail")
            release_read.set()
            await stale_task
            assert "current details" in str(screen._detail_panel._content.render())
            assert "slow details" not in str(screen._detail_panel._content.render())
    finally:
        release_read.set()


def test_report_prune_preview_and_delete_failures_are_visible():
    screen = ReportsScreen(ConfigManager())
    status = _StatusRecorder()

    class _BrokenReportManager:
        def prune_reports(self, **_kwargs):
            raise OSError("reports folder is read-only")

    screen.report_manager = _BrokenReportManager()
    screen._status_bar = status
    screen._preview_prune(1)
    assert "Prune preview failed" in status.message
    screen._on_prune_confirmed(True, 1)
    assert "Prune failed" in status.message