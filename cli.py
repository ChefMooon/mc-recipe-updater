#!/usr/bin/env python3
"""
mcru - A CLI tool to compare and sync folders using saved config profiles.

Usage:
    mcru run <profile>                    # Run a saved profile or suite
    mcru profile add <name> <src> <tgt>   # Save a new profile
    mcru profile list                     # List all saved profiles
    mcru profile show <name>              # Show details for a single profile
    mcru profile remove <name>            # Remove a profile
    mcru profile update <name> <src> <tgt># Edit a saved profile
    mcru run <profile> --dry-run          # Preview without making changes
    mcru suite add <name>                 # Create a new suite
    mcru suite add-profile <suite> <profile>  # Add a profile to a suite
    mcru config show                      # Show the config directory path and file locations
    mcru config open                      # Open the config directory in the file explorer
    mcru reports show                     # Show the reports directory path and count
    mcru reports list                     # List saved reports with timestamps and sizes
    mcru reports open                     # Open the reports directory in the file explorer
    mcru reports view <name>              # Display the contents of a report
    mcru reports delete <name>            # Delete one or more reports
    mcru reports search <query>           # Search reports by profile or suite name
    mcru reports prune                    # Delete old reports by count, age, or all
"""

import json
import click
import subprocess
import sys
import shutil
from pathlib import Path
from config import ConfigManager, ReportManager, CONFIG_DIR, CONFIG_FILE, SUITES_FILE, DEFAULT_MAPPING_FILE, BUNDLED_MAPPING_FILE
from syncer import FolderSyncer
from reporter import Reporter, SuiteReporter, TargetChangelogWriter, REPORTS_DIR


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
    click.echo(f"    suites.json      : {SUITES_FILE}")
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
    CONFIG_FILE.write_text(json.dumps({"profiles": []}, indent=2))
    click.echo(f"✅  Created fresh: {CONFIG_FILE}")
    SUITES_FILE.write_text(json.dumps({"suites": []}, indent=2))
    click.echo(f"✅  Created fresh: {SUITES_FILE}")

    if BUNDLED_MAPPING_FILE.exists():
        shutil.copy2(BUNDLED_MAPPING_FILE, DEFAULT_MAPPING_FILE)
        click.echo(f"✅  Seeded: {DEFAULT_MAPPING_FILE}")

    click.echo("✅  Config reset complete.")


# ──────────────────────────────────────────────
# Reports
# ──────────────────────────────────────────────

@cli.group()
def reports():
    """View and manage saved run reports."""
    pass


@reports.command("show")
def reports_show():
    """Show the reports directory path."""
    click.echo(f"\n📁  Reports directory : {REPORTS_DIR}")
    if not REPORTS_DIR.exists():
        click.echo("    (directory does not exist yet — run a profile to generate reports)\n")
        return
    files = list(REPORTS_DIR.glob("*.txt"))
    click.echo(f"    {len(files)} report(s) saved\n")


@reports.command("list")
@click.option("--limit", "-l", default=None, type=int,
              help="Maximum number of reports to show (default: all).")
@click.option("--sort", default="date",
              type=click.Choice(["date", "name", "size"]),
              help="Sort order: date (newest first), name, or size (default: date).")
def reports_list(limit, sort):
    """List saved reports."""
    rm = ReportManager()
    items = rm.list_reports(limit=limit, sort_by=sort)
    if not items:
        click.echo("No reports found. Run a profile to generate one.")
        return
    header = f"\n{'FILENAME':<45} {'SIZE':>8}  {'DATE':<19}  PROFILE / SUITE"
    click.echo(header)
    click.echo("─" * len(header))
    for r in items:
        size_str = f"{r['size']:,} B" if r["size"] < 1024 else f"{r['size'] / 1024:.1f} KB"
        ts_str = r["timestamp"].strftime("%Y-%m-%d %H:%M:%S") if r["timestamp"] else "unknown"
        click.echo(f"{r['filename']:<45} {size_str:>8}  {ts_str:<19}  {r['name']}")
    click.echo()


@reports.command("open")
def reports_open():
    """Open the reports directory in the file explorer."""
    if not REPORTS_DIR.exists():
        click.echo("⚠️  Reports directory doesn't exist yet. Run a profile to generate reports.")
        return
    if sys.platform == "win32":
        subprocess.Popen(["explorer", str(REPORTS_DIR)])
    elif sys.platform == "darwin":
        subprocess.Popen(["open", str(REPORTS_DIR)])
    else:
        subprocess.Popen(["xdg-open", str(REPORTS_DIR)])
    click.echo(f"📂  Opened: {REPORTS_DIR}")


