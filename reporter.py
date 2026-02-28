"""
Reporter - Formats and saves sync job results.

Prints a colour-coded summary to the terminal and saves
a timestamped .txt report to ~/.mcru/reports/

Classes:
  Reporter      - single-profile report
  SuiteReporter - combined report for a suite (list of profile runs)
"""

import click
from datetime import datetime
from pathlib import Path

REPORTS_DIR = Path.home() / ".mcru" / "reports"


class Reporter:
    def __init__(self, profile_name: str, config: dict, results: dict, dry_run: bool = False):
        self.profile_name = profile_name
        self.config = config
        self.results = results
        self.dry_run = dry_run
        self.timestamp = datetime.now()

    def print_summary(self):
        r = self.results
        total_changes = (
            len(r["added"]) + len(r["updated"]) + len(r["removed"])
            + len(r.get("dirs_added", [])) + len(r.get("dirs_removed", []))
        )

        mode = "DRY RUN" if self.dry_run else "LIVE"
        click.echo(f"{'─'*60}")
        click.echo(f"  Sync Report  [{mode}]  {self.timestamp.strftime('%Y-%m-%d %H:%M:%S')}")
        click.echo(f"{'─'*60}")

        if r["added"]:
            click.echo(click.style(f"\n  ➕ Added ({len(r['added'])})", fg="green", bold=True))
            for f in r["added"]:
                click.echo(f"     {f}")

        if r.get("dirs_added"):
            click.echo(click.style(f"\n  📁 Dirs added ({len(r['dirs_added'])})", fg="green", bold=True))
            for d in r["dirs_added"]:
                click.echo(f"     {d}/")

        if r["updated"]:
            click.echo(click.style(f"\n  ✏️  Updated ({len(r['updated'])})", fg="yellow", bold=True))
            for f in r["updated"]:
                click.echo(f"     {f}")

        if r["removed"]:
            click.echo(click.style(f"\n  🗑️  Removed ({len(r['removed'])})", fg="red", bold=True))
            for f in r["removed"]:
                click.echo(f"     {f}")

        if r.get("dirs_removed"):
            click.echo(click.style(f"\n  📁 Dirs removed ({len(r['dirs_removed'])})", fg="red", bold=True))
            for d in r["dirs_removed"]:
                click.echo(f"     {d}/")

        if r["errors"]:
            click.echo(click.style(f"\n  ⚠️  Errors ({len(r['errors'])})", fg="bright_red", bold=True))
            for f, err in r["errors"]:
                click.echo(f"     {f}: {err}")

        click.echo(f"\n  {'─'*40}")
        if total_changes == 0:
            click.echo(click.style("  ✅  Folders are already in sync.", fg="bright_green"))
        else:
            summary = []
            if r["added"]:                  summary.append(f"{len(r['added'])} added")
            if r["updated"]:                summary.append(f"{len(r['updated'])} updated")
            if r["removed"]:                summary.append(f"{len(r['removed'])} removed")
            if r.get("dirs_added"):         summary.append(f"{len(r['dirs_added'])} dirs added")
            if r.get("dirs_removed"):       summary.append(f"{len(r['dirs_removed'])} dirs removed")
            label = "Would apply" if self.dry_run else "Applied"
            click.echo(f"  {label}: " + click.style(", ".join(summary), bold=True))

        click.echo(f"  Unchanged: {len(r['unchanged'])} files")
        click.echo(f"{'─'*60}\n")

    def save_report(self) -> str:
        REPORTS_DIR.mkdir(parents=True, exist_ok=True)
        filename = f"{self.profile_name}_{self.timestamp.strftime('%Y%m%d_%H%M%S')}.txt"
        filepath = REPORTS_DIR / filename

        r = self.results
        def fmt(items, prefix):
            return [f"  {prefix} {f}" for f in items] if items else ["  (none)"]

        lines = [
            "mcru Report",
            "=" * 60,
            f"Profile  : {self.profile_name}",
            f"Date     : {self.timestamp.isoformat(timespec='seconds')}",
            f"Mode     : {'DRY RUN' if self.dry_run else 'LIVE'}",
            f"Source   : {self.config['source']}",
            f"Target   : {self.config['target']}",
            f"Parsers  : {', '.join(self.config.get('parsers', [])) or 'none'}",
            f"Mapping  : {self.config.get('mapping_preset') or 'none'}",
            "=" * 60,
            "",
            f"Added ({len(r['added'])}): (files)",
            *fmt(r["added"], "+"),
            "",
            f"Updated ({len(r['updated'])}):",
            *fmt(r["updated"], "~"),
            "",
            f"Removed ({len(r['removed'])}): (files)",
            *fmt(r["removed"], "-"),
            "",
            f"Unchanged ({len(r['unchanged'])}):",
            *fmt(r["unchanged"], "="),
            "",
            f"Dirs added ({len(r.get('dirs_added', []))}):",
            *fmt([d + "/" for d in r.get("dirs_added", [])], "+"),
            "",
            f"Dirs removed ({len(r.get('dirs_removed', []))}):",
            *fmt([d + "/" for d in r.get("dirs_removed", [])], "-"),
            "",
        ]
        if r["errors"]:
            lines += [f"Errors ({len(r['errors'])}):", *[f"  ! {f}: {e}" for f, e in r["errors"]], ""]

        filepath.write_text("\n".join(lines), encoding="utf-8")
        return str(filepath)


