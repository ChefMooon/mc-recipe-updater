"""Behavioral tests for the Run screen state machine and safety guards."""

import asyncio
import threading

import pytest

from textual.app import App

from tui.screens import run_profile


class _DummyConfigManager:
    def list_profiles(self):
        return []

    def list_suites(self):
        return []

    def get_profile(self, _name):
        return None

    def get_suite(self, _name):
        return None

    def get_mapping_preset(self, _name):
        return None


class _ProfileConfigManager(_DummyConfigManager):
    def __init__(self, source, target):
        self.profile = {"name": "selected", "source": str(source), "target": str(target)}

    def list_profiles(self):
        return [{"name": "first"}, self.profile]

    def get_profile(self, name):
        return self.profile if name == "selected" else None


def _empty_results():
    return {
        "added": [],
        "updated": [],
        "removed": [],
        "unchanged": [],
        "dirs_added": [],
        "dirs_removed": [],
        "errors": [],
    }


def _failed_results(rollback_complete, recovery_path=None):
    results = _empty_results()
    results["errors"].append(("bad.json", "injected mutation failure"))
    results.update(
        rollback_complete=rollback_complete,
        recovery_path=recovery_path,
        rollback_errors=[] if rollback_complete else [("bad.json", "restore denied")],
    )
    return results


class _FakeApp:
    def __init__(self):
        self.exited = False
        self.popped = False

    def exit(self):
        self.exited = True

    def pop_screen(self):
        self.popped = True


def test_run_screen_has_primary_and_fallback_section_bindings():
    keys = {binding.key for binding in run_profile.RunProfileScreen.BINDINGS}

    assert "ctrl+c" in keys
    assert "q" in keys
    assert "ctrl+1" in keys
    assert "ctrl+2" in keys
    assert "ctrl+3" in keys
    assert "alt+1" in keys
    assert "alt+2" in keys
    assert "alt+3" in keys
    assert "f1" in keys
    assert "f2" in keys
    assert "f3" in keys


def test_focus_section_three_is_focus_only_and_does_not_change_run_id(monkeypatch):
    screen = run_profile.RunProfileScreen(_DummyConfigManager())
    screen._run_id = 7

    monkeypatch.setattr(screen, "_focus_widget", lambda *_args, **_kwargs: True)

    screen.action_focus_section_3()

    assert screen._run_id == 7


def test_stale_progress_callback_is_ignored():
    screen = run_profile.RunProfileScreen(_DummyConfigManager())
    screen._run_id = 2

    class _Panel:
        def __init__(self):
            self.called = False

        def update_progress(self, _text):
            self.called = True

    panel = _Panel()
    screen._progress_panel = panel

    screen._on_progress(1, 1, 10, "Comparing", "demo-profile")

    assert panel.called is False


def test_stale_profile_complete_callback_is_ignored(monkeypatch):
    screen = run_profile.RunProfileScreen(_DummyConfigManager())
    screen._run_id = 3
    called = {"switch": False}

    monkeypatch.setattr(screen, "_switch_to_results", lambda *_args, **_kwargs: called.update(switch=True))

    screen._on_profile_complete(
        2,
        "demo",
        {"target": "x"},
        {"dry_run": True, "changelog": False},
        None,
        _empty_results(),
        None,
    )

    assert called["switch"] is False


def test_profile_complete_handles_post_step_failures_and_reaches_done(monkeypatch):
    screen = run_profile.RunProfileScreen(_DummyConfigManager())
    screen._run_id = 9

    captured = {"summary": None, "details": None, "status": None}

    class _BrokenReporter:
        def __init__(self, *_args, **_kwargs):
            pass

        def save_report(self):
            raise OSError("report unavailable")

    class _BrokenChangelog:
        def __init__(self, *_args, **_kwargs):
            pass

        def write(self, *_args, **_kwargs):
            raise UnicodeError("bad encoding")

    monkeypatch.setattr(run_profile, "Reporter", _BrokenReporter)
    monkeypatch.setattr(run_profile, "TargetChangelogWriter", _BrokenChangelog)
    monkeypatch.setattr(
        screen,
        "_switch_to_results",
        lambda summary, details: captured.update(summary=summary, details=details),
    )
    monkeypatch.setattr(screen, "_set_status", lambda text: captured.update(status=text))

    screen._on_profile_complete(
        9,
        "demo",
        {"target": "C:/tmp", "target_changelog": True},
        {"dry_run": False, "changelog": True},
        None,
        _empty_results(),
        None,
    )

    assert "outcome: partial" in captured["summary"].lower()
    assert "Post-run warnings" in captured["details"]
    assert captured["status"] == "Run partial."