@reports.command("view")
@click.argument("name")
def reports_view(name):
    """Display the contents of a report.

    NAME is the report filename (with or without .txt extension).
    """
    rm = ReportManager()
    path = rm.find_report(name)
    if path is None:
        click.echo(f"❌  Report not found: '{name}'")
        click.echo(f"    Use 'mcru reports list' to see available reports.")
        return
    click.echo(path.read_text())


@reports.command("delete")
@click.argument("names", nargs=-1, required=True)
@click.option("--yes", "-y", is_flag=True, help="Skip confirmation prompt.")
def reports_delete(names, yes):
    """Delete one or more reports by filename.

    NAMES are report filenames (with or without .txt extension).
    """
    rm = ReportManager()
    to_delete = []
    for name in names:
        path = rm.find_report(name)
        if path is None:
            click.echo(f"⚠️  Not found, skipping: '{name}'")
        else:
            to_delete.append(path)

    if not to_delete:
        click.echo("Nothing to delete.")
        return

    click.echo(f"Reports to delete ({len(to_delete)}):")
    for p in to_delete:
        click.echo(f"  {p.name}")

    if not yes and not click.confirm("Delete these reports?"):
        click.echo("Cancelled.")
        return

    total_freed = 0
    for p in to_delete:
        total_freed += p.stat().st_size
        rm.delete_report(p)
    freed_str = f"{total_freed / 1024:.1f} KB" if total_freed >= 1024 else f"{total_freed} B"
    click.echo(f"🗑️  Deleted {len(to_delete)} report(s), freed {freed_str}.")


@reports.command("search")
@click.argument("query")
def reports_search(query):
    """Search reports by profile or suite name.

    QUERY is a case-insensitive substring matched against the profile/suite name.
    """
    rm = ReportManager()
    results = rm.search_reports(query)
    if not results:
        click.echo(f"No reports matching '{query}'.")
        return
    click.echo(f"\nFound {len(results)} report(s) matching '{query}':\n")
    for r in results:
        ts_str = r["timestamp"].strftime("%Y-%m-%d %H:%M:%S") if r["timestamp"] else "unknown"
        size_str = f"{r['size'] / 1024:.1f} KB" if r["size"] >= 1024 else f"{r['size']} B"
        click.echo(f"  {r['filename']}  ({size_str}, {ts_str})")
    click.echo()


@reports.command("prune")
@click.option("--keep", default=None, type=int,
              help="Keep only the N most recent reports; delete the rest.")
@click.option("--older-than", "older_than", default=None, type=int, metavar="DAYS",
              help="Delete reports older than DAYS days.")
@click.option("--all", "delete_all", is_flag=True,
              help="Delete all reports.")
@click.option("--dry-run", is_flag=True,
              help="Preview which reports would be deleted without deleting them.")
@click.option("--yes", "-y", is_flag=True, help="Skip confirmation prompt.")
def reports_prune(keep, older_than, delete_all, dry_run, yes):
    """Delete old reports by age, count, or all.

    Strategies can be combined: e.g. keep last 10 AND delete anything older than 60 days.

    \b
    Examples:
      mcru reports prune --keep 10
      mcru reports prune --older-than 30
      mcru reports prune --keep 5 --older-than 90
      mcru reports prune --all
      mcru reports prune --keep 10 --dry-run
    """
    if not delete_all and keep is None and older_than is None:
        click.echo("❌  Specify at least one option: --keep N, --older-than DAYS, or --all.")
        click.echo("    Run 'mcru reports prune --help' for usage.")
        return

    rm = ReportManager()
    result = rm.prune_reports(
        keep_count=keep,
        older_than_days=older_than,
        delete_all=delete_all,
        dry_run=True,  # always preview first
    )

    if not result["deleted"]:
        click.echo("Nothing to prune — no reports match the given criteria.")
        return

    freed_str = (
        f"{result['space_freed'] / 1024:.1f} KB"
        if result["space_freed"] >= 1024
        else f"{result['space_freed']} B"
    )
    label = "Would delete" if dry_run else "About to delete"
    click.echo(f"{label} {len(result['deleted'])} report(s), freeing ~{freed_str}:")
    for p in result["deleted"]:
        click.echo(f"  {p.name}")

    if dry_run:
        click.echo("\n(Dry run — no files were deleted.)")
        return

    if not yes and not click.confirm("\nProceed with deletion?"):
        click.echo("Cancelled.")
        return

    rm.prune_reports(
        keep_count=keep,
        older_than_days=older_than,
        delete_all=delete_all,
        dry_run=False,
    )
    click.echo(f"🗑️  Pruned {len(result['deleted'])} report(s), freed ~{freed_str}.")


