#!/usr/bin/env python3
"""
FolderSyncer - A CLI tool to compare and sync folders using saved config profiles.

Usage:
    python cli.py run <profile>           # Run a saved profile
    python cli.py add <name> <src> <tgt>  # Save a new profile
    python cli.py list                    # List all saved profiles
    python cli.py remove <name>           # Remove a profile
    python cli.py run <profile> --dry-run # Preview without making changes
"""

import click
from config import ConfigManager
from syncer import FolderSyncer
from reporter import Reporter


@click.group()
def cli():
    """FolderSyncer - Compare and sync folders using saved profiles."""
    pass


# ──────────────────────────────────────────────
# Profile Management
# ──────────────────────────────────────────────

@cli.command()
@click.argument("name")
@click.argument("source")
@click.argument("target")
@click.option("--parser", "-p", multiple=True,
              type=click.Choice(["strip_bom", "normalize_line_endings", "lowercase_names"]),
              help="Apply one or more parsers to source files before comparing.")
@click.option("--description", "-d", default="", help="Optional description for this profile.")
def add(name, source, target, parser, description):
    """Save a new sync profile.\n
    Example: foldersyncer add myproject ./src ./dist --parser normalize_line_endings
    """
    cm = ConfigManager()
    cm.add_profile(name, source, target, list(parser), description)
    click.echo(f"✅  Profile '{name}' saved.")
    click.echo(f"    Source : {source}")
    click.echo(f"    Target : {target}")
    if parser:
        click.echo(f"    Parsers: {', '.join(parser)}")


@cli.command("list")
def list_profiles():
    """List all saved sync profiles."""
    cm = ConfigManager()
    profiles = cm.list_profiles()
    if not profiles:
        click.echo("No profiles saved yet. Use 'add' to create one.")
        return
    click.echo(f"\n{'NAME':<20} {'SOURCE':<35} {'TARGET':<35} PARSERS")
    click.echo("─" * 100)
    for p in profiles:
        parsers = ", ".join(p.get("parsers", [])) or "—"
        click.echo(f"{p['name']:<20} {p['source']:<35} {p['target']:<35} {parsers}")
    click.echo()


@cli.command()
@click.argument("name")
def remove(name):
    """Remove a saved profile."""
    cm = ConfigManager()
    cm.remove_profile(name)
    click.echo(f"🗑️  Profile '{name}' removed.")


@cli.command()
@click.argument("name")
@click.argument("source")
@click.argument("target")
@click.option("--parser", "-p", multiple=True,
              type=click.Choice(["strip_bom", "normalize_line_endings", "lowercase_names"]))
@click.option("--description", "-d", default="")
def update(name, source, target, parser, description):
    """Update an existing profile."""
    cm = ConfigManager()
    cm.add_profile(name, source, target, list(parser), description)
    click.echo(f"✏️  Profile '{name}' updated.")


# ──────────────────────────────────────────────
# Run a Sync Job
# ──────────────────────────────────────────────

@cli.command()
@click.argument("profile")
@click.option("--dry-run", is_flag=True, help="Preview changes without applying them.")
@click.option("--no-report", is_flag=True, help="Skip saving the report file.")
@click.option("--source", default=None, help="Override the source folder for this run.")
@click.option("--target", default=None, help="Override the target folder for this run.")
def run(profile, dry_run, no_report, source, target):
    """Run a sync job using a saved profile.\n
    Example: foldersyncer run myproject --dry-run
    """
    cm = ConfigManager()
    config = cm.get_profile(profile)

    if config is None:
        click.echo(f"❌  Profile '{profile}' not found. Run 'list' to see available profiles.")
        return

    # Allow one-off overrides without changing the saved profile
    if source:
        config["source"] = source
    if target:
        config["target"] = target

    click.echo(f"\n🔍  Running profile: {profile}")
    click.echo(f"    Source : {config['source']}")
    click.echo(f"    Target : {config['target']}")
    if config.get("parsers"):
        click.echo(f"    Parsers: {', '.join(config['parsers'])}")
    if dry_run:
        click.echo("    Mode   : DRY RUN (no changes will be made)\n")
    else:
        click.echo("    Mode   : LIVE\n")

    syncer = FolderSyncer(config, dry_run=dry_run)
    results = syncer.run()

    reporter = Reporter(profile, config, results, dry_run=dry_run)
    reporter.print_summary()

    if not no_report:
        report_path = reporter.save_report()
        click.echo(f"\n📄  Report saved to: {report_path}")


# ──────────────────────────────────────────────
# Quick one-off run (no saved profile)
# ──────────────────────────────────────────────

@cli.command()
@click.argument("source")
@click.argument("target")
@click.option("--dry-run", is_flag=True)
@click.option("--parser", "-p", multiple=True,
              type=click.Choice(["strip_bom", "normalize_line_endings", "lowercase_names"]))
def quick(source, target, dry_run, parser):
    """Quick one-off compare without saving a profile.\n
    Example: foldersyncer quick ./src ./dist --dry-run
    """
    config = {"source": source, "target": target, "parsers": list(parser)}
    syncer = FolderSyncer(config, dry_run=dry_run)
    results = syncer.run()
    reporter = Reporter("quick-run", config, results, dry_run=dry_run)
    reporter.print_summary()


if __name__ == "__main__":
    cli()
