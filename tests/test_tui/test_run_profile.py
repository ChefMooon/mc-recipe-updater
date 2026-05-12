"""Behavioral tests for the Run screen state machine and safety guards."""

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

    assert "post-run warnings" in captured["summary"].lower()
    assert "Post-run warnings" in captured["details"]
    assert captured["status"] == "Run complete with post-run warnings."


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
    monkeypatch.setattr(run_profile.RunProfileScreen, "app", property(lambda _self: app))

    screen.action_force_quit()

    assert app.exited is True


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