# ──────────────────────────────────────────────────────────────
# Suite Reporter — combined report for multi-profile suite runs
# ──────────────────────────────────────────────────────────────

class SuiteReporter:
    """
    Formats and saves a combined report for a suite run.

    Parameters
    ----------
    suite_name : str
        Name of the suite that was run.
    runs : list of (profile_name, config, results) tuples
        One entry per successfully completed profile in the suite.
    dry_run : bool
        Whether the run was in dry-run mode.
    """

    def __init__(self, suite_name: str, runs: list, dry_run: bool = False):
        self.suite_name = suite_name
        self.runs = runs
        self.dry_run = dry_run
        self.timestamp = datetime.now()

    # ── Internal helpers ─────────────────────────────────────

    def _totals(self) -> dict:
        totals = {"added": 0, "updated": 0, "removed": 0, "unchanged": 0,
                  "dirs_added": 0, "dirs_removed": 0, "errors": 0}
        for _, _, results in self.runs:
            totals["added"]       += len(results["added"])
            totals["updated"]     += len(results["updated"])
            totals["removed"]     += len(results["removed"])
            totals["unchanged"]   += len(results["unchanged"])
            totals["dirs_added"]  += len(results.get("dirs_added", []))
            totals["dirs_removed"] += len(results.get("dirs_removed", []))
            totals["errors"]      += len(results["errors"])
        return totals

    def _print_profile_block(self, profile_name: str, config: dict, results: dict):
        """Print a single profile's result block to the terminal."""
        r = results
        click.echo(f"\n{'─'*60}")
        click.echo(f"  Profile : {profile_name}")
        click.echo(f"  Source  : {config['source']}")
        click.echo(f"  Target  : {config['target']}")
        click.echo(f"{'─'*60}")

        if r["added"]:
            click.echo(click.style(f"\n  ➕ Added ({len(r['added'])})", fg="green", bold=True))
            for f in r["added"]:
                click.echo(f"     {f}")

        if r.get("dirs_added"):
            click.echo(click.style(f"\n  📁 Dirs added ({len(r['dirs_added'])})", fg="green", bold=True))
            for d in r["dirs_added"]:
                click.echo(f"     {d}/")

        if r["updated"]:
            click.echo(click.style(f"\n  ✏️  Updated ({len(r['updated'])})", fg="yellow", bold=True))
            for f in r["updated"]:
                click.echo(f"     {f}")

        if r["removed"]:
            click.echo(click.style(f"\n  🗑️  Removed ({len(r['removed'])})", fg="red", bold=True))
            for f in r["removed"]:
                click.echo(f"     {f}")

        if r.get("dirs_removed"):
            click.echo(click.style(f"\n  📁 Dirs removed ({len(r['dirs_removed'])})", fg="red", bold=True))
            for d in r["dirs_removed"]:
                click.echo(f"     {d}/")

        if r["errors"]:
            click.echo(click.style(f"\n  ⚠️  Errors ({len(r['errors'])})", fg="bright_red", bold=True))
            for f, err in r["errors"]:
                click.echo(f"     {f}: {err}")

        total_changes = (
            len(r["added"]) + len(r["updated"]) + len(r["removed"])
            + len(r.get("dirs_added", [])) + len(r.get("dirs_removed", []))
        )
        click.echo(f"\n  {'·'*40}")
        if total_changes == 0:
            click.echo(click.style("  ✅  Already in sync.", fg="bright_green"))
        else:
            parts = []
            if r["added"]:               parts.append(f"{len(r['added'])} added")
            if r["updated"]:             parts.append(f"{len(r['updated'])} updated")
            if r["removed"]:             parts.append(f"{len(r['removed'])} removed")
            if r.get("dirs_added"):      parts.append(f"{len(r['dirs_added'])} dirs added")
            if r.get("dirs_removed"):    parts.append(f"{len(r['dirs_removed'])} dirs removed")
            label = "Would apply" if self.dry_run else "Applied"
            click.echo(f"  {label}: " + click.style(", ".join(parts), bold=True))
        click.echo(f"  Unchanged: {len(r['unchanged'])} files")

    # ── Public API ────────────────────────────────────────────

    def print_summary(self):
        mode = "DRY RUN" if self.dry_run else "LIVE"
        click.echo(f"\n{'═'*60}")
        click.echo(f"  Suite Report  [{mode}]  {self.timestamp.strftime('%Y-%m-%d %H:%M:%S')}")
        click.echo(f"  Suite    : {self.suite_name}")
        click.echo(f"  Profiles : {len(self.runs)}")
        click.echo(f"{'═'*60}")

        for profile_name, config, results in self.runs:
            self._print_profile_block(profile_name, config, results)

        # ── Totals ──
        t = self._totals()
        total_changes = t["added"] + t["updated"] + t["removed"] + t["dirs_added"] + t["dirs_removed"]
        click.echo(f"\n{'═'*60}")
        click.echo(click.style("  SUITE TOTALS", bold=True))
        click.echo(f"{'═'*60}")
        if total_changes == 0:
            click.echo(click.style("  ✅  All profiles already in sync.", fg="bright_green"))
        else:
            if t["added"]:        click.echo(click.style(f"  ➕ Added      : {t['added']}", fg="green"))
            if t["updated"]:      click.echo(click.style(f"  ✏️  Updated    : {t['updated']}", fg="yellow"))
            if t["removed"]:      click.echo(click.style(f"  🗑️  Removed    : {t['removed']}", fg="red"))
            if t["dirs_added"]:   click.echo(click.style(f"  📁 Dirs added  : {t['dirs_added']}", fg="green"))
            if t["dirs_removed"]: click.echo(click.style(f"  📁 Dirs removed: {t['dirs_removed']}", fg="red"))
        if t["errors"]:
            click.echo(click.style(f"  ⚠️  Errors     : {t['errors']}", fg="bright_red"))
        click.echo(f"  Unchanged: {t['unchanged']} files")
        click.echo(f"{'═'*60}\n")

    def save_report(self) -> str:
        REPORTS_DIR.mkdir(parents=True, exist_ok=True)
        filename = f"{self.suite_name}_{self.timestamp.strftime('%Y%m%d_%H%M%S')}.txt"
        filepath = REPORTS_DIR / filename

        def fmt(items, prefix):
            return [f"  {prefix} {f}" for f in items] if items else ["  (none)"]

        lines = [
            "mcru Suite Report",
            "=" * 60,
            f"Suite    : {self.suite_name}",
            f"Date     : {self.timestamp.isoformat(timespec='seconds')}",
            f"Mode     : {'DRY RUN' if self.dry_run else 'LIVE'}",
            f"Profiles : {len(self.runs)}",
            "=" * 60,
            "",
        ]

        for profile_name, config, results in self.runs:
            r = results
            lines += [
                "─" * 60,
                f"Profile  : {profile_name}",
                f"Source   : {config['source']}",
                f"Target   : {config['target']}",
                f"Parsers  : {', '.join(config.get('parsers', [])) or 'none'}",
                f"Mapping  : {config.get('mapping_preset') or 'none'}",
                "─" * 60,
                "",
                f"Added ({len(r['added'])}): (files)",
                *fmt(r["added"], "+"),
                "",
                f"Updated ({len(r['updated'])}):",
                *fmt(r["updated"], "~"),
                "",
                f"Removed ({len(r['removed'])}): (files)",
                *fmt(r["removed"], "-"),
                "",
                f"Unchanged ({len(r['unchanged'])}):",
                *fmt(r["unchanged"], "="),
                "",
                f"Dirs added ({len(r.get('dirs_added', []))}):",
                *fmt([d + "/" for d in r.get("dirs_added", [])], "+"),
                "",
                f"Dirs removed ({len(r.get('dirs_removed', []))}):",
                *fmt([d + "/" for d in r.get("dirs_removed", [])], "-"),
                "",
            ]
            if r["errors"]:
                lines += [f"Errors ({len(r['errors'])}):", *[f"  ! {f}: {e}" for f, e in r["errors"]], ""]

        t = self._totals()
        lines += [
            "=" * 60,
            "SUITE TOTALS",
            "=" * 60,
            f"Added    : {t['added']} (files)",
            f"Updated  : {t['updated']}",
            f"Removed  : {t['removed']} (files)",
            f"Unchanged: {t['unchanged']}",
            f"Dirs added   : {t['dirs_added']}",
            f"Dirs removed : {t['dirs_removed']}",
            f"Errors   : {t['errors']}",
        ]

        filepath.write_text("\n".join(lines), encoding="utf-8")
        return str(filepath)