# ──────────────────────────────────────────────
# Profile Management
# ──────────────────────────────────────────────

@cli.group()
def profile():
    """Save and manage sync profiles."""
    pass


@profile.command("add")
@click.argument("name")
@click.argument("source")
@click.argument("target")
@click.option("--parser", "-p", multiple=True,
              type=click.Choice(["strip_bom", "normalize_line_endings", "lowercase_names"]),
              help="Apply one or more parsers to source files before comparing.")
@click.option("--description", "-d", default="", help="Optional description for this profile.")
@click.option("--mapping", default=None, help="Optional mapping preset name (from mapping-presets.json).")
@click.option("--target-changelog", is_flag=True, default=False,
              help="Append a Markdown changelog entry to CHANGELOG.md in the target folder on every live run.")
def profile_add(name, source, target, parser, description, mapping, target_changelog):
    """Save a new sync profile.\n
    Example: mcru profile add myproject ./src ./dist --parser normalize_line_endings
    """
    cm = ConfigManager()
    cm.add_profile(name, source, target, list(parser), description, mapping, target_changelog)
    click.echo(f"✅  Profile '{name}' saved.")
    click.echo(f"    Source : {source}")
    click.echo(f"    Target : {target}")
    if parser:
        click.echo(f"    Parsers: {', '.join(parser)}")
    if mapping:
        click.echo(f"    Mapping: {mapping}")
    if target_changelog:
        click.echo(f"    Target changelog: enabled")


@profile.command("list")
def profile_list():
    """List all saved sync profiles."""
    cm = ConfigManager()
    profiles = cm.list_profiles()
    if not profiles:
        click.echo("No profiles saved yet. Use 'mcru profile add' to create one.")
        return
    click.echo(f"\n{'NAME':<20} {'SOURCE':<30} {'TARGET':<30} {'PARSERS':<20} MAPPING")
    click.echo("─" * 125)
    for p in profiles:
        parsers = ", ".join(p.get("parsers", [])) or "—"
        mapping = p.get("mapping_preset") or "—"
        click.echo(f"{p['name']:<20} {p['source']:<30} {p['target']:<30} {parsers:<20} {mapping}")
    click.echo()


@profile.command("show")
@click.argument("name")
def profile_show(name):
    """Show all details for a single saved profile."""
    cm = ConfigManager()
    p = cm.get_profile(name)
    if p is None:
        click.echo(f"❌  Profile '{name}' not found.")
        return
    click.echo(f"\nProfile : {p['name']}")
    if p.get("description"):
        click.echo(f"Desc    : {p['description']}")
    click.echo("─" * 40)
    click.echo(f"  Source  : {p['source']}")
    click.echo(f"  Target  : {p['target']}")
    parsers = ", ".join(p.get("parsers", [])) or "—"
    click.echo(f"  Parsers : {parsers}")
    mapping = p.get("mapping_preset") or "—"
    click.echo(f"  Mapping : {mapping}")
    click.echo(f"  Target changelog: {'enabled' if p.get('target_changelog') else 'disabled'}")
    if p.get("created_at"):
        click.echo(f"  Created : {p['created_at']}")
    click.echo()


@profile.command("remove")
@click.argument("name")
def profile_remove(name):
    """Remove a saved profile."""
    cm = ConfigManager()
    cm.remove_profile(name)
    click.echo(f"🗑️  Profile '{name}' removed.")


@profile.command("update")
@click.argument("name")
@click.argument("source")
@click.argument("target")
@click.option("--parser", "-p", multiple=True,
              type=click.Choice(["strip_bom", "normalize_line_endings", "lowercase_names"]))
@click.option("--description", "-d", default="")
@click.option("--mapping", default=None, help="Optional mapping preset name (from mapping-presets.json).")
@click.option("--target-changelog", is_flag=True, default=False,
              help="Enable target changelog for this profile.")
def profile_update(name, source, target, parser, description, mapping, target_changelog):
    """Update an existing profile.\n
    Example: mcru profile update myproject ./src ./dist
    """
    cm = ConfigManager()
    cm.add_profile(name, source, target, list(parser), description, mapping, target_changelog)
    click.echo(f"✏️  Profile '{name}' updated.")


