"""Config screen standards-compliance tests."""

import asyncio
import json

import pytest

import config as config_module
import tui.screens.config as config_screen_module
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


def test_config_back_calls_pop_screen(monkeypatch):
    screen = ConfigScreen(ConfigManager())
    app = _FakeApp()
    monkeypatch.setattr(ConfigScreen, "app", property(lambda _self: app))

    screen.action_back()

    assert app.popped is True


def test_config_force_quit_calls_exit(monkeypatch):
    screen = ConfigScreen(ConfigManager())
    app = _FakeApp()
    monkeypatch.setattr(ConfigScreen, "app", property(lambda _self: app))

    screen.action_force_quit()

    assert app.exited is True


def _patch_config_files(monkeypatch, tmp_path):
    config_dir = tmp_path / "mcru"
    profiles = config_dir / "profiles.json"
    suites = config_dir / "suites.json"
    global_settings = config_dir / "config.json"
    mapping = config_dir / "mapping-presets.json"
    bundled = tmp_path / "bundled-mapping.json"
    bundled.write_text('{"presets": {}}', encoding="utf-8")
    for module in (config_module, config_screen_module):
        monkeypatch.setattr(module, "CONFIG_DIR", config_dir)
        monkeypatch.setattr(module, "CONFIG_FILE", profiles)
        monkeypatch.setattr(module, "SUITES_FILE", suites)
        monkeypatch.setattr(module, "GLOBAL_CONFIG_FILE", global_settings)
        monkeypatch.setattr(module, "DEFAULT_MAPPING_FILE", mapping)
        monkeypatch.setattr(
            module,
            "read_bundled_mapping_presets",
            lambda: bundled.read_text(encoding="utf-8"),
        )
    return config_dir, profiles, suites, global_settings, mapping, bundled


def test_malformed_profile_and_suite_files_are_preserved_and_recoverable(monkeypatch, tmp_path):
    _, profiles, suites, _, _, _ = _patch_config_files(monkeypatch, tmp_path)
    profiles.parent.mkdir()
    original_profiles = b"\xffinvalid profile json"
    original_suites = b'{"suites": {"wrong": "shape"}}'
    profiles.write_bytes(original_profiles)
    suites.write_bytes(original_suites)

    manager = ConfigManager()

    assert manager.profiles == []
    assert manager.suites == []
    assert len(manager.recovery_errors) == 2
    assert profiles.read_bytes() == original_profiles
    assert suites.read_bytes() == original_suites
    with pytest.raises(RuntimeError, match="original file is invalid"):
        manager.add_profile("new", "src", "tgt", [])
    assert profiles.read_bytes() == original_profiles


@pytest.mark.parametrize(
    "payload",
    [b"{", b"[]", b'{"backup": []}', b'{"backup": {"enabled": "yes"}}', b'{"backup": {"max_backups": -1}}', b"\xff"],
)
def test_invalid_global_settings_fall_back_without_overwriting_source(monkeypatch, tmp_path, payload):
    _, _, _, settings, _, _ = _patch_config_files(monkeypatch, tmp_path)
    settings.parent.mkdir()
    settings.write_bytes(payload)

    global_config = config_module.GlobalConfig()
    loaded = global_config.load()

    assert loaded == config_module.GlobalConfig.DEFAULT_CONFIG
    assert global_config.load_error
    assert settings.read_bytes() == payload


def test_tui_entry_and_config_screen_recover_from_bad_profile_json(monkeypatch, tmp_path):
    _, profiles, _, settings, _, _ = _patch_config_files(monkeypatch, tmp_path)
    profiles.parent.mkdir()
    profiles.write_text("not json", encoding="utf-8")
    settings.write_text('{"backup": []}', encoding="utf-8")

    from tui.app import MCRecipeApp

    app = MCRecipeApp()
    assert app.config_manager.recovery_errors

    async def exercise():
        async with app.run_test() as pilot:
            app.push_config_screen()
            await pilot.pause()
            status = str(app.screen.query_one("#status-bar").render())
            assert "Recovery needed" in status
            assert "preserved" in status
            assert "Global settings were not loaded" in status

    asyncio.run(exercise())