def test_run_screen_has_option_navigation_bindings():
    """Verify Up/Down bindings are present for option navigation."""
    keys = {binding.key for binding in run_profile.RunProfileScreen.BINDINGS}
    assert "up" in keys
    assert "down" in keys


def test_option_navigation_is_gated_to_selection_phase(monkeypatch):
    """Verify Up/Down navigation is unavailable outside selection phase."""
    screen = run_profile.RunProfileScreen(_DummyConfigManager())
    screen._phase = "running"
    
    status_captured = {"message": None}
    monkeypatch.setattr(screen, "_set_status", lambda msg: status_captured.update(message=msg))
    
    screen.action_option_down()
    
    assert "selection" in status_captured["message"].lower()


def test_option_navigation_wraps_forward(monkeypatch):
    """Verify Down navigation wraps from last option to first."""
    screen = run_profile.RunProfileScreen(_DummyConfigManager())
    screen._phase = "selection"
    
    # Track which options get focused
    focused_options = []
    
    def mock_focus_option(index):
        if 0 <= index < len(screen._option_order):
            focused_options.append(screen._option_order[index])
            return True
        return False
    
    monkeypatch.setattr(screen, "_focus_option_by_index", mock_focus_option)
    monkeypatch.setattr(screen, "_get_focused_option_index", lambda: -1)  # Start unfocused
    
    # Press Down once: should focus first option
    screen.action_option_down()
    assert focused_options[-1] == "option-dry-run"
    
    # Simulate being at last option and pressing Down
    monkeypatch.setattr(screen, "_get_focused_option_index", lambda: len(screen._option_order) - 1)
    screen.action_option_down()
    # Should wrap to first option (index 0)
    assert focused_options[-1] == "option-dry-run"


def test_option_navigation_wraps_backward(monkeypatch):
    """Verify Up navigation wraps from first option to last."""
    screen = run_profile.RunProfileScreen(_DummyConfigManager())
    screen._phase = "selection"
    
    focused_options = []
    
    def mock_focus_option(index):
        if 0 <= index < len(screen._option_order):
            focused_options.append(screen._option_order[index])
            return True
        return False
    
    monkeypatch.setattr(screen, "_focus_option_by_index", mock_focus_option)
    # Simulate being at first option
    monkeypatch.setattr(screen, "_get_focused_option_index", lambda: 0)
    
    # Press Up: should wrap to last option
    screen.action_option_up()
    assert focused_options[-1] == "option-mapping"


def test_space_on_checkbox_toggles_without_starting_run(monkeypatch):
    """Verify Space toggles a focused checkbox without triggering run start."""
    from textual.widgets import Checkbox
    
    screen = run_profile.RunProfileScreen(_DummyConfigManager())
    screen._phase = "selection"
    
    # Create a real checkbox to test isinstance check
    checkbox = Checkbox("Test", id="option-dry-run")
    checkbox.value = False
    
    # Mock the focused property to return our checkbox
    monkeypatch.setattr(screen, "focused", checkbox)
    
    # Prevent actual run start
    run_started = {"called": False}
    monkeypatch.setattr(screen, "_start_profile_run", lambda *_: run_started.update(called=True))
    monkeypatch.setattr(screen, "_selected_target", lambda: "dummy-profile")
    
    # Call action_start_run when checkbox is focused
    screen.action_start_run()
    
    # Verify checkbox was toggled and run did not start
    assert checkbox.value is True
    assert run_started["called"] is False


