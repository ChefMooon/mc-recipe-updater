"""Sync execution screen."""

import threading
from datetime import datetime
from pathlib import Path
from typing import Any
from textual.screen import Screen
from textual.containers import Container, Horizontal, Vertical
from textual.widgets import Button, Static, ListView, ListItem, Label, Input, Checkbox
from textual.binding import Binding
from config import ConfigManager, GlobalConfig
from backup import BackupManager
from reporter import Reporter, SuiteReporter, TargetChangelogWriter
from syncer import MCRU, SyncCancelled
from tui.utils import ThreadedSyncer


class RunTargetItem(ListItem):
    """Profile or suite target row."""

    def __init__(self, name: str, **kwargs):
        super().__init__(**kwargs)
        self.target_name = name

    def compose(self):
        yield Label(self.target_name)


class TargetList(Container):
    """Selectable profiles or suites."""

    DEFAULT_CSS = """
    TargetList {
        width: 1fr;
        height: 1fr;
        border: solid $primary;
        border-title-color: $text;
        border-title-style: bold;
        padding: 0;
    }

    TargetList ListView {
        width: 1fr;
        height: 1fr;
        background: $surface;
    }

    TargetList ListView > ListItem {
        padding: 0 1;
        height: 1;
        background: $surface;
    }

    TargetList ListView > ListItem.--highlight {
        background: $primary 30%;
    }

    TargetList ListView:focus > ListItem.--highlight {
        background: $primary 50%;
    }

    TargetList ListView > ListItem.--highlight Label {
        color: $text;
        text-style: bold;
    }
    """

    def __init__(self, mode: str, targets: list[str], selected: str | None = None):
        super().__init__(id="target-list-panel", classes="section-1-panel")
        self.mode = mode
        self.targets = targets
        self.selected = selected
        self.border_title = f"[1] {'Profiles' if mode == 'profile' else 'Suites'}"

    def compose(self):
        selected_index = self.targets.index(self.selected) if self.selected in self.targets else 0
        yield ListView(*self._build_items(), id="target-listview", initial_index=selected_index)

    def update_targets(self, mode: str, targets: list[str]) -> None:
        self.mode = mode
        self.targets = targets
        self.border_title = f"[1] {'Profiles' if mode == 'profile' else 'Suites'}"
        listview = self.query_one("#target-listview", ListView)
        listview.clear()
        listview.extend(self._build_items())

    def _build_items(self) -> list[ListItem]:
        if self.targets:
            return [RunTargetItem(name) for name in self.targets]
        label = "profiles" if self.mode == "profile" else "suites"
        return [ListItem(Label(f" No {label} found"))]


class OptionsPanel(Container):
    """Run options and selected target details."""

    DEFAULT_CSS = """
    OptionsPanel {
        width: 1fr;
        height: 1fr;
        border: solid $primary;
        border-title-color: $text;
        border-title-style: bold;
        padding: 1 2;
    }

    OptionsPanel #target-detail {
        width: 1fr;
        height: auto;
        margin: 0 0 1 0;
    }

    OptionsPanel .option-input {
        width: 1fr;
        height: 3;
    }
    """

    def __init__(self, backup_enabled: bool):
        super().__init__(id="options-panel", classes="section-2-panel")
        self.border_title = "[2] Options"
        self.backup_enabled = backup_enabled
        self._detail = Static("Select a target to view details", id="target-detail")

    def compose(self):
        yield self._detail
        yield Checkbox("Dry run", id="option-dry-run")
        yield Checkbox("Create backups for live runs", value=self.backup_enabled, id="option-backup")
        yield Checkbox("Force target changelog for live runs", id="option-changelog")
        yield Static("[bold]Source override[/bold] [dim](optional)[/dim]")
        yield Input(placeholder="Leave blank to use saved source", id="option-source", classes="option-input")
        yield Static("[bold]Target override[/bold] [dim](optional)[/dim]")
        yield Input(placeholder="Leave blank to use saved target", id="option-target", classes="option-input")
        yield Static("[bold]Mapping override[/bold] [dim](optional)[/dim]")
        yield Input(placeholder="Leave blank to use saved mapping", id="option-mapping", classes="option-input")

    def update_target(self, text: str) -> None:
        self._detail.update(text)