def test_reset_all_cancel_and_missing_defaults_preserve_existing_data(monkeypatch, tmp_path):
    config_dir, profiles, _, _, _, bundled = _patch_config_files(monkeypatch, tmp_path)
    config_dir.mkdir()
    profiles.write_text("user profiles", encoding="utf-8")
    screen = ConfigScreen(ConfigManager())
    status = _StatusRecorder()
    app = _FakeApp()
    screen._status_bar = status
    monkeypatch.setattr(ConfigScreen, "app", property(lambda _self: app))

    screen._on_reset_all_confirmed(False)
    assert profiles.read_text(encoding="utf-8") == "user profiles"
    bundled.unlink()
    screen._on_reset_all_confirmed(True)

    assert profiles.read_text(encoding="utf-8") == "user profiles"
    assert "existing data was preserved" in status.message


def test_reset_all_stages_defaults_then_replaces_existing_data(monkeypatch, tmp_path):
    config_dir, profiles, suites, global_settings, mapping, _ = _patch_config_files(monkeypatch, tmp_path)
    config_dir.mkdir()
    profiles.write_text("bad profiles", encoding="utf-8")
    screen = ConfigScreen(ConfigManager())
    status = _StatusRecorder()
    app = _FakeApp()
    screen._status_bar = status
    monkeypatch.setattr(ConfigScreen, "app", property(lambda _self: app))

    screen._on_reset_all_confirmed(True)

    assert json.loads(profiles.read_text(encoding="utf-8")) == {"profiles": []}
    assert json.loads(suites.read_text(encoding="utf-8")) == {"suites": []}
    assert json.loads(global_settings.read_text(encoding="utf-8")) == config_module.GlobalConfig.DEFAULT_CONFIG
    assert json.loads(mapping.read_text(encoding="utf-8")) == {"presets": {}}
    assert "reset" in status.message.lower()


def test_preset_reset_preflights_defaults_and_external_override_disables_action(monkeypatch, tmp_path):
    _, _, _, _, mapping, bundled = _patch_config_files(monkeypatch, tmp_path)
    mapping.parent.mkdir()
    mapping.write_text("keep me", encoding="utf-8")
    screen = ConfigScreen(ConfigManager())
    status = _StatusRecorder()
    app = _FakeApp()
    screen._status_bar = status
    monkeypatch.setattr(ConfigScreen, "app", property(lambda _self: app))
    bundled.unlink()
    screen._on_reset_presets_confirmed(True)
    assert mapping.read_text(encoding="utf-8") == "keep me"
    assert "failed" in status.message.lower()

    external = tmp_path / "external.json"
    external.write_text('{"presets": {}}', encoding="utf-8")
    monkeypatch.setenv("MCRU_MAPPING_FILE", str(external))
    screen.action_reset_presets()
    assert not app.pushed
    assert "disabled" in status.message.lower()
    paths_panel = PathsPanel()
    paths_panel.refresh_paths(screen.config_manager._resolve_mapping_file())
    assert str(external) in str(paths_panel._content.render())


def test_view_presets_reports_invalid_utf8(monkeypatch, tmp_path):
    _, _, _, _, mapping, _ = _patch_config_files(monkeypatch, tmp_path)
    mapping.parent.mkdir()
    mapping.write_bytes(b"\xff")
    screen = ConfigScreen(ConfigManager())
    app = _FakeApp()
    monkeypatch.setattr(ConfigScreen, "app", property(lambda _self: app))

    screen.action_view_presets()

    modal, _ = app.pushed[-1]
    assert "not valid UTF-8" in modal._content


def test_view_presets_displays_bundled_defaults_after_config_seeding(monkeypatch, tmp_path):
    _, _, _, _, mapping, _ = _patch_config_files(monkeypatch, tmp_path)
    screen = ConfigScreen(ConfigManager())
    app = _FakeApp()
    monkeypatch.setattr(ConfigScreen, "app", property(lambda _self: app))

    screen.action_view_presets()

    modal, _ = app.pushed[-1]
    assert json.loads(mapping.read_text(encoding="utf-8")) == {"presets": {}}
    assert json.loads(modal._content) == {"presets": {}}