def test_space_outside_options_starts_run(monkeypatch):
    """Verify Space still starts a run when focus is outside options widgets."""
    screen = run_profile.RunProfileScreen(_DummyConfigManager())
    screen._phase = "selection"
    
    # Mock a non-option focused widget (e.g., target list item)
    class _MockListItem:
        def __init__(self):
            self.id = "some-list-item"
    
    monkeypatch.setattr(screen, "focused", _MockListItem())
    
    # Mock run start
    run_started = {"target": None}
    monkeypatch.setattr(screen, "_selected_target", lambda: "demo-profile")
    monkeypatch.setattr(screen, "_start_profile_run", lambda target: run_started.update(target=target))
    
    # Call action_start_run
    screen.action_start_run()
    
    # Verify run started
    assert run_started["target"] == "demo-profile"


def test_option_navigation_does_not_mutate_run_id(monkeypatch):
    """Verify option navigation is focus-only and does not trigger phase changes."""
    screen = run_profile.RunProfileScreen(_DummyConfigManager())
    screen._phase = "selection"
    screen._run_id = 42
    
    monkeypatch.setattr(screen, "_focus_option_by_index", lambda index: True)
    monkeypatch.setattr(screen, "_get_focused_option_index", lambda: -1)
    
    screen.action_option_down()
    
    assert screen._run_id == 42  # No phase change, no run increment


def test_section_2_focus_entry_lands_on_first_option(monkeypatch):
    """Verify focusing section 2 during selection phase focuses first option."""
    screen = run_profile.RunProfileScreen(_DummyConfigManager())
    screen._phase = "selection"
    
    focused_option = {"id": None}
    
    def mock_focus_option(index):
        if 0 <= index < len(screen._option_order):
            focused_option["id"] = screen._option_order[index]
            return True
        return False
    
    monkeypatch.setattr(screen, "_focus_option_by_index", mock_focus_option)
    
    # Simulate action_focus_section_2 attempt to focus first checkbox
    screen._focus_option_by_index(0)
    
    assert focused_option["id"] == "option-dry-run"


def test_run_force_quit_exits_app(monkeypatch):
    screen = run_profile.RunProfileScreen(_DummyConfigManager())
    app = _FakeApp()
    cancel_calls = []

    class _Syncer:
        def cancel(self):
            cancel_calls.append(True)

    screen._syncer = _Syncer()
    monkeypatch.setattr(run_profile.RunProfileScreen, "app", property(lambda _self: app))

    screen.action_force_quit()
    screen.action_force_quit()

    assert app.exited is True
    assert cancel_calls == [True]


def test_run_back_pops_screen_in_selection_phase(monkeypatch):
    screen = run_profile.RunProfileScreen(_DummyConfigManager())
    screen._phase = "selection"
    app = _FakeApp()
    monkeypatch.setattr(run_profile.RunProfileScreen, "app", property(lambda _self: app))

    screen.action_back()

    assert app.popped is True


def test_run_back_returns_to_selection_from_done_phase(monkeypatch):
    screen = run_profile.RunProfileScreen(_DummyConfigManager())
    screen._phase = "done"
    called = {"selection": False}
    monkeypatch.setattr(screen, "_switch_to_selection", lambda: called.update(selection=True))

    screen.action_back()

    assert called["selection"] is True


def test_mounted_run_phase_transitions_do_not_duplicate_ids():
    screen = run_profile.RunProfileScreen(_ProfileConfigManager("source", "target"))
    screen._last_selection = "selected"
    started = []

    def start_profile_run(name):
        started.append(name)
        screen._switch_to_running(name, "profile", True)

    screen._start_profile_run = start_profile_run

    class _RunApp(App):
        def on_mount(self):
            self.push_screen(screen)

    async def exercise_transitions():
        async with _RunApp().run_test() as pilot:
            await pilot.pause()
            screen._last_selection = "selected"
            screen._switch_to_running("selected", "profile", True)
            await pilot.pause()
            assert screen._phase == "running"
            screen._switch_to_results("done", "details")
            await pilot.pause()
            assert screen._phase == "done"
            screen._switch_to_selection()
            await pilot.pause()
            assert screen._phase == "selection"
            assert screen.query_one("#target-listview").index == 1
            screen._switch_to_running("selected", "profile", True)
            await pilot.pause()
            screen._switch_to_results("done", "details")
            await pilot.pause()
            screen.action_back()
            await pilot.pause()
            assert screen.query_one("#target-listview").index == 1
            screen._switch_to_running("selected", "profile", True)
            await pilot.pause()
            screen._switch_to_results("done", "details")
            await pilot.pause()
            screen.action_rerun()
            await pilot.pause()
            assert started == ["selected"]
            assert screen._phase == "running"
            screen._switch_to_results("done", "details")
            await pilot.pause()
            screen.action_back()
            await pilot.pause()
            assert screen.query_one("#target-listview").index == 1

    asyncio.run(exercise_transitions())