# ──────────────────────────────────────────────────────────────────────────────
# Target Changelog Writer — writes CHANGELOG.md inside target folder
# ──────────────────────────────────────────────────────────────────────────────

class TargetChangelogWriter:
    """
    Prepends a Markdown changelog entry to CHANGELOG.md in the target folder.

    Only writes when the run is live (not dry-run) and at least one real
    change was made (added, updated, removed, or directory changes).

    Parameters
    ----------
    target_path : str | Path
        The synced target folder — CHANGELOG.md will be written here.
    profile_name : str
        Profile name included in the entry header.
    """

    CHANGELOG_FILENAME = "CHANGELOG.md"

    def __init__(self, target_path, profile_name: str):
        self.target_path = Path(target_path)
        self.profile_name = profile_name
        self.timestamp = datetime.now()

    def _has_changes(self, results: dict) -> bool:
        return bool(
            results.get("added") or results.get("updated") or results.get("removed")
            or results.get("dirs_added") or results.get("dirs_removed")
        )

    def _build_entry(self, results: dict, config: dict) -> str:
        r = results
        ts = self.timestamp.strftime("%Y-%m-%d %H:%M:%S")
        parsers = ", ".join(config.get("parsers", [])) or "none"
        mapping  = config.get("mapping_preset") or "none"

        summary_parts = []
        if r.get("added"):         summary_parts.append(f"{len(r['added'])} added")
        if r.get("updated"):       summary_parts.append(f"{len(r['updated'])} updated")
        if r.get("removed"):       summary_parts.append(f"{len(r['removed'])} removed")
        if r.get("dirs_added"):    summary_parts.append(f"{len(r['dirs_added'])} dirs added")
        if r.get("dirs_removed"):  summary_parts.append(f"{len(r['dirs_removed'])} dirs removed")
        if r.get("errors"):        summary_parts.append(f"{len(r['errors'])} errors")
        summary_str = ", ".join(summary_parts) or "no changes"

        lines = [
            f"## {ts} \u2014 {self.profile_name}",
            "",
            f"**Summary:** {summary_str}  ",
            f"**Source:** `{config.get('source', '\u2014')}`  ",
            f"**Target:** `{config.get('target', '\u2014')}`  ",
            f"**Parsers:** {parsers}  ",
            f"**Mapping:** {mapping}  ",
            "",
        ]

        def file_list(items, suffix=""):
            return [f"- `{f}{suffix}`" for f in items] if items else ["_(none)_"]

        if r.get("added"):
            lines += [f"### Added ({len(r['added'])})", *file_list(r["added"]), ""]

        if r.get("dirs_added"):
            lines += [f"### Dirs Added ({len(r['dirs_added'])})", *file_list(r["dirs_added"], "/"), ""]

        if r.get("updated"):
            lines += [f"### Updated ({len(r['updated'])})", *file_list(r["updated"]), ""]

        if r.get("removed"):
            lines += [f"### Removed ({len(r['removed'])})", *file_list(r["removed"]), ""]

        if r.get("dirs_removed"):
            lines += [f"### Dirs Removed ({len(r['dirs_removed'])})", *file_list(r["dirs_removed"], "/"), ""]

        if r.get("errors"):
            lines += [f"### Errors ({len(r['errors'])})",
                      *[f"- `{f}`: {err}" for f, err in r["errors"]], ""]

        lines += ["---", ""]
        return "\n".join(lines)

    def write(self, results: dict, config: dict) -> bool:
        """
        Prepend a changelog entry to CHANGELOG.md in the target folder.

        Returns True if the file was written, False if skipped (no changes).
        """
        if not self._has_changes(results):
            return False

        changelog_path = self.target_path / self.CHANGELOG_FILENAME
        new_entry = self._build_entry(results, config)
        existing = changelog_path.read_text(encoding="utf-8") if changelog_path.exists() else ""
        content = new_entry + ("\n" + existing if existing else "")
        changelog_path.write_text(content, encoding="utf-8")
        return True
