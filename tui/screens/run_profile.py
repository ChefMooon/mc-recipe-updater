"""Sync execution screen."""

import threading
from datetime import datetime
from pathlib import Path
from textual.screen import Screen
from textual.containers import Container, Horizontal, Vertical
from textual.widgets import Static, ListView, ListItem, Label, Input, Checkbox
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

    def __init__(self, mode: str, targets: list[str]):
        super().__init__()
        self.mode = mode
        self.targets = targets
        self.border_title = f"[1] {'Profiles' if mode == 'profile' else 'Suites'}"

    def compose(self):
        if self.targets:
            yield ListView(*[RunTargetItem(name) for name in self.targets], id="target-listview")
        else:
            label = "profiles" if self.mode == "profile" else "suites"
            yield Static(f" No {label} found", id="empty-state")


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
        super().__init__()
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
        super().__init__()
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
        super().__init__()
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

    def __init__(self):
        super().__init__()
        self.border_title = "[2] Details"
        self._content = Static("", id="run-detail-content")

    def compose(self):
        yield self._content

    def update_detail(self, text: str) -> None:
        self._content.update(text)


class RunActionBar(Container):
    """Phase-aware action bar."""

    DEFAULT_CSS = """
    RunActionBar {
        width: 1fr;
        height: 3;
        border: solid $primary;
        border-title-color: $text;
        border-title-style: bold;
        padding: 0 1;
        align: left middle;
    }
    """

    def __init__(self):
        super().__init__()
        self.border_title = "[3] Actions"
        self._content = Static("", id="run-action-keys")

    def compose(self):
        yield self._content

    def update_phase(self, phase: str) -> None:
        if phase == "running":
            text = "[bold dim]Esc[/bold dim]: Request cancel"
        elif phase == "done":
            text = "[bold green]r[/bold green]: Re-run  [bold dim]Esc[/bold dim]: Back to selection"
        else:
            text = "[bold green]Space[/bold green]: Start  [bold cyan]Tab[/bold cyan]: Profile/Suite  [bold dim]Esc[/bold dim]: Back"
        self._content.update(text)