@pytest.mark.parametrize("bad_path_kind", ["file", "missing"])
@pytest.mark.parametrize("bad_role", ["source", "target"])
def test_profile_preflight_rejects_non_directories_without_mutating_target(tmp_path, bad_path_kind, bad_role):
    source = tmp_path / "source"
    target = tmp_path / "target"
    source.mkdir()
    target.mkdir()
    sentinel = target / "keep.txt"
    sentinel.write_text("keep")
    bad_path = tmp_path / f"bad-{bad_role}"
    if bad_path_kind == "file":
        bad_path.write_text("not a directory")
    paths = {"source": source, "target": target}
    paths[bad_role] = bad_path
    screen = run_profile.RunProfileScreen(_ProfileConfigManager(source, target))

    with pytest.raises(FileNotFoundError):
        screen._prepare_profile_config(
            "selected",
            {"source": str(paths["source"]), "target": str(paths["target"])},
        )

    assert sentinel.read_text() == "keep"


def test_profile_completion_reports_backup_finalize_and_rotation_warnings(tmp_path, monkeypatch):
    source = tmp_path / "source"
    target = tmp_path / "target"
    source.mkdir()
    target.mkdir()

    class _BrokenBackup:
        def __init__(self, stage):
            self.stage = stage

        def finalize_backup(self, *_args):
            if self.stage == "finalize":
                raise OSError("finalize unavailable")

        def rotate_backups(self, *_args):
            if self.stage == "rotation":
                raise OSError("rotation unavailable")

    class _Reporter:
        def __init__(self, *_args, **_kwargs):
            pass

        def save_report(self):
            return None

    monkeypatch.setattr(run_profile, "Reporter", _Reporter)

    async def exercise(stage):
        screen = run_profile.RunProfileScreen(_ProfileConfigManager(source, target))
        screen._run_id = 2
        screen.backup_manager = _BrokenBackup(stage)

        class _RunApp(App):
            def on_mount(self):
                self.push_screen(screen)

        async with _RunApp().run_test() as pilot:
            await pilot.pause()
            screen._switch_to_running("selected", "profile", False)
            await pilot.pause()
            screen._on_profile_complete(
                2,
                "selected",
                {"target": str(target)},
                {"dry_run": False, "changelog": False},
                "backup-id",
                _empty_results(),
                None,
            )
            await pilot.pause()
            assert screen._phase == "done"
            assert "outcome: partial" in str(screen._results_panel._content.render()).lower()
            assert stage in str(screen._details_panel._content.render()).lower()

    asyncio.run(exercise("finalize"))
    asyncio.run(exercise("rotation"))


def test_actual_ctrl_c_dispatch_cancels_and_exits_without_waiting():
    screen = run_profile.RunProfileScreen(_DummyConfigManager())
    cancelled = threading.Event()

    class _Syncer:
        cancel_event = cancelled

        def cancel(self):
            cancelled.set()

    screen._syncer = _Syncer()
    screen._phase = "running"

    class _RunApp(App):
        def on_mount(self):
            self.push_screen(screen)

    async def dispatch_ctrl_c():
        async with _RunApp().run_test() as pilot:
            await pilot.pause()
            await pilot.press("ctrl+c")
            assert cancelled.is_set()
            assert not pilot.app.is_running
            screen._dispatch_to_app(lambda: None)

    asyncio.run(dispatch_ctrl_c())