# ──────────────────────────────────────────────
# Run a Sync Job
# ──────────────────────────────────────────────

@cli.command()
@click.argument("profile")
@click.option("--dry-run", is_flag=True, help="Preview changes without applying them.")
@click.option("--no-report", is_flag=True, help="Skip saving the report file.")
@click.option("--source", default=None, help="Override the source folder for this run (applies to every profile in a suite).")
@click.option("--target", default=None, help="Override the target folder for this run (applies to every profile in a suite).")
@click.option("--mapping", default=None, help="Mapping preset name. Overrides profile/suite mapping if set.")
@click.option("--target-changelog", is_flag=True, default=False,
              help="Prepend a Markdown entry to CHANGELOG.md in the target folder on every live run (overrides profile setting).")
def run(profile, dry_run, no_report, source, target, mapping, target_changelog):
    """Run a sync job using a saved profile or suite.\n
    If the name matches a suite, all profiles in the suite are run in order
    and a single combined report is produced.\n
    Example: mcru run myproject --dry-run
    """
    cm = ConfigManager()
    config = cm.get_profile(profile)

    # ── Suite run ──────────────────────────────────────────────
    if config is None:
        suite = cm.get_suite(profile)
        if suite is None:
            click.echo(f"❌  '{profile}' not found. "
                       "Run 'mcru profile list' to see profiles or 'mcru suite list' for suites.")
            return

        mode_label = "DRY RUN" if dry_run else "LIVE"
        click.echo(f"\n🗂️  Running suite  : {profile}")
        click.echo(f"    Profiles      : {len(suite['profiles'])}")
        click.echo(f"    Mode          : {mode_label}\n")

        if not suite["profiles"]:
            click.echo("⚠️  Suite has no profiles. Add some with 'mcru suite add-profile'.")
            return

        runs = []
        for pname in suite["profiles"]:
            pcfg = cm.get_profile(pname)
            if pcfg is None:
                click.echo(f"  ⚠️  Profile '{pname}' not found — skipping.")
                continue

            if source:
                pcfg["source"] = source
            if target:
                pcfg["target"] = target

            active_mapping = mapping or pcfg.get("mapping_preset")
            if active_mapping:
                try:
                    pcfg["mapping"] = cm.get_mapping_preset(active_mapping)
                except (FileNotFoundError, ValueError) as err:
                    click.echo(f"  ⚠️  Profile '{pname}' mapping error: {err} — skipping.")
                    continue
                pcfg["mapping_preset"] = active_mapping

            click.echo(f"  ▶  {pname}")
            click.echo(f"     Source : {pcfg['source']}")
            click.echo(f"     Target : {pcfg['target']}")
            if pcfg.get("mapping_preset"):
                click.echo(f"     Mapping: {pcfg['mapping_preset']}")

            syncer = FolderSyncer(pcfg, dry_run=dry_run)
            try:
                results = syncer.run()
            except ValueError as err:
                click.echo(f"  ❌  {pname}: {err} — skipping.")
                continue
            runs.append((pname, pcfg, results))

            if (target_changelog or pcfg.get("target_changelog")) and not dry_run:
                writer = TargetChangelogWriter(pcfg["target"], pname)
                writer.write(results, pcfg)

        if not runs:
            click.echo("\n❌  No profiles ran successfully.")
            return

        suite_reporter = SuiteReporter(profile, runs, dry_run=dry_run)
        suite_reporter.print_summary()

        if not no_report:
            report_path = suite_reporter.save_report()
            click.echo(f"\n📄  Suite report saved to: {report_path}")

        changelog_profiles = [
            pname for pname, pcfg, _ in runs
            if target_changelog or pcfg.get("target_changelog")
        ]
        if changelog_profiles and not dry_run:
            click.echo(f"\n📋  Changelog updated for: {', '.join(changelog_profiles)}")
        return

    # ── Single profile run ─────────────────────────────────────────

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

    if (target_changelog or config.get("target_changelog")) and not dry_run:
        writer = TargetChangelogWriter(config["target"], profile)
        if writer.write(results, config):
            changelog_path = Path(config["target"]) / TargetChangelogWriter.CHANGELOG_FILENAME
            click.echo(f"\n📋  Changelog updated: {changelog_path}")


# ──────────────────────────────────────────────
# Suite Management
# ──────────────────────────────────────────────