class ProgressPanel(Container):
    """Progress display shown during execution."""

    DEFAULT_CSS = """
    ProgressPanel {
        width: 1fr;
        height: 1fr;
        border: solid $primary;
        border-title-color: $text;
        border-title-style: bold;
        padding: 1 2;
    }
    """

    def __init__(self):
        super().__init__(id="progress-panel", classes="section-1-panel")
        self.border_title = "[1] Progress"
        self._content = Static("Waiting to start", id="progress-content")

    def compose(self):
        yield self._content

    def update_progress(self, text: str) -> None:
        self._content.update(text)


class ResultsPanel(Container):
    """Results summary panel."""

    DEFAULT_CSS = """
    ResultsPanel {
        width: 1fr;
        height: 1fr;
        border: solid $primary;
        border-title-color: $text;
        border-title-style: bold;
        padding: 1 2;
    }

    ResultsPanel #results-content {
        width: 1fr;
        height: 1fr;
        overflow-y: auto;
    }
    """

    def __init__(self):
        super().__init__(id="results-panel", classes="section-1-panel")
        self.border_title = "[1] Results"
        self._content = Static("No run results yet", id="results-content")

    def compose(self):
        yield self._content

    def update_results(self, text: str) -> None:
        self._content.update(text)


class RunDetailPanel(Container):
    """Right-side details panel for progress/results phases."""

    DEFAULT_CSS = """
    RunDetailPanel {
        width: 1fr;
        height: 1fr;
        border: solid $primary;
        border-title-color: $text;
        border-title-style: bold;
        padding: 1 2;
    }

    RunDetailPanel #run-detail-content {
        width: 1fr;
        height: 1fr;
        overflow-y: auto;
    }
    """

    def __init__(self, phase: str):
        super().__init__(id=f"{phase}-details-panel", classes="section-2-panel")
        self.border_title = "[2] Details"
        self._content = Static("", id="run-detail-content")

    def compose(self):
        yield self._content

    def update_detail(self, text: str) -> None:
        self._content.update(text)


class RunActionBar(Container):
    """Phase-aware action bar."""

    can_focus = True

    DEFAULT_CSS = """
    RunActionBar {
        width: 1fr;
        height: 5;
        border: solid $primary;
        border-title-color: $text;
        border-title-style: bold;
        padding: 0 1;
        align: left middle;
    }

    RunActionBar #run-actions {
        width: 1fr;
        height: 3;
    }

    RunActionBar Button {
        width: auto;
        min-width: 10;
        height: 3;
        margin: 0 1 0 0;
    }

    RunActionBar #run-action-keys {
        width: 1fr;
        height: 1;
    }
    """

    def __init__(self):
        super().__init__(id="section-3-actions")
        self.border_title = "[3] Actions"
        self._content = Static("", id="run-action-keys")

    def compose(self):
        with Horizontal(id="run-actions"):
            yield Button("Start", id="start-run", variant="primary")
            yield self._content

    def update_phase(self, phase: str) -> None:
        self.query_one("#start-run", Button).display = phase == "selection"
        if phase == "running":
            text = (
                "[bold dim]Esc[/bold dim]: Request cancel"
            )
        elif phase == "done":
            text = (
                "[bold green]r[/bold green]: Re-run  "
                "[bold dim]Esc[/bold dim]: Back to selection"
            )
        else:
            text = (
                "[bold green]Space[/bold green]: Start  "
                "[bold cyan]Tab[/bold cyan]: Profile/Suite  "
                "[bold dim]Esc[/bold dim]: Back"
            )
        self._content.update(text)