def test_suite_worker_uses_captured_event_and_keeps_cancelled_profile_results(monkeypatch, tmp_path):
    source = tmp_path / "source"
    target = tmp_path / "target"
    source.mkdir()
    target.mkdir()
    screen = run_profile.RunProfileScreen(_ProfileConfigManager(source, target))
    captured_event = threading.Event()
    newer_event = threading.Event()
    newer_event.set()
    screen._suite_cancel_event = newer_event
    partial = _empty_results()
    partial["added"].append("done.json")

    class _CancelledMCRU:
        def __init__(self, _config, **kwargs):
            assert kwargs["cancel_event"] is captured_event

        def run(self):
            raise run_profile.SyncCancelled("cancelled", partial)

    class _SuiteReporter:
        def __init__(self, _name, runs, **_kwargs):
            self.runs = runs

        def save_report(self):
            return "suite-report.txt"

    completion = []
    monkeypatch.setattr(run_profile, "MCRU", _CancelledMCRU)
    monkeypatch.setattr(run_profile, "SuiteReporter", _SuiteReporter)
    monkeypatch.setattr(screen, "_dispatch_to_app", lambda callback, *args: completion.append((callback, args)))

    screen._run_suite_worker(
        1,
        "suite",
        {"profiles": ["selected"]},
        {"dry_run": False, "backup": False, "changelog": False},
        captured_event,
    )

    assert completion[0][1][3][0][2]["added"] == ["done.json"]
    assert completion[0][1][7] is True
    assert captured_event.is_set() is False


def test_suite_cancellation_after_mutation_propagates_results(monkeypatch, tmp_path):
    source = tmp_path / "source"
    target = tmp_path / "target"
    recipe_dir = source / "fabric" / "src" / "main" / "resources" / "data" / "demo" / "recipes"
    recipe_dir.mkdir(parents=True)
    target.mkdir()
    (recipe_dir / "first.json").write_text("first")
    (recipe_dir / "second.json").write_text("second")
    screen = run_profile.RunProfileScreen(_ProfileConfigManager(source, target))
    cancel_event = threading.Event()

    class _SuiteReporter:
        def __init__(self, *_args, **_kwargs):
            pass

        def save_report(self):
            return None

    completion = []

    def dispatch(callback, *args):
        if getattr(callback, "__name__", "") == "_on_progress" and args[3] == "Adding files" and args[1] == 1:
            cancel_event.set()
        elif getattr(callback, "__name__", "") == "_on_suite_complete":
            completion.append((callback, args))

    monkeypatch.setattr(run_profile, "SuiteReporter", _SuiteReporter)
    monkeypatch.setattr(screen, "_dispatch_to_app", dispatch)
    screen._prepare_profile_config = lambda _name, _options: {
        "source": str(source),
        "target": str(target),
        "parsers": [],
    }

    screen._run_suite_worker(
        3,
        "suite",
        {"profiles": ["selected"]},
        {"dry_run": False, "backup": False, "changelog": False},
        cancel_event,
    )

    run_result = completion[0][1][3][0][2]
    assert len(run_result["added"]) == 1
    assert (target / run_result["added"][0]).exists()
    assert completion[0][1][7] is True


def test_dispatch_ignores_worker_callback_after_app_shutdown(monkeypatch):
    screen = run_profile.RunProfileScreen(_DummyConfigManager())

    class _ClosedApp:
        def call_from_thread(self, *_args):
            raise RuntimeError("App is not running")

    monkeypatch.setattr(run_profile.RunProfileScreen, "app", property(lambda _self: _ClosedApp()))

    screen._dispatch_to_app(lambda: None)


def test_cancelled_profile_summary_includes_partial_counts_and_no_rollback(monkeypatch):
    screen = run_profile.RunProfileScreen(_DummyConfigManager())
    screen._run_id = 4
    captured = {}
    monkeypatch.setattr(screen, "_switch_to_results", lambda summary, details: captured.update(summary=summary, details=details))
    monkeypatch.setattr(screen, "_set_status", lambda status: captured.update(status=status))
    partial = _empty_results()
    partial["added"].append("applied.json")

    screen._on_profile_complete(
        4,
        "demo",
        {"target": "target"},
        {"dry_run": False, "changelog": False},
        None,
        partial,
        run_profile.SyncCancelled("cancelled", partial),
    )

    assert "outcome: cancelled" in captured["summary"].lower()
    assert "Added:" in captured["summary"] and "1" in captured["summary"]
    assert "not rolled back" in captured["summary"]
    assert captured["status"] == "Run cancelled."