@cli.group()
def suite():
    """Create and manage suites (ordered groups of profiles run together)."""
    pass


@suite.command("add")
@click.argument("name")
@click.option("--description", "-d", default="", help="Optional description for the suite.")
def suite_add(name, description):
    """Create a new empty suite.\n
    Example: mcru suite add full-sync -d "Sync all mods"
    """
    cm = ConfigManager()
    if cm.get_suite(name):
        click.echo(f"⚠️  Suite '{name}' already exists. Use 'suite remove' then 'suite add' to recreate it.")
        return
    cm.save_suite(name, description=description)
    click.echo(f"✅  Suite '{name}' created.")


@suite.command("remove")
@click.argument("name")
def suite_remove(name):
    """Delete a suite. The profiles within it are not affected."""
    cm = ConfigManager()
    try:
        cm.delete_suite(name)
    except ValueError as err:
        click.echo(f"❌  {err}")
        return
    click.echo(f"🗑️  Suite '{name}' removed.")


@suite.command("list")
def suite_list():
    """List all saved suites."""
    cm = ConfigManager()
    suites = cm.list_suites()
    if not suites:
        click.echo("No suites saved yet. Use 'mcru suite add <name>' to create one.")
        return
    click.echo(f"\n{'NAME':<20} {'PROFILES':<10} DESCRIPTION")
    click.echo("─" * 60)
    for s in suites:
        desc = s.get("description") or "—"
        click.echo(f"{s['name']:<20} {len(s.get('profiles', [])):<10} {desc}")
    click.echo()


@suite.command("show")
@click.argument("name")
def suite_show(name):
    """Show the ordered profile list for a suite."""
    cm = ConfigManager()
    s = cm.get_suite(name)
    if s is None:
        click.echo(f"❌  Suite '{name}' not found.")
        return
    profiles = s.get("profiles", [])
    click.echo(f"\nSuite : {s['name']}")
    if s.get("description"):
        click.echo(f"Desc  : {s['description']}")
    click.echo("─" * 40)
    if not profiles:
        click.echo("  (no profiles — add some with 'mcru suite add-profile')")
    else:
        for i, pname in enumerate(profiles, 1):
            flag = "" if cm.get_profile(pname) else "  ⚠️  (profile not found)"
            click.echo(f"  {i:>3}. {pname}{flag}")
    click.echo()


@suite.command("update")
@click.argument("name")
@click.option("--description", "-d", required=True, help="New description for the suite.")
def suite_update(name, description):
    """Update a suite's description.\n
    Example: mcru suite update full-sync -d "New description"
    """
    cm = ConfigManager()
    try:
        cm.update_suite_description(name, description)
    except ValueError as err:
        click.echo(f"\u274c  {err}")
        return
    click.echo(f"\u2705  Suite '{name}' description updated.")


@suite.command("add-profile")
@click.argument("suite_name")
@click.argument("profile_name")
def suite_add_profile(suite_name, profile_name):
    """Append a profile to a suite.\n
    Example: mcru suite add-profile full-sync mod-a
    """
    cm = ConfigManager()
    try:
        cm.add_profile_to_suite(suite_name, profile_name)
    except ValueError as err:
        click.echo(f"❌  {err}")
        return
    click.echo(f"✅  Profile '{profile_name}' added to suite '{suite_name}'.")


@suite.command("remove-profile")
@click.argument("suite_name")
@click.argument("profile_name")
def suite_remove_profile(suite_name, profile_name):
    """Remove a profile from a suite. The profile itself is not deleted.\n
    Example: mcru suite remove-profile full-sync mod-a
    """
    cm = ConfigManager()
    try:
        cm.remove_profile_from_suite(suite_name, profile_name)
    except ValueError as err:
        click.echo(f"❌  {err}")
        return
    click.echo(f"🗑️  Profile '{profile_name}' removed from suite '{suite_name}'.")


@suite.command("reorder")
@click.argument("suite_name")
@click.argument("profile_name")
@click.argument("position", type=int)
def suite_reorder(suite_name, profile_name, position):
    """Move a profile to a specific position in a suite (1-based).\n
    Example: mcru suite reorder full-sync mod-a 1
    """
    cm = ConfigManager()
    try:
        cm.reorder_profile_in_suite(suite_name, profile_name, position)
    except ValueError as err:
        click.echo(f"❌  {err}")
        return
    click.echo(f"✅  '{profile_name}' moved to position {position} in suite '{suite_name}'.")


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
