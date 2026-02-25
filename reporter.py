"""
Reporter - Formats and saves sync job results.

Prints a colour-coded summary to the terminal and saves
a timestamped .txt report to ~/.foldersyncer/reports/
"""

import click
from datetime import datetime
from pathlib import Path

REPORTS_DIR = Path.home() / ".foldersyncer" / "reports"


class Reporter:
    def __init__(self, profile_name: str, config: dict, results: dict, dry_run: bool = False):
        self.profile_name = profile_name
        self.config = config
        self.results = results
        self.dry_run = dry_run
        self.timestamp = datetime.now()

    def print_summary(self):
        r = self.results
        total_changes = len(r["added"]) + len(r["updated"]) + len(r["removed"])

        mode = "DRY RUN" if self.dry_run else "LIVE"
        click.echo(f"{'─'*60}")
        click.echo(f"  Sync Report  [{mode}]  {self.timestamp.strftime('%Y-%m-%d %H:%M:%S')}")
        click.echo(f"{'─'*60}")

        if r["added"]:
            click.echo(click.style(f"\n  ➕ Added ({len(r['added'])})", fg="green", bold=True))
            for f in r["added"]:
                click.echo(f"     {f}")

        if r["updated"]:
            click.echo(click.style(f"\n  ✏️  Updated ({len(r['updated'])})", fg="yellow", bold=True))
            for f in r["updated"]:
                click.echo(f"     {f}")

        if r["removed"]:
            click.echo(click.style(f"\n  🗑️  Removed ({len(r['removed'])})", fg="red", bold=True))
            for f in r["removed"]:
                click.echo(f"     {f}")

        if r["errors"]:
            click.echo(click.style(f"\n  ⚠️  Errors ({len(r['errors'])})", fg="bright_red", bold=True))
            for f, err in r["errors"]:
                click.echo(f"     {f}: {err}")

        click.echo(f"\n  {'─'*40}")
        if total_changes == 0:
            click.echo(click.style("  ✅  Folders are already in sync.", fg="bright_green"))
        else:
            summary = []
            if r["added"]:    summary.append(f"{len(r['added'])} added")
            if r["updated"]:  summary.append(f"{len(r['updated'])} updated")
            if r["removed"]:  summary.append(f"{len(r['removed'])} removed")
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
            "FolderSyncer Report",
            "=" * 60,
            f"Profile  : {self.profile_name}",
            f"Date     : {self.timestamp.isoformat(timespec='seconds')}",
            f"Mode     : {'DRY RUN' if self.dry_run else 'LIVE'}",
            f"Source   : {self.config['source']}",
            f"Target   : {self.config['target']}",
            f"Parsers  : {', '.join(self.config.get('parsers', [])) or 'none'}",
            "=" * 60,
            "",
            f"Added ({len(r['added'])}):",
            *fmt(r["added"], "+"),
            "",
            f"Updated ({len(r['updated'])}):",
            *fmt(r["updated"], "~"),
            "",
            f"Removed ({len(r['removed'])}):",
            *fmt(r["removed"], "-"),
            "",
            f"Unchanged ({len(r['unchanged'])}):",
            *fmt(r["unchanged"], "="),
            "",
        ]
        if r["errors"]:
            lines += [f"Errors ({len(r['errors'])}):", *[f"  ! {f}: {e}" for f, e in r["errors"]], ""]

        filepath.write_text("\n".join(lines))
        return str(filepath)