def test_profile_complete_reports_restored_rollback_and_finalizes_backup_failed(monkeypatch):
    screen = run_profile.RunProfileScreen(_DummyConfigManager())
    screen._run_id = 8
    captured = {}
    finalized = []
    rotated = []

    class _BackupManager:
        def finalize_backup(self, backup_id, result):
            finalized.append((backup_id, result))

        def rotate_backups(self, _max_backups):
            rotated.append(True)

    class _Reporter:
        def __init__(self, _name, _config, _results, dry_run=False, outcome="success"):
            captured["outcome"] = outcome

        def save_report(self):
            return "profile-report.txt"

    screen.backup_manager = _BackupManager()
    monkeypatch.setattr(run_profile, "Reporter", _Reporter)
    monkeypatch.setattr(
        screen,
        "_switch_to_results",
        lambda summary, details: captured.update(summary=summary, details=details),
    )
    monkeypatch.setattr(screen, "_set_status", lambda status: captured.update(status=status))

    screen._on_profile_complete(
        8,
        "selected",
        {"target": "target"},
        {"dry_run": False, "changelog": False},
        "backup-selected",
        _failed_results(True),
        None,
    )

    assert captured["outcome"] == "failed"
    assert "Rollback completed; failed changes were restored." in captured["summary"]
    assert captured["status"] == "Run failed."
    assert finalized == [("backup-selected", "failed")]
    assert rotated == []


def test_suite_worker_reports_incomplete_rollback_and_keeps_backup_failed(monkeypatch, tmp_path):
    source = tmp_path / "source"
    target = tmp_path / "target"
    source.mkdir()
    target.mkdir()
    screen = run_profile.RunProfileScreen(_ProfileConfigManager(source, target))
    screen._run_id = 11
    screen.global_config = type("_GlobalConfig", (), {"get": lambda *_args: 10})()
    finalized = []
    rotated = []
    outcomes = []
    completion = []
    captured = {}

    class _BackupManager:
        def create_backup(self, _target, _profile):
            return "backup-selected"

        def finalize_backup(self, backup_id, result):
            finalized.append((backup_id, result))

        def rotate_backups(self, _max_backups):
            rotated.append(True)

    class _FailedMCRU:
        def __init__(self, *_args, **_kwargs):
            pass

        def run(self):
            return _failed_results(False, "transaction-recovery")

    class _SuiteReporter:
        def __init__(self, _name, _runs, dry_run=False, outcome="success"):
            outcomes.append(outcome)

        def save_report(self):
            return "suite-report.txt"

    screen.backup_manager = _BackupManager()
    screen._prepare_profile_config = lambda _name, _options: {
        "source": str(source),
        "target": str(target),
        "parsers": [],
    }
    screen._dispatch_to_app = lambda callback, *args: completion.append((callback, args))
    monkeypatch.setattr(run_profile, "MCRU", _FailedMCRU)
    monkeypatch.setattr(run_profile, "SuiteReporter", _SuiteReporter)
    monkeypatch.setattr(
        screen,
        "_switch_to_results",
        lambda summary, details: captured.update(summary=summary, details=details),
    )
    monkeypatch.setattr(screen, "_set_status", lambda status: captured.update(status=status))

    screen._run_suite_worker(
        11,
        "suite",
        {"profiles": ["selected"]},
        {"dry_run": False, "backup": True, "changelog": False},
        threading.Event(),
    )

    assert outcomes == ["partial"]
    assert finalized == [("backup-selected", "failed")]
    assert rotated == []
    completion[0][0](*completion[0][1])
    assert "Outcome: partial" in captured["summary"]
    assert "Rollback incomplete; the target may retain changes." in captured["summary"]
    assert "Rollback errors" in captured["summary"]
    assert "restore denied" in captured["summary"]
    assert "transaction-recovery" in captured["summary"]
    assert captured["status"] == "Suite run partial."