class RunProfileScreen(Screen):
    """Sync execution and monitoring screen."""

    BINDINGS = [
        Binding("escape", "back", "Back", show=False),
        Binding("q", "back", "Back", show=False),
        Binding("ctrl+c", "force_quit", "Force Quit", show=False),
        Binding("space", "start_run", "Start", show=False),
        Binding("tab", "toggle_mode", "Toggle", show=False),
        Binding("r", "rerun", "Re-run", show=False),
        Binding("up", "option_up", "Option Up", show=False),
        Binding("down", "option_down", "Option Down", show=False),
        Binding("ctrl+1", "focus_section_1", "Section 1", show=False),
        Binding("ctrl+2", "focus_section_2", "Section 2", show=False),
        Binding("ctrl+3", "focus_section_3", "Section 3", show=False),
        Binding("alt+1", "focus_section_1", "Section 1", show=False),
        Binding("alt+2", "focus_section_2", "Section 2", show=False),
        Binding("alt+3", "focus_section_3", "Section 3", show=False),
        Binding("f1", "focus_section_1", "Section 1", show=False),
        Binding("f2", "focus_section_2", "Section 2", show=False),
        Binding("f3", "focus_section_3", "Section 3", show=False),
    ]

    DEFAULT_CSS = """
    RunProfileScreen {
        background: $surface;
    }

    RunProfileScreen #run-layout {
        width: 1fr;
        height: 1fr;
    }

    RunProfileScreen #panels-row {
        width: 1fr;
        height: 1fr;
    }

    RunProfileScreen #status-bar {
        width: 1fr;
        height: 1;
        background: $surface;
        color: $text-muted;
        padding: 0 1;
        dock: bottom;
    }
    """

    def __init__(self, config_manager: ConfigManager):
        super().__init__()
        self.config_manager = config_manager
        self.global_config = GlobalConfig()
        self.backup_manager = BackupManager()
        self._mode = "profile"
        self._phase = "selection"
        self._target_list: TargetList | None = None
        self._options_panel: OptionsPanel | None = None
        self._progress_panel: ProgressPanel | None = None
        self._results_panel: ResultsPanel | None = None
        self._details_panel: RunDetailPanel | None = None
        self._action_bar: RunActionBar | None = None
        self._status_bar: Static | None = None
        self._syncer: ThreadedSyncer | None = None
        self._suite_cancel_event: threading.Event | None = None
        self._suite_thread: threading.Thread | None = None
        self._started_at: datetime | None = None
        self._last_selection: str | None = None
        self._last_result: dict | None = None
        self._run_id: int = 0
        self._shutdown_requested = False
        self._option_order = ["option-dry-run", "option-backup", "option-changelog", "option-source", "option-target", "option-mapping"]
        self._focused_option_index = 0

    def _next_run_id(self) -> int:
        self._run_id += 1
        return self._run_id

    def _is_active_run(self, run_id: int) -> bool:
        return run_id == self._run_id

    def compose(self):
        with Vertical(id="run-layout"):
            with Horizontal(id="panels-row"):
                self._target_list = TargetList(self._mode, self._target_names())
                yield self._target_list
                self._options_panel = OptionsPanel(self.global_config.get("backup.enabled", True))
                yield self._options_panel
            self._action_bar = RunActionBar()
            yield self._action_bar
        self._status_bar = Static("", id="status-bar")
        yield self._status_bar

    def on_mount(self) -> None:
        if self._action_bar:
            self._action_bar.update_phase(self._phase)
        self._update_selected_detail()
        try:
            self.query_one("#target-listview", ListView).focus()
        except Exception:
            pass

    def on_list_view_highlighted(self, event: ListView.Highlighted) -> None:
        if isinstance(event.item, RunTargetItem):
            self._last_selection = event.item.target_name
            self._update_selected_detail()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "start-run":
            self.action_start_run()

    def _target_names(self) -> list[str]:
        if self._mode == "profile":
            return [profile["name"] for profile in self.config_manager.list_profiles()]
        return [suite["name"] for suite in self.config_manager.list_suites()]

    def _selected_target(self) -> str | None:
        try:
            item = self.query_one("#target-listview", ListView).highlighted_child
        except Exception:
            return self._last_selection
        if isinstance(item, RunTargetItem):
            return item.target_name
        return self._last_selection

    def _update_selected_detail(self) -> None:
        if not self._options_panel:
            return
        name = self._selected_target()
        if not name:
            self._options_panel.update_target("[dim]Select a target to view details[/dim]")
            return
        if self._mode == "profile":
            profile = self.config_manager.get_profile(name)
            if not profile:
                self._options_panel.update_target("[red]Profile not found[/red]")
                return
            self._options_panel.update_target(
                "\n".join([
                    f"[bold dim]{'Profile:':<10}[/bold dim] [bold]{name}[/bold]",
                    f"[bold dim]{'Source:':<10}[/bold dim] {profile.get('source', '')}",
                    f"[bold dim]{'Target:':<10}[/bold dim] {profile.get('target', '')}",
                    f"[bold dim]{'Mapping:':<10}[/bold dim] {profile.get('mapping_preset') or '[dim]none[/dim]'}",
                ])
            )
        else:
            suite = self.config_manager.get_suite(name)
            profiles = suite.get("profiles", []) if suite else []
            self._options_panel.update_target(
                "\n".join([
                    f"[bold dim]{'Suite:':<10}[/bold dim] [bold]{name}[/bold]",
                    f"[bold dim]{'Profiles:':<10}[/bold dim] {len(profiles)}",
                    f"[bold dim]{'Order:':<10}[/bold dim] {', '.join(profiles) if profiles else '[dim]none[/dim]'}",
                ])
            )

    def _set_status(self, message: str) -> None:
        if self._status_bar:
            self._status_bar.update(message)

    def _option_values(self) -> dict:
        return {
            "dry_run": self.query_one("#option-dry-run", Checkbox).value,
            "backup": self.query_one("#option-backup", Checkbox).value,
            "changelog": self.query_one("#option-changelog", Checkbox).value,
            "source": self.query_one("#option-source", Input).value.strip() or None,
            "target": self.query_one("#option-target", Input).value.strip() or None,
            "mapping": self.query_one("#option-mapping", Input).value.strip() or None,
        }

    def _prepare_profile_config(self, profile_name: str, options: dict) -> dict:
        config = self.config_manager.get_profile(profile_name)
        if config is None:
            raise ValueError(f"Profile '{profile_name}' not found.")
        if options.get("source"):
            config["source"] = options["source"]
        if options.get("target"):
            config["target"] = options["target"]
        source = Path(config["source"])
        target = Path(config["target"])
        if not source.is_dir():
            raise FileNotFoundError(f"Source folder does not exist: {source}")
        if not target.is_dir():
            raise FileNotFoundError(f"Target folder does not exist: {target}")
        active_mapping = options.get("mapping") or config.get("mapping_preset")
        if active_mapping:
            config["mapping"] = self.config_manager.get_mapping_preset(active_mapping)
            config["mapping_preset"] = active_mapping
        return config

    def _replace_main_panels(self, left: Container, right: Container) -> None:
        row = self.query_one("#panels-row", Horizontal)
        for child in list(row.children):
            child.remove()
        row.mount(left)
        row.mount(right)

    def _switch_to_running(self, target_name: str, mode: str, dry_run: bool) -> None:
        self._phase = "running"
        self._last_selection = target_name
        self._started_at = datetime.now()
        self._progress_panel = ProgressPanel()
        self._details_panel = RunDetailPanel("progress")
        self._replace_main_panels(self._progress_panel, self._details_panel)
        if self._action_bar:
            self._action_bar.update_phase(self._phase)
        self._details_panel.update_detail(
            "\n".join([
                f"[bold dim]{'Target:':<12}[/bold dim] {target_name}",
                f"[bold dim]{'Type:':<12}[/bold dim] {mode}",
                f"[bold dim]{'Mode:':<12}[/bold dim] {'DRY RUN' if dry_run else 'LIVE'}",
                f"[bold dim]{'Started:':<12}[/bold dim] {self._started_at.strftime('%Y-%m-%d %H:%M:%S')}",
            ])
        )

    def _switch_to_results(self, summary: str, details: str) -> None:
        self._phase = "done"
        self._results_panel = ResultsPanel()
        self._details_panel = RunDetailPanel("results")
        self._replace_main_panels(self._results_panel, self._details_panel)
        self._results_panel.update_results(summary)
        self._details_panel.update_detail(details)
        if self._action_bar:
            self._action_bar.update_phase(self._phase)

    def _switch_to_selection(self) -> None:
        self._phase = "selection"
        self._syncer = None
        self._suite_cancel_event = None
        self._suite_thread = None
        self._target_list = TargetList(self._mode, self._target_names(), self._last_selection)
        self._options_panel = OptionsPanel(self.global_config.get("backup.enabled", True))
        self._replace_main_panels(self._target_list, self._options_panel)
        if self._action_bar:
            self._action_bar.update_phase(self._phase)
        try:
            self.query_one("#target-listview", ListView).focus()
        except Exception:
            pass
        self._update_selected_detail()

    def action_toggle_mode(self) -> None:
        if self._phase != "selection":
            self._set_status("Tab toggle is available only during selection.")
            return
        self._mode = "suite" if self._mode == "profile" else "profile"
        if self._target_list:
            self._target_list.update_targets(self._mode, self._target_names())
        self._set_status(f"Selection mode: {'Profiles' if self._mode == 'profile' else 'Suites'}.")
        self._update_selected_detail()
        try:
            self.query_one("#target-listview", ListView).focus()
        except Exception:
            pass

    def action_focus_section_1(self) -> None:
        if self._phase == "selection":
            if not self._focus_widget("#target-listview", ListView):
                self._focus_widget(".section-1-panel", Container)
            return
        self._focus_widget(".section-1-panel", Container)

    def action_focus_section_2(self) -> None:
        if self._phase == "selection":
            if self._focus_widget("#option-dry-run", Checkbox):
                return
        self._focus_widget(".section-2-panel", Container)

    def action_focus_section_3(self) -> None:
        if not self._focus_widget("#section-3-actions", RunActionBar):
            self._set_status("No actions section is focusable right now.")

    def _focus_widget(self, selector: str, widget_type: type[Any]) -> bool:
        try:
            self.query_one(selector, widget_type).focus()
            return True
        except Exception:
            return False

    def _is_option_widget(self, widget: Any) -> bool:
        """Check if widget is a checkbox or input in the options panel."""
        if isinstance(widget, (Checkbox, Input)):
            try:
                widget_id = widget.id
                return widget_id in self._option_order
            except Exception:
                return False
        return False

    def _get_focused_option_index(self) -> int:
        """Get the index of the currently focused option widget in _option_order."""
        try:
            focused = self.focused
            if focused and self._is_option_widget(focused):
                widget_id = focused.id
                try:
                    return self._option_order.index(widget_id)
                except ValueError:
                    return -1
        except Exception:
            pass
        return -1

    def _focus_option_by_index(self, index: int) -> bool:
        """Focus the option widget at the given index in _option_order."""
        if not (0 <= index < len(self._option_order)):
            return False
        option_id = self._option_order[index]
        if self._phase == "selection":
            try:
                widget = self.query_one(f"#{option_id}", (Checkbox, Input))
                widget.focus()
                self._focused_option_index = index
                return True
            except Exception:
                return False
        return False

    def _move_option_focus(self, delta: int) -> None:
        """Move focus by delta positions in _option_order with wrap-around."""
        if self._phase != "selection":
            self._set_status("Option navigation is available only during selection.")
            return
        current_index = self._get_focused_option_index()
        if current_index == -1:
            # No option is currently focused; start from the beginning
            current_index = 0
        else:
            # Move by delta with wrap-around
            current_index = (current_index + delta) % len(self._option_order)
        if self._focus_option_by_index(current_index):
            pass  # Focus moved successfully
        else:
            self._set_status("Could not navigate options.")

    def action_option_up(self) -> None:
        """Navigate up in the option list."""
        self._move_option_focus(-1)

    def action_option_down(self) -> None:
        """Navigate down in the option list."""
        self._move_option_focus(1)

    def action_start_run(self) -> None:
        if self._phase != "selection":
            return
        # If focused widget is a checkbox in options, toggle it instead of starting run
        try:
            focused = self.focused
            if focused and isinstance(focused, Checkbox) and self._is_option_widget(focused):
                focused.toggle()
                return
        except Exception:
            pass
        target_name = self._selected_target()
        if not target_name:
            self._set_status("No target selected.")
            return
        self._last_selection = target_name
        if self._mode == "profile":
            self._start_profile_run(target_name)
        else:
            self._start_suite_run(target_name)

    def _start_profile_run(self, profile_name: str) -> None:
        options = self._option_values()
        try:
            config = self._prepare_profile_config(profile_name, options)
        except Exception as err:
            self._set_status(str(err))
            return
        dry_run = options["dry_run"]
        backup_id = None
        if options["backup"] and not dry_run:
            try:
                backup_id = self.backup_manager.create_backup(config["target"], profile_name)
            except OSError as err:
                self._set_status(f"Backup failed: {err}")
                return
        run_id = self._next_run_id()
        self._switch_to_running(profile_name, "profile", dry_run)
        self._syncer = ThreadedSyncer(
            config,
            dry_run=dry_run,
            on_progress=lambda current, total, op: self._dispatch_to_app(
                self._on_progress,
                run_id,
                current,
                total,
                op,
                profile_name,
            ),
            on_complete=lambda results, error: self._dispatch_to_app(
                self._on_profile_complete,
                run_id,
                profile_name,
                config,
                options,
                backup_id,
                results,
                error,
            ),
        )
        self._syncer.start()

    def _start_suite_run(self, suite_name: str) -> None:
        suite = self.config_manager.get_suite(suite_name)
        if not suite:
            self._set_status(f"Suite '{suite_name}' not found.")
            return
        if not suite.get("profiles"):
            self._set_status("Suite has no profiles.")
            return
        options = self._option_values()
        run_id = self._next_run_id()
        cancel_event = threading.Event()
        self._suite_cancel_event = cancel_event
        self._switch_to_running(suite_name, "suite", options["dry_run"])
        self._suite_thread = threading.Thread(
            target=self._run_suite_worker,
            args=(run_id, suite_name, suite, options, cancel_event),
            daemon=True,
        )
        self._suite_thread.start()

    def _run_suite_worker(
        self,
        run_id: int,
        suite_name: str,
        suite: dict,
        options: dict,
        cancel_event: threading.Event,
    ) -> None:
        runs = []
        skipped = []
        warnings = []
        report_path = None
        cancelled = False
        error = None
        for profile_name in suite.get("profiles", []):
            if cancel_event.is_set():
                cancelled = True
                error = SyncCancelled()
                break
            try:
                config = self._prepare_profile_config(profile_name, options)
            except Exception as err:
                skipped.append((profile_name, str(err)))
                continue
            backup_id = None
            if options["backup"] and not options["dry_run"]:
                try:
                    backup_id = self.backup_manager.create_backup(config["target"], profile_name)
                except OSError as err:
                    skipped.append((profile_name, f"Backup failed: {err}"))
                    continue
            try:
                mcru = MCRU(
                    config,
                    dry_run=options["dry_run"],
                    progress_callback=lambda current, total, op, name=profile_name: self._dispatch_to_app(
                        self._on_progress, run_id, current, total, op, name
                    ),
                    cancel_event=cancel_event,
                )
                results = mcru.run()
            except SyncCancelled as err:
                results = err.results
                runs.append((profile_name, config, results))
                cancelled = True
                error = err
                if backup_id:
                    try:
                        self.backup_manager.finalize_backup(backup_id, "failed")
                    except Exception as finalize_err:
                        warnings.append(f"{profile_name} backup finalization failed: {finalize_err}")
                break
            except Exception as err:
                error = err
                if backup_id:
                    try:
                        self.backup_manager.finalize_backup(backup_id, "failed")
                    except Exception as finalize_err:
                        warnings.append(f"{profile_name} backup finalization failed: {finalize_err}")
                break

            runs.append((profile_name, config, results))
            if backup_id:
                try:
                    self.backup_manager.finalize_backup(backup_id, "success")
                    self.backup_manager.rotate_backups(self.global_config.get("backup.max_backups", 10))
                except Exception as err:
                    warnings.append(f"{profile_name} backup finalization/rotation failed: {err}")
            if (options["changelog"] or config.get("target_changelog")) and not options["dry_run"]:
                try:
                    TargetChangelogWriter(config["target"], profile_name).write(results, config)
                except Exception as err:
                    warnings.append(f"{profile_name} changelog failed: {err}")

        if runs:
            try:
                outcome = _classify_outcome(
                    _aggregate_results([result for _, _, result in runs]),
                    skipped,
                    warnings,
                    cancelled,
                    error,
                    bool(runs),
                )
                report_path = SuiteReporter(
                    suite_name, runs, dry_run=options["dry_run"], outcome=outcome
                ).save_report()
            except Exception as err:
                warnings.append(f"Suite report failed: {err}")
        self._dispatch_to_app(
            self._on_suite_complete,
            run_id,
            suite_name,
            options,
            runs,
            skipped,
            warnings,
            report_path,
            cancelled,
            error,
        )

    def _dispatch_to_app(self, callback, *args) -> None:
        try:
            self.app.call_from_thread(callback, *args)
        except RuntimeError:
            # The worker may finish after Ctrl+C has shut down the app.
            pass

    def _on_progress(self, run_id: int, current: int, total: int, operation: str, profile_name: str) -> None:
        if not self._is_active_run(run_id) or not self._progress_panel:
            return
        counter = f"{current} / {total}" if total else "working"
        cancel_note = "\n[dim]Cancellation requested; waiting for current operation to finish.[/dim]" if self._cancel_requested() else ""
        self._progress_panel.update_progress(
            "\n".join([
                f"[bold dim]{'Profile:':<12}[/bold dim] {profile_name}",
                f"[bold dim]{'Operation:':<12}[/bold dim] {operation}",
                f"[bold dim]{'Progress:':<12}[/bold dim] {counter}",
                cancel_note,
            ])
        )

    def _cancel_requested(self) -> bool:
        if self._syncer and self._syncer.cancel_event.is_set():
            return True
        if self._suite_cancel_event and self._suite_cancel_event.is_set():
            return True
        return False

    def _on_profile_complete(
        self,
        run_id: int,
        profile_name: str,
        config: dict,
        options: dict,
        backup_id: str | None,
        results: dict | None,
        error: Exception | None,
    ) -> None:
        if not self._is_active_run(run_id):
            return
        if isinstance(error, SyncCancelled) and results is None:
            results = error.results
        report_path = None
        backup_status = "none"
        post_warnings: list[str] = []
        if backup_id:
            try:
                self.backup_manager.finalize_backup(backup_id, "failed" if error else "success")
                backup_status = backup_id
            except Exception as err:
                backup_status = f"finalize failed: {err}"
                post_warnings.append(f"Backup finalization failed: {err}")
            if not error:
                try:
                    self.backup_manager.rotate_backups(self.global_config.get("backup.max_backups", 10))
                except Exception as err:
                    backup_status = f"{backup_id} (rotation failed)"
                    post_warnings.append(f"Backup rotation failed: {err}")
        outcome = _classify_outcome(
            results or _empty_result_summary(),
            [],
            post_warnings,
            isinstance(error, SyncCancelled),
            error if not isinstance(error, SyncCancelled) else None,
            bool(results),
        )
        if results and not error:
            try:
                report_path = Reporter(
                    profile_name, config, results, dry_run=options["dry_run"], outcome=outcome
                ).save_report()
            except Exception as err:
                post_warnings.append(f"Report failed: {err}")
            if (options["changelog"] or config.get("target_changelog")) and not options["dry_run"]:
                try:
                    TargetChangelogWriter(config["target"], profile_name).write(results, config)
                except Exception as err:
                    post_warnings.append(f"Changelog failed: {err}")
        outcome = _classify_outcome(
            results or _empty_result_summary(),
            [],
            post_warnings,
            isinstance(error, SyncCancelled),
            error if not isinstance(error, SyncCancelled) else None,
            bool(results),
        )
        self._last_result = results
        summary = _format_outcome_summary(outcome, results)
        if error and not isinstance(error, SyncCancelled):
            summary += f"\n\n[red]{error}[/red]"
        details = _format_run_details(profile_name, "profile", options, report_path, backup_status, [], post_warnings)
        if isinstance(error, SyncCancelled):
            details += f"\n\n[yellow]{error}[/yellow]"
        self._switch_to_results(summary, details)
        self._set_status(f"Run {outcome}." + (f" {error}" if error and not isinstance(error, SyncCancelled) else ""))

    def _on_suite_complete(
        self,
        run_id: int,
        suite_name: str,
        options: dict,
        runs: list,
        skipped: list,
        warnings: list,
        report_path: str | None,
        cancelled: bool,
        error: Exception | None,
    ) -> None:
        if not self._is_active_run(run_id):
            return
        aggregate = _aggregate_results([result for _, _, result in runs]) if runs else _empty_result_summary()
        outcome = _classify_outcome(aggregate, skipped, warnings, cancelled, error, bool(runs))
        summary = _format_outcome_summary(outcome, aggregate)
        if error and not cancelled:
            summary += f"\n\n[red]{error}[/red]"
        details = _format_run_details(suite_name, "suite", options, report_path, "per profile", skipped, warnings)
        self._switch_to_results(summary, details)
        self._set_status(f"Suite run {outcome}." + (f" {error}" if error and not cancelled else ""))

    def action_rerun(self) -> None:
        if self._phase != "done":
            return
        self._switch_to_selection()
        self.action_start_run()

    def action_back(self) -> None:
        if self._phase == "running":
            self._request_cancellation()
            self._set_status("Cancellation requested.")
            return
        if self._phase == "done":
            self._switch_to_selection()
            return
        self.app.pop_screen()

    def action_force_quit(self) -> None:
        """Signal cancellation and exit without waiting for worker cleanup."""
        if self._shutdown_requested:
            return
        self._shutdown_requested = True
        self._request_cancellation()
        self._next_run_id()
        self.app.exit()

    def _request_cancellation(self) -> None:
        if self._syncer:
            self._syncer.cancel()
        if self._suite_cancel_event:
            self._suite_cancel_event.set()


