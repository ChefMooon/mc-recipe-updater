#!/usr/bin/env python3
"""
mcru - A CLI tool to compare and sync folders using saved config profiles.

Usage:
    mcru run <profile>           # Run a saved profile
    mcru add <name> <src> <tgt>  # Save a new profile
    mcru list                    # List all saved profiles
    mcru remove <name>           # Remove a profile
    mcru run <profile> --dry-run # Preview without making changes
    mcru config show             # Show the config directory path and file locations
    mcru config open             # Open the config directory in the file explorer
"""

import click
import subprocess
import sys
import shutil
from config import ConfigManager, CONFIG_DIR, CONFIG_FILE, DEFAULT_MAPPING_FILE, BUNDLED_MAPPING_FILE
from syncer import FolderSyncer
from reporter import Reporter, REPORTS_DIR


@click.group()
def cli():
    """mcru - Compare and sync folders using saved profiles."""
    pass


# ──────────────────────────────────────────────
# Config directory
# ──────────────────────────────────────────────

@cli.group()
def config():
    """View or open the mcru config directory."""
    pass


@config.command("show")
def config_show():
    """Show the config directory path and file locations."""
    click.echo(f"\n📁  Config directory : {CONFIG_DIR}")
    click.echo(f"    profiles.json    : {CONFIG_FILE}")
    click.echo(f"    mapping-presets  : {DEFAULT_MAPPING_FILE}")
    click.echo(f"    reports/         : {REPORTS_DIR}\n")


@config.command("open")
def config_open():
    """Open the config directory in the file explorer."""
    if not CONFIG_DIR.exists():
        click.echo("⚠️  Config directory doesn't exist yet. Run any mcru command to create it.")
        return
    if sys.platform == "win32":
        subprocess.Popen(["explorer", str(CONFIG_DIR)])
    elif sys.platform == "darwin":
        subprocess.Popen(["open", str(CONFIG_DIR)])
    else:
        subprocess.Popen(["xdg-open", str(CONFIG_DIR)])
    click.echo(f"📂  Opened: {CONFIG_DIR}")


@config.command("reset-presets")
def config_reset_presets():
    """Reset mapping presets to package defaults.\n
    Deletes ~/.mcru/mapping-presets.json and re-seeds it from the bundled defaults.
    """
    if DEFAULT_MAPPING_FILE.exists():
        DEFAULT_MAPPING_FILE.unlink()
        click.echo(f"🗑️  Deleted: {DEFAULT_MAPPING_FILE}")
    
    if BUNDLED_MAPPING_FILE.exists():
        shutil.copy2(BUNDLED_MAPPING_FILE, DEFAULT_MAPPING_FILE)
        click.echo(f"✅  Re-seeded: {DEFAULT_MAPPING_FILE}")
    else:
        click.echo(f"⚠️  Bundled mapping file not found: {BUNDLED_MAPPING_FILE}")


@config.command("reset")
def config_reset():
    """Reset all configs: profiles, mapping presets, and reports.\n
    WARNING: This will delete all saved profiles, custom presets, and reports!
    """
    if not click.confirm("⚠️  This will delete all ~/.mcru/ data (profiles, presets, reports). Continue?"):
        click.echo("Cancelled.")
        return
    
    if CONFIG_DIR.exists():
        shutil.rmtree(CONFIG_DIR)
        click.echo(f"🗑️  Deleted: {CONFIG_DIR}")
    
    # Recreate and seed
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_FILE.write_text("{\"profiles\": []}")
    click.echo(f"✅  Created fresh: {CONFIG_FILE}")
    
    if BUNDLED_MAPPING_FILE.exists():
        shutil.copy2(BUNDLED_MAPPING_FILE, DEFAULT_MAPPING_FILE)
        click.echo(f"✅  Seeded: {DEFAULT_MAPPING_FILE}")
    
    click.echo("✅  Config reset complete.")



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
@click.option("--mapping", default=None, help="Optional mapping preset name (from mapping-presets.json).")
def add(name, source, target, parser, description, mapping):
    """Save a new sync profile.\n
    Example: mcru add myproject ./src ./dist --parser normalize_line_endings
    """
    cm = ConfigManager()
    cm.add_profile(name, source, target, list(parser), description, mapping)
    click.echo(f"✅  Profile '{name}' saved.")
    click.echo(f"    Source : {source}")
    click.echo(f"    Target : {target}")
    if parser:
        click.echo(f"    Parsers: {', '.join(parser)}")
    if mapping:
        click.echo(f"    Mapping: {mapping}")


@cli.command("list")
def list_profiles():
    """List all saved sync profiles."""
    cm = ConfigManager()
    profiles = cm.list_profiles()
    if not profiles:
        click.echo("No profiles saved yet. Use 'add' to create one.")
        return
    click.echo(f"\n{'NAME':<20} {'SOURCE':<30} {'TARGET':<30} {'PARSERS':<20} MAPPING")
    click.echo("─" * 125)
    for p in profiles:
        parsers = ", ".join(p.get("parsers", [])) or "—"
        mapping = p.get("mapping_preset") or "—"
        click.echo(f"{p['name']:<20} {p['source']:<30} {p['target']:<30} {parsers:<20} {mapping}")
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
@click.option("--mapping", default=None, help="Optional mapping preset name (from mapping-presets.json).")
def update(name, source, target, parser, description, mapping):
    """Update an existing profile."""
    cm = ConfigManager()
    cm.add_profile(name, source, target, list(parser), description, mapping)
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
@click.option("--mapping", default=None, help="Mapping preset name. Overrides profile mapping if set.")
def run(profile, dry_run, no_report, source, target, mapping):
    """Run a sync job using a saved profile.\n
    Example: mcru run myproject --dry-run
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

    active_mapping = mapping or config.get("mapping_preset")
    if active_mapping:
        try:
            config["mapping"] = cm.get_mapping_preset(active_mapping)
        except (FileNotFoundError, ValueError) as err:
            click.echo(f"❌  {err}")
            return
        config["mapping_preset"] = active_mapping

    click.echo(f"\n🔍  Running profile: {profile}")
    click.echo(f"    Source : {config['source']}")
    click.echo(f"    Target : {config['target']}")
    if config.get("parsers"):
        click.echo(f"    Parsers: {', '.join(config['parsers'])}")
    if config.get("mapping_preset"):
        click.echo(f"    Mapping: {config['mapping_preset']}")
    if dry_run:
        click.echo("    Mode   : DRY RUN (no changes will be made)\n")
    else:
        click.echo("    Mode   : LIVE\n")

    syncer = FolderSyncer(config, dry_run=dry_run)
    try:
        results = syncer.run()
    except ValueError as err:
        click.echo(f"❌  {err}")
        return

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
@click.option("--mapping", default=None, help="Optional mapping preset name.")
def quick(source, target, dry_run, parser, mapping):
    """Quick one-off compare without saving a profile.\n
    Example: mcru quick ./src ./dist --dry-run
    """
    config = {"source": source, "target": target, "parsers": list(parser)}
    if mapping:
        cm = ConfigManager()
        try:
            config["mapping"] = cm.get_mapping_preset(mapping)
            config["mapping_preset"] = mapping
        except (FileNotFoundError, ValueError) as err:
            click.echo(f"❌  {err}")
            return

    syncer = FolderSyncer(config, dry_run=dry_run)
    try:
        results = syncer.run()
    except ValueError as err:
        click.echo(f"❌  {err}")
        return
    reporter = Reporter("quick-run", config, results, dry_run=dry_run)
    reporter.print_summary()


if __name__ == "__main__":
    cli()