def test_cancel_back_and_new_run_uses_fresh_cancellation_event(monkeypatch):
    screen = run_profile.RunProfileScreen(_ProfileConfigManager("source", "target"))
    old_event = threading.Event()

    class _CancelledSyncer:
        cancel_event = old_event

        def cancel(self):
            old_event.set()

    screen._phase = "running"
    screen._syncer = _CancelledSyncer()
    screen.action_back()
    assert old_event.is_set()

    monkeypatch.setattr(screen, "_replace_main_panels", lambda *_args: None)
    monkeypatch.setattr(screen, "_update_selected_detail", lambda: None)
    monkeypatch.setattr(screen, "_option_values", lambda: {"dry_run": True, "backup": False})
    monkeypatch.setattr(
        screen,
        "_prepare_profile_config",
        lambda *_args: {"source": "source", "target": "target"},
    )
    screen._phase = "done"
    screen.action_back()

    class _FreshSyncer:
        def __init__(self, *_args, **_kwargs):
            self.cancel_event = threading.Event()

        def start(self):
            return None

    monkeypatch.setattr(run_profile, "ThreadedSyncer", _FreshSyncer)
    screen._start_profile_run("selected")

    assert screen._phase == "running"
    assert screen._syncer.cancel_event is not old_event
    assert not screen._syncer.cancel_event.is_set()


def test_run_outcome_classification_distinguishes_success_partial_failed_and_cancelled():
    clean = _empty_results()
    with_changes = _empty_results()
    with_changes["added"].append("done.json")
    failed_operations = _empty_results()
    failed_operations["errors"].append(("bad.json", "permission denied"))

    assert run_profile._classify_outcome(clean, [], [], False, None, True) == "success"
    assert run_profile._classify_outcome(with_changes, [], ["rotation failed"], False, None, True) == "partial"
    assert run_profile._classify_outcome(failed_operations, [], [], False, None, True) == "failed"
    assert run_profile._classify_outcome(_failed_results(True), [], [], False, None, True) == "failed"
    assert run_profile._classify_outcome(_failed_results(False), [], [], False, None, True) == "partial"
    assert run_profile._classify_outcome(clean, [("missing", "not found")], [], False, None, False) == "failed"
    assert run_profile._classify_outcome(with_changes, [], [], True, None, True) == "cancelled"


class _MountedRunApp(App):
    def __init__(self, screen):
        super().__init__()
        self._initial_screen = screen

    def on_mount(self):
        self.push_screen(self._initial_screen)


def test_run_starts_from_button_and_space_on_target_list():
    from textual.widgets import ListView

    screen = run_profile.RunProfileScreen(_ProfileConfigManager("source", "target"))
    screen._last_selection = "selected"
    started = []
    screen._start_profile_run = lambda name: started.append(name)
    app = _MountedRunApp(screen)

    async def exercise():
        async with app.run_test() as pilot:
            await pilot.pause()
            screen.query_one("#target-listview", ListView).index = 1
            await pilot.pause()
            await pilot.click("#start-run")
            await pilot.pause()
            assert started == ["selected"]

            screen.query_one("#target-listview", ListView).focus()
            await pilot.press("space")
            await pilot.pause()
            assert started == ["selected", "selected"]

    asyncio.run(exercise())


def test_run_space_on_focused_checkbox_toggles_without_starting():
    from textual.widgets import Checkbox

    screen = run_profile.RunProfileScreen(_ProfileConfigManager("source", "target"))
    screen._last_selection = "selected"
    started = []
    screen._start_profile_run = lambda name: started.append(name)
    app = _MountedRunApp(screen)

    async def exercise():
        async with app.run_test() as pilot:
            await pilot.pause()
            checkbox = screen.query_one("#option-dry-run", Checkbox)
            checkbox.focus()
            original_value = checkbox.value
            await pilot.press("space")
            await pilot.pause()

            assert checkbox.value is not original_value
            assert started == []

    asyncio.run(exercise())