def _aggregate_results(results_list: list[dict]) -> dict:
    aggregate = {"added": [], "updated": [], "removed": [], "unchanged": [], "dirs_added": [], "dirs_removed": [], "errors": []}
    for results in results_list:
        for key in aggregate:
            aggregate[key].extend(results.get(key, []))
    return aggregate


def _format_result_summary(results: dict | None) -> str:
    if not results:
        return "[dim]No results.[/dim]"
    rows = [
        ("Added", len(results.get("added", []))),
        ("Updated", len(results.get("updated", []))),
        ("Removed", len(results.get("removed", []))),
        ("Unchanged", len(results.get("unchanged", []))),
        ("Dirs added", len(results.get("dirs_added", []))),
        ("Dirs removed", len(results.get("dirs_removed", []))),
        ("Errors", len(results.get("errors", []))),
    ]
    lines = [f"[bold dim]{label + ':':<14}[/bold dim] {count}" for label, count in rows]
    if results.get("errors"):
        lines.append("")
        lines.append("[bold red]Errors[/bold red]")
        for file_path, err in results.get("errors", [])[:10]:
            lines.append(f"{file_path}: {err}")
    return "\n".join(lines)


def _empty_result_summary() -> dict:
    return {key: [] for key in ("added", "updated", "removed", "unchanged", "dirs_added", "dirs_removed", "errors")}