class RunProfileScreen(Screen):
    """Sync execution and monitoring screen."""

    BINDINGS = [
        Binding("escape", "back", "Back", show=False),
        Binding("space", "start_run", "Start", show=False),
        Binding("tab", "toggle_mode", "Toggle", show=False),
        Binding("r", "rerun", "Re-run", show=False),
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
        self._started_at: datetime | None = None
        self._last_selection: str | None = None
        self._last_result: dict | None = None

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
        if not source.exists():
            raise FileNotFoundError(f"Source folder does not exist: {source}")
        if not target.exists():
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
        self._started_at = datetime.now()
        self._progress_panel = ProgressPanel()
        self._details_panel = RunDetailPanel()
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
        self._details_panel = RunDetailPanel()
        self._replace_main_panels(self._results_panel, self._details_panel)
        self._results_panel.update_results(summary)
        self._details_panel.update_detail(details)
        if self._action_bar:
            self._action_bar.update_phase(self._phase)

    def _switch_to_selection(self) -> None:
        self._phase = "selection"
        self._syncer = None
        self._suite_cancel_event = None
        self._target_list = TargetList(self._mode, self._target_names())
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
            return
        self._mode = "suite" if self._mode == "profile" else "profile"
        self._target_list = TargetList(self._mode, self._target_names())
        row = self.query_one("#panels-row", Horizontal)
        if row.children:
            row.children[0].remove()
        row.mount(self._target_list, before=self._options_panel)
        self._set_status(f"Selection mode: {'Profiles' if self._mode == 'profile' else 'Suites'}.")
        self._update_selected_detail()
        try:
            self.query_one("#target-listview", ListView).focus()
        except Exception:
            pass

    def action_start_run(self) -> None:
        if self._phase != "selection":
            return
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
        self._switch_to_running(profile_name, "profile", dry_run)
        self._syncer = ThreadedSyncer(
            config,
            dry_run=dry_run,
            on_progress=lambda current, total, op: self.app.call_from_thread(self._on_progress, current, total, op, profile_name),
            on_complete=lambda results, error: self.app.call_from_thread(
                self._on_profile_complete,
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
        self._suite_cancel_event = threading.Event()
        self._switch_to_running(suite_name, "suite", options["dry_run"])
        thread = threading.Thread(target=self._run_suite_worker, args=(suite_name, suite, options), daemon=True)
        thread.start()

    def _run_suite_worker(self, suite_name: str, suite: dict, options: dict) -> None:
        runs = []
        skipped = []
        report_path = None
        cancelled = False
        error = None
        try:
            for profile_name in suite.get("profiles", []):
                if self._suite_cancel_event and self._suite_cancel_event.is_set():
                    raise SyncCancelled("Sync cancelled.")
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
                        progress_callback=lambda current, total, op, name=profile_name: self.app.call_from_thread(
                            self._on_progress, current, total, op, name
                        ),
                        cancel_event=self._suite_cancel_event,
                    )
                    results = mcru.run()
                except Exception:
                    if backup_id:
                        self.backup_manager.finalize_backup(backup_id, "failed")
                    raise
                if backup_id:
                    self.backup_manager.finalize_backup(backup_id, "success")
                    self.backup_manager.rotate_backups(self.global_config.get("backup.max_backups", 10))
                if (options["changelog"] or config.get("target_changelog")) and not options["dry_run"]:
                    TargetChangelogWriter(config["target"], profile_name).write(results, config)
                runs.append((profile_name, config, results))
            if runs:
                report_path = SuiteReporter(suite_name, runs, dry_run=options["dry_run"]).save_report()
        except SyncCancelled as err:
            cancelled = True
            error = err
        except Exception as err:
            error = err
        self.app.call_from_thread(self._on_suite_complete, suite_name, options, runs, skipped, report_path, cancelled, error)

    def _on_progress(self, current: int, total: int, operation: str, profile_name: str) -> None:
        if not self._progress_panel:
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
        profile_name: str,
        config: dict,
        options: dict,
        backup_id: str | None,
        results: dict | None,
        error: Exception | None,
    ) -> None:
        report_path = None
        backup_status = "none"
        if backup_id:
            try:
                self.backup_manager.finalize_backup(backup_id, "failed" if error else "success")
                if not error:
                    self.backup_manager.rotate_backups(self.global_config.get("backup.max_backups", 10))
                backup_status = backup_id
            except ValueError as err:
                backup_status = f"finalize failed: {err}"
        if results and not error:
            report_path = Reporter(profile_name, config, results, dry_run=options["dry_run"]).save_report()
            if (options["changelog"] or config.get("target_changelog")) and not options["dry_run"]:
                TargetChangelogWriter(config["target"], profile_name).write(results, config)
        self._last_result = results
        if error:
            summary = "[red]Run failed[/red]"
            if isinstance(error, SyncCancelled):
                summary = "[yellow]Run cancelled[/yellow]"
            details = str(error)
        else:
            summary = _format_result_summary(results)
            details = _format_run_details(profile_name, "profile", options, report_path, backup_status, [])
        self._switch_to_results(summary, details)
        self._set_status("Run cancelled." if isinstance(error, SyncCancelled) else "Run complete." if not error else f"Run failed: {error}")

    def _on_suite_complete(
        self,
        suite_name: str,
        options: dict,
        runs: list,
        skipped: list,
        report_path: str | None,
        cancelled: bool,
        error: Exception | None,
    ) -> None:
        if runs:
            aggregate = _aggregate_results([result for _, _, result in runs])
            summary = _format_result_summary(aggregate)
        elif cancelled:
            summary = "[yellow]Suite run cancelled[/yellow]"
        else:
            summary = "[red]No profiles ran successfully[/red]"
        if error and not cancelled:
            summary += f"\n\n[red]{error}[/red]"
        details = _format_run_details(suite_name, "suite", options, report_path, "per profile", skipped)
        self._switch_to_results(summary, details)
        self._set_status("Suite run cancelled." if cancelled else "Suite run complete." if not error else f"Suite run failed: {error}")

    def action_rerun(self) -> None:
        if self._phase != "done":
            return
        self._switch_to_selection()
        self.action_start_run()

    def action_back(self) -> None:
        if self._phase == "running":
            if self._syncer:
                self._syncer.cancel()
            if self._suite_cancel_event:
                self._suite_cancel_event.set()
            self._set_status("Cancellation requested.")
            return
        if self._phase == "done":
            self._switch_to_selection()
            return
        self.app.pop_screen()


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


def _format_run_details(
    target_name: str,
    target_type: str,
    options: dict,
    report_path: str | None,
    backup_status: str,
    skipped: list[tuple[str, str]],
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
    return "\n".join(lines)