def _classify_outcome(results: dict, skipped: list, warnings: list, cancelled: bool, error: Exception | None, ran: bool) -> str:
    if cancelled:
        return "cancelled"
    mutations = sum(len(results.get(key, [])) for key in ("added", "updated", "removed", "dirs_added", "dirs_removed"))
    if error:
        return "partial" if mutations or ran else "failed"
    if results.get("errors"):
        return "partial" if mutations else "failed"
    if warnings or skipped:
        return "partial" if ran else "failed"
    return "success"


def _format_outcome_summary(outcome: str, results: dict | None) -> str:
    color = {"success": "green", "partial": "yellow", "failed": "red", "cancelled": "yellow"}[outcome]
    lines = [f"[bold {color}]Outcome: {outcome}[/bold {color}]", "", _format_result_summary(results)]
    if outcome == "cancelled":
        lines.extend(["", "[yellow]Completed changes were not rolled back.[/yellow]"])
    return "\n".join(lines)


def _format_run_details(
    target_name: str,
    target_type: str,
    options: dict,
    report_path: str | None,
    backup_status: str,
    skipped: list[tuple[str, str]],
    post_warnings: list[str],
) -> str:
    lines = [
        f"[bold dim]{'Target:':<12}[/bold dim] {target_name}",
        f"[bold dim]{'Type:':<12}[/bold dim] {target_type}",
        f"[bold dim]{'Mode:':<12}[/bold dim] {'DRY RUN' if options['dry_run'] else 'LIVE'}",
        f"[bold dim]{'Report:':<12}[/bold dim] {report_path or '[dim]none[/dim]'}",
        f"[bold dim]{'Backup:':<12}[/bold dim] {backup_status}",
    ]
    if skipped:
        lines.append("")
        lines.append("[bold yellow]Skipped[/bold yellow]")
        for name, reason in skipped[:12]:
            lines.append(f"{name}: {reason}")
    if post_warnings:
        lines.append("")
        lines.append("[bold yellow]Post-run warnings[/bold yellow]")
        for warning in post_warnings[:12]:
            lines.append(warning)
    return "\n".join(lines)