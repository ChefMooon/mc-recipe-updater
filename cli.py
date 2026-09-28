#!/usr/bin/env python3
"""
mcru - A CLI tool to compare and sync folders using saved config profiles.

Usage:
    mcru run <profile>                    # Run a saved profile or suite
    mcru profile add <name> <src> <tgt>   # Save a new profile
    mcru profile list                     # List all saved profiles
    mcru profile show <name>              # Show details for a single profile
    mcru profile verify <name>            # Verify that source and target folders exist
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
import os
import click
import subprocess
import sys
import shutil
from pathlib import Path
from config import ConfigManager, ReportManager, CONFIG_DIR, CONFIG_FILE, SUITES_FILE, DEFAULT_MAPPING_FILE, BUNDLED_MAPPING_FILE, GlobalConfig
from syncer import MCRU
from backup import BackupManager, BACKUPS_DIR
from reporter import Reporter, SuiteReporter, TargetChangelogWriter, ProfileListFormatter, REPORTS_DIR


SNAPSHOT_EXCLUDED_NAMES = {
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    "build",
    "dist",
}

_RESULT_MUTATION_KEYS = ("added", "updated", "removed", "dirs_added", "dirs_removed")


def _result_outcome(results: dict) -> str:
    rollback_complete = results.get("rollback_complete")
    if rollback_complete is False:
        return "partial"
    if rollback_complete is True:
        return "failed"
    if results.get("errors"):
        retained_changes = sum(len(results.get(key, [])) for key in _RESULT_MUTATION_KEYS)
        return "partial" if retained_changes else "failed"
    return "success"


def _suite_outcome(runs: list[tuple[str, dict, dict]]) -> str:
    results = [result for _, _, result in runs]
    if any(result.get("rollback_complete") is False for result in results):
        return "partial"
    if any(
        result.get("rollback_complete") is True or result.get("errors")
        for result in results
    ):
        retained_changes = sum(
            len(result.get(key, []))
            for result in results
            for key in _RESULT_MUTATION_KEYS
        )
        return "partial" if retained_changes else "failed"
    return "success"


def _is_snapshot_excluded_name(name: str) -> bool:
    lowered = name.lower()
    return (
        name in SNAPSHOT_EXCLUDED_NAMES
        or lowered.endswith(".egg-info")
        or lowered.startswith("bdist.")
    )


def _collect_snapshot_paths(base_path: Path, scan_roots: list[Path]) -> tuple[set[str], set[str]]:
    folders = set()
    files = set()

    for root in scan_roots:
        if not root.exists() or not root.is_dir():
            continue

        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [d for d in dirnames if not _is_snapshot_excluded_name(d)]
            current = Path(dirpath)
            current_rel = current.relative_to(base_path).as_posix()
            if current_rel != ".":
                folders.add(current_rel)

            for filename in filenames:
                if _is_snapshot_excluded_name(filename):
                    continue
                file_rel = (current / filename).relative_to(base_path).as_posix()
                files.add(file_rel)

    return folders, files


def _build_snapshot_tree(folders: set[str], files: set[str]) -> dict:
    tree = {"dirs": {}, "files": []}

    for folder in sorted(folders):
        node = tree
        for part in Path(folder).parts:
            node = node["dirs"].setdefault(part, {"dirs": {}, "files": []})

    for file_path in sorted(files):
        node = tree
        path_obj = Path(file_path)
        for part in path_obj.parts[:-1]:
            node = node["dirs"].setdefault(part, {"dirs": {}, "files": []})
        node["files"].append(path_obj.name)

    return tree


def _render_snapshot_tree(tree: dict, indent: str = "", dir_icon: str | None = None, file_icon: str | None = None) -> list[str]:
    if dir_icon is None or file_icon is None:
        dir_icon, file_icon = _snapshot_icons()
    lines = []
    for dirname in sorted(tree["dirs"].keys()):
        lines.append(f"{indent}{dir_icon} {dirname}/")
        lines.extend(_render_snapshot_tree(tree["dirs"][dirname], indent + "  ", dir_icon, file_icon))
    for filename in sorted(tree["files"]):
        lines.append(f"{indent}{file_icon} {filename}")
    return lines


def _snapshot_icons() -> tuple[str, str]:
    encoding = getattr(sys.stdout, "encoding", None) or "utf-8"
    try:
        "📁📄".encode(encoding)
    except (UnicodeEncodeError, LookupError):
        return "[D]", "[F]"
    return "📁", "📄"


def _resolve_snapshot_scope(profile_config: dict, manager: ConfigManager) -> dict:
    source_base = Path(profile_config["source"])
    target_base = Path(profile_config["target"])
    mapping_name = profile_config.get("mapping_preset")

    if not mapping_name:
        return {
            "mapping_name": None,
            "mapping": None,
            "source_roots": [source_base],
            "target_roots": [target_base],
        }

    mapping = manager.get_mapping_preset(mapping_name)
    scoped_config = dict(profile_config)
    scoped_config["mapping"] = mapping
    scoped_runner = MCRU(scoped_config, dry_run=True)

    source_roots = []
    source_roots_raw = mapping.get("source_roots", {})
    category_map = mapping.get("category_map", {})
    target_roots_map = mapping.get("target_roots", {})
    rules = mapping.get("rules", {})

    for source_category in category_map.keys():
        source_dirs = scoped_runner._resolve_source_dirs(source_category, source_roots_raw)
        source_roots.extend(source_dirs)

    target_categories = sorted(set(category_map.values()))
    target_roots = []
    for target_category in target_categories:
        mapped_target_root = target_roots_map.get(target_category)
        if mapped_target_root is None:
            raise ValueError(
                f"Mapping target category '{target_category}' has no target root."
            )
        target_roots.append(target_base / mapped_target_root)

    return {
        "mapping_name": mapping_name,
        "mapping": mapping,
        "source_roots": source_roots,
        "target_roots": target_roots,
        "rules": rules,
    }


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
    gc = GlobalConfig()
    config = gc.load()
    
    click.echo(f"\n📁  Config directory : {CONFIG_DIR}")
    click.echo(f"    profiles.json    : {CONFIG_FILE}")
    click.echo(f"    suites.json      : {SUITES_FILE}")
    click.echo(f"    mapping-presets  : {DEFAULT_MAPPING_FILE}")
    click.echo(f"    reports/         : {REPORTS_DIR}")
    click.echo(f"    config.json      : {CONFIG_DIR / 'config.json'}\n")
    
    # Show global config settings
    click.echo("⚙️  Global Settings:")
    backup_config = config.get("backup", {})
    click.echo(f"    backup.enabled     : {backup_config.get('enabled', True)}")
    click.echo(f"    backup.max_backups : {backup_config.get('max_backups', 10)}\n")


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


@config.command("set")
@click.argument("key")
@click.argument("value")
def config_set(key, value):
    """Set a global config value by key (e.g., 'backup.enabled true')."""
    gc = GlobalConfig()
    
    # Parse value as boolean, int, or string
    if value.lower() in ("true", "yes", "1", "on"):
        parsed_value = True
    elif value.lower() in ("false", "no", "0", "off"):
        parsed_value = False
    elif value.isdigit():
        parsed_value = int(value)
    else:
        parsed_value = value
    
    try:
        gc.set(key, parsed_value)
        click.echo(f"✅  Config updated: {key} = {parsed_value}")
    except Exception as err:
        click.echo(f"❌  {err}")


@config.command("get")
@click.argument("key", required=False)
def config_get(key):
    """Get a global config value by key, or show all if no key provided."""
    gc = GlobalConfig()
    
    if key is None:
        # Show all config
        config = gc.load()
        click.echo("\n⚙️  Global Config:")
        click.echo(json.dumps(config, indent=2))
        click.echo()
    else:
        value = gc.get(key)
        if value is None:
            click.echo(f"❌  Key not found: {key}")
        else:
            click.echo(f"{key} = {value}")



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
@click.option("--tags", default=None, help="Comma-separated tags for this profile (e.g., fabric,priority-high).")
def profile_add(name, source, target, parser, description, mapping, target_changelog, tags):
    """Save a new sync profile with source, target, and optional settings.

    Args:
        name: Unique profile identifier.
        source: Path to source folder.
        target: Path to target folder.
        parser: One or more content parsers to apply before hashing.
        description: Optional description for this profile.
        mapping: Optional mapping preset name for category-based sync.
        target_changelog: If set, append changelog entries to target CHANGELOG.md.
        tags: Comma-separated tags for organizing profiles (optional).

    Tags help organize and filter profiles. Tags are case-insensitive and normalized to lowercase.
    See 'mcru profile list --filter-tag' to filter by tags.
    """
    cm = ConfigManager()
    cm.add_profile(name, source, target, list(parser), description, mapping, target_changelog)
    
    # Add tags if provided
    if tags:
        tag_list = [tag.strip() for tag in tags.split(",")]
        for tag in tag_list:
            cm.update_profile_field(name, "add-tag", tag)
    
    click.echo(f"✅  Profile '{name}' saved.")
    click.echo(f"    Source : {source}")
    click.echo(f"    Target : {target}")
    if parser:
        click.echo(f"    Parsers: {', '.join(parser)}")
    if mapping:
        click.echo(f"    Mapping: {mapping}")
    if target_changelog:
        click.echo(f"    Target changelog: enabled")
    if tags:
        click.echo(f"    Tags   : {', '.join(tag_list)}")


@profile.command("list")
@click.option("--filter-tag", multiple=True, help="Filter profiles by tag (can be specified multiple times). Use comma for multiple tags in one group, add ',+and' for AND logic.")
def profile_list(filter_tag):
    """List all saved sync profiles, optionally filtered by tags.

    Args:
        filter_tag: Filter by tag (repeatable). Examples:
            - '--filter-tag fabric' → profiles with tag "fabric"
            - '--filter-tag fabric --filter-tag forge' → profiles with "fabric" OR "forge"
            - '--filter-tag fabric,priority-high,+and' → profiles with BOTH "fabric" AND "priority-high"

    By default, multiple --filter-tag options use OR logic (union of tag groups).
    Within a comma-separated group, default is OR. Add ',+and' to a group to use AND logic.
    """
    cm = ConfigManager()
    
    # Apply filtering if --filter-tag is specified
    if filter_tag:
        profiles_data = cm.list_profiles_by_tags(list(filter_tag))
    else:
        profiles_data = cm.list_profiles()
    
    if not profiles_data:
        click.echo("No profiles saved yet. Use 'mcru profile add' to create one.")
        return
    
    # Convert to formatter format
    profiles = [
        {
            "name": p["name"],
            "source": p["source"],
            "target": p["target"],
            "mapping": p.get("mapping_preset"),
            "parsers": p.get("parsers"),
            "tags": p.get("tags", []),
        }
        for p in profiles_data
    ]
    
    formatter = ProfileListFormatter()
    output = formatter.format_profiles(profiles)
    click.echo()
    click.echo(output)
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
    tags = p.get("tags") or []
    if tags:
        tags_str = ", ".join(tags)
        click.echo(f"  Tags    : {tags_str}")
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


@profile.command("set")
@click.argument("name")
@click.option("--description", "-d", default=None, help="Update profile description.")
@click.option("--mapping", default=None, help="Update mapping preset name.")
@click.option("--target-changelog", type=click.Choice(["on", "off"]), default=None,
              help="Enable or disable target changelog.")
@click.option("--parser", "-p", multiple=True,
              type=click.Choice(["strip_bom", "normalize_line_endings", "lowercase_names"]),
              help="Set parser list (replaces existing parsers).")
@click.option("--source", default=None, help="Update source folder path.")
@click.option("--target", default=None, help="Update target folder path.")
@click.option("--add-tags", default=None, multiple=True, help="Comma-separated tags to add to the profile.")
@click.option("--remove-tags", default=None, multiple=True, help="Comma-separated tags to remove from the profile.")
def profile_set(name, description, mapping, target_changelog, parser, source, target, add_tags, remove_tags):
    """Update individual fields of an existing profile without re-specifying the entire configuration.

    Args:
        name: Profile name to update.
        description: Optional new description.
        mapping: Optional new mapping preset name.
        target_changelog: Enable ('on') or disable ('off') target changelog.
        parser: One or more parsers (replaces existing parser list).
        source: Optional new source folder path.
        target: Optional new target folder path.
        add_tags: Comma-separated tags to add (repeatable option).
        remove_tags: Comma-separated tags to remove (repeatable option).

    Tags are case-insensitive; duplication is prevented automatically.
    Only specified fields are updated; unchanged fields are preserved.
    """
    cm = ConfigManager()
    
    # Check if profile exists
    if cm.get_profile(name) is None:
        click.echo(f"❌  Profile '{name}' not found.")
        return
    
    changes = []
    
    # Update each field if provided
    if description is not None:
        cm.update_profile_field(name, "description", description)
        changes.append(f"description → {description}")
    
    if mapping is not None:
        cm.update_profile_field(name, "mapping_preset", mapping)
        changes.append(f"mapping → {mapping}")
    
    if target_changelog is not None:
        is_enabled = target_changelog == "on"
        cm.update_profile_field(name, "target_changelog", is_enabled)
        status = "enabled" if is_enabled else "disabled"
        changes.append(f"target-changelog → {status}")
    
    if parser:
        cm.update_profile_field(name, "parsers", list(parser))
        parser_str = ", ".join(parser) if parser else "(none)"
        changes.append(f"parsers → {parser_str}")
    
    if source is not None:
        cm.update_profile_field(name, "source", source)
        changes.append(f"source → {source}")
    
    if target is not None:
        cm.update_profile_field(name, "target", target)
        changes.append(f"target → {target}")
    
    # Handle add-tags
    if add_tags:
        added_tags = []
        for tags_str in add_tags:
            tag_list = [tag.strip() for tag in tags_str.split(",")]
            for tag in tag_list:
                cm.update_profile_field(name, "add-tag", tag)
                added_tags.append(tag)
        if added_tags:
            changes.append(f"tags added → {', '.join(added_tags)}")
    
    # Handle remove-tags
    if remove_tags:
        removed_tags = []
        for tags_str in remove_tags:
            tag_list = [tag.strip() for tag in tags_str.split(",")]
            for tag in tag_list:
                cm.update_profile_field(name, "remove-tag", tag)
                removed_tags.append(tag)
        if removed_tags:
            changes.append(f"tags removed → {', '.join(removed_tags)}")
    
    if not changes:
        click.echo(f"❌  No changes specified. Use --description, --mapping, --parser, --target-changelog, --source, --target, --add-tags, or --remove-tags.")
        return
    
    click.echo(f"✏️  Profile '{name}' updated:")
    for change in changes:
        click.echo(f"    • {change}")


@profile.command("verify")
@click.argument("name")
def profile_verify(name):
    """Verify that a profile's source and target folders exist."""
    cm = ConfigManager()
    p = cm.get_profile(name)
    if p is None:
        click.echo(f"❌  Profile '{name}' not found.")
        return
    
    source_path = Path(p['source'])
    target_path = Path(p['target'])
    source_exists = source_path.exists()
    target_exists = target_path.exists()
    
    click.echo(f"\nProfile: {p['name']}")
    click.echo("─" * 40)
    source_icon = "✅" if source_exists else "❌"
    target_icon = "✅" if target_exists else "❌"
    click.echo(f"{source_icon}  Source: {p['source']}")
    click.echo(f"{target_icon}  Target: {p['target']}")
    
    if source_exists and target_exists:
        click.echo(f"\n✅  Profile '{name}' is valid.")
    else:
        click.echo(f"\n⚠️  Profile '{name}' has missing folders.")
        if not source_exists:
            click.echo(f"    Source folder does not exist: {p['source']}")
        if not target_exists:
            click.echo(f"    Target folder does not exist: {p['target']}")
    click.echo()


@profile.command("snapshot")
@click.argument("name")
def profile_snapshot(name):
    """Show a source/target folder snapshot for a profile.

    Includes full folder/file trees and summary counts. If the profile uses
    a mapping preset, only mapped source/target roots are scanned.
    """
    cm = ConfigManager()
    p = cm.get_profile(name)
    if p is None:
        click.echo(f"❌  Profile '{name}' not found.")
        return

    source_base = Path(p["source"])
    target_base = Path(p["target"])

    if not source_base.exists():
        click.echo(f"❌  Source folder does not exist: {p['source']}")
        return

    try:
        scope = _resolve_snapshot_scope(p, cm)
    except (FileNotFoundError, ValueError) as err:
        click.echo(f"❌  {err}")
        return

    source_roots = scope["source_roots"]
    target_roots = scope["target_roots"]

    source_folders, source_files = _collect_snapshot_paths(source_base, source_roots)
    target_folders, target_files = _collect_snapshot_paths(target_base, target_roots)

    source_tree = _build_snapshot_tree(source_folders, source_files)
    target_tree = _build_snapshot_tree(target_folders, target_files)

    click.echo(f"\nProfile: {p['name']}")
    click.echo("-" * 72)
    click.echo(f"Source : {source_base}")
    click.echo(f"Target : {target_base}")
    if scope["mapping_name"]:
        click.echo(f"Mapping: {scope['mapping_name']} (snapshot scoped to mapped roots)")

    click.echo("\n1) Source snapshot")
    click.echo("-" * 72)
    if scope["mapping_name"]:
        click.echo("Mapped source roots:")
        if source_roots:
            for root in source_roots:
                click.echo(f"  - {root}")
        else:
            click.echo("  (none resolved from mapping source_roots)")
        click.echo()

    source_lines = _render_snapshot_tree(source_tree)
    if source_lines:
        for line in source_lines:
            click.echo(line)
    else:
        click.echo("(no files found)")

    click.echo(f"\nSource summary: {len(source_files)} files, {len(source_folders)} folders")

    click.echo("\n2) Target snapshot")
    click.echo("-" * 72)
    if not target_base.exists():
        click.echo(f"(target folder missing: {target_base})")
    else:
        if scope["mapping_name"]:
            click.echo("Mapped target roots:")
            for root in target_roots:
                click.echo(f"  - {root}")
            click.echo()

        target_lines = _render_snapshot_tree(target_tree)
        if target_lines:
            for line in target_lines:
                click.echo(line)
        else:
            click.echo("(no files found)")

    click.echo(f"\nTarget summary: {len(target_files)} files, {len(target_folders)} folders")

    click.echo("\n3) Comprehensive summary")
    click.echo("-" * 72)
    click.echo(f"Source totals : {len(source_files)} files, {len(source_folders)} folders")
    click.echo(f"Target totals : {len(target_files)} files, {len(target_folders)} folders")
    click.echo(f"File delta    : {len(source_files) - len(target_files):+d}")
    click.echo(f"Folder delta  : {len(source_folders) - len(target_folders):+d}")
    click.echo()


@profile.command("sort")
@click.option(
    "--sort-by",
    type=click.Choice(["name", "created_at"], case_sensitive=False),
    default="name",
    show_default=True,
    help="Field to sort by.",
)
@click.option(
    "--order",
    type=click.Choice(["asc", "desc"], case_sensitive=False),
    default="asc",
    show_default=True,
    help="Sort direction: ascending or descending.",
)
@click.option(
    "--dry-run",
    is_flag=True,
    help="Preview the sorted order without modifying profiles.json.",
)
def profile_sort(sort_by, order, dry_run):
    """Sort saved profiles by name or creation date.

    Use --dry-run to preview the result without writing changes.

    \b
    Examples:
      mcru profile sort --sort-by name --order asc
      mcru profile sort --sort-by created_at --order desc --dry-run
    """
    cm = ConfigManager()

    if not cm.list_profiles():
        click.echo("No profiles saved yet. Use 'mcru profile add' to create one.")
        return

    result = cm.sort_profiles(sort_by=sort_by, order=order, dry_run=dry_run)
    sorted_profiles = result["profiles"]
    label = "name" if sort_by == "name" else "date created"
    direction = "ascending" if order == "asc" else "descending"

    if dry_run:
        click.echo()
        click.echo(f"  [Dry run] Would sort {len(sorted_profiles)} profile(s) by {label} ({direction}):")
        click.echo()
        profiles = [
            {
                "name": p["name"],
                "source": p["source"],
                "target": p["target"],
                "mapping": p.get("mapping_preset"),
                "parsers": p.get("parsers"),
            }
            for p in sorted_profiles
        ]
        formatter = ProfileListFormatter()
        click.echo(formatter.format_profiles(profiles))
        click.echo()
        click.echo("  Run without --dry-run to apply.")
        click.echo()
    else:
        click.echo(f"✔  Sorted {len(sorted_profiles)} profile(s) by {label} ({direction}).")


# ──────────────────────────────────────────────
# Run a Sync Job
# ──────────────────────────────────────────────

@cli.command()
@click.argument("profile")
@click.option("--dry-run", is_flag=True, help="Preview changes without applying them.")
@click.option("--no-report", is_flag=True, help="Skip saving the report file.")
@click.option("--backup", "backup_override", flag_value=True, default=None, help="Force backup on this run even if globally disabled.")
@click.option("--no-backup", "backup_override", flag_value=False, help="Skip backup on this run even if globally enabled.")
@click.option("--source", default=None, help="Override the source folder for this run (applies to every profile in a suite).")
@click.option("--target", default=None, help="Override the target folder for this run (applies to every profile in a suite).")
@click.option("--mapping", default=None, help="Mapping preset name. Overrides profile/suite mapping if set.")
@click.option("--target-changelog", is_flag=True, default=False,
              help="Prepend a Markdown entry to CHANGELOG.md in the target folder on every live run (overrides profile setting).")
def run(profile, dry_run, no_report, backup_override, source, target, mapping, target_changelog):
    """Run a sync job using a saved profile or suite.\n
    If the name matches a suite, all profiles in the suite are run in order
    and a single combined report is produced.\n
    Example: mcru run myproject --dry-run
    """
    cm = ConfigManager()
    gc = GlobalConfig()
    bm = BackupManager()
    
    # Determine if backups should be created
    backup_enabled = gc.get("backup.enabled", True)
    if backup_override is not None:
        backup_enabled = backup_override
    backup_enabled = backup_enabled and not dry_run  # Never backup in dry-run mode
    max_backups = gc.get("backup.max_backups", 10)
    
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

            # Validate source and target folders exist
            source_path = Path(pcfg["source"])
            target_path = Path(pcfg["target"])
            if not source_path.exists():
                click.echo(f"  ❌  {pname}: Source folder does not exist: {pcfg['source']} — skipping.")
                continue
            if not target_path.exists():
                click.echo(f"  ❌  {pname}: Target folder does not exist: {pcfg['target']} — skipping.")
                continue

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

            # Create backup if enabled
            backup_id = None
            if backup_enabled:
                try:
                    backup_id = bm.create_backup(pcfg["target"], pname)
                except OSError as err:
                    click.echo(f"  ⚠️  {pname}: Backup failed: {err}")
                    if not click.confirm("  Continue without backup?", default=True):
                        click.echo(f"  ❌  Aborted.")
                        continue

            mcru = MCRU(pcfg, dry_run=dry_run)
            try:
                results = mcru.run()
            except ValueError as err:
                click.echo(f"  ❌  {pname}: {err} — skipping.")
                if backup_id:
                    bm.finalize_backup(backup_id, "failed")
                continue

            run_outcome = _result_outcome(results)
            if backup_id:
                bm.finalize_backup(backup_id, "success" if run_outcome == "success" else "failed")
                if run_outcome == "success":
                    bm.rotate_backups(max_backups)

            runs.append((pname, pcfg, results))

            if (target_changelog or pcfg.get("target_changelog")) and not dry_run:
                writer = TargetChangelogWriter(pcfg["target"], pname)
                writer.write(results, pcfg)

        if not runs:
            click.echo("\n❌  No profiles ran successfully.")
            return

        outcome = _suite_outcome(runs)
        suite_reporter = SuiteReporter(profile, runs, dry_run=dry_run, outcome=outcome)
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
        if outcome != "success":
            raise click.exceptions.Exit(1)
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

    # Validate source and target folders exist
    source_path = Path(config["source"])
    target_path = Path(config["target"])
    if not source_path.exists():
        click.echo(f"❌  Source folder does not exist: {config['source']}")
        return
    if not target_path.exists():
        click.echo(f"❌  Target folder does not exist: {config['target']}")
        return

    # Create backup if enabled
    backup_id = None
    if backup_enabled:
        try:
            backup_id = bm.create_backup(config["target"], profile)
        except OSError as err:
            click.echo(f"❌  Backup failed: {err}")
            if not click.confirm("Continue without backup?", default=True):
                click.echo("Aborted.")
                return

    mcru = MCRU(config, dry_run=dry_run)
    try:
        results = mcru.run()
    except ValueError as err:
        click.echo(f"❌  {err}")
        if backup_id:
            bm.finalize_backup(backup_id, "failed")
        return

    outcome = _result_outcome(results)
    if backup_id:
        bm.finalize_backup(backup_id, "success" if outcome == "success" else "failed")
        if outcome == "success":
            bm.rotate_backups(max_backups)

    reporter = Reporter(profile, config, results, dry_run=dry_run, outcome=outcome)
    reporter.print_summary()

    if not no_report:
        report_path = reporter.save_report()
        click.echo(f"\n📄  Report saved to: {report_path}")

    if (target_changelog or config.get("target_changelog")) and not dry_run:
        writer = TargetChangelogWriter(config["target"], profile)
        if writer.write(results, config):
            changelog_path = Path(config["target"]) / TargetChangelogWriter.CHANGELOG_FILENAME
            click.echo(f"\n📋  Changelog updated: {changelog_path}")
    if outcome != "success":
        raise click.exceptions.Exit(1)


# ──────────────────────────────────────────────
# Suite Management
# ──────────────────────────────────────────────

@cli.group()
def suite():
    """Create and manage suites."""
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

    mcru = MCRU(config, dry_run=dry_run)
    try:
        results = mcru.run()
    except ValueError as err:
        click.echo(f"❌  {err}")
        return
    outcome = _result_outcome(results)
    reporter = Reporter("quick-run", config, results, dry_run=dry_run, outcome=outcome)
    reporter.print_summary()
    if outcome != "success":
        raise click.exceptions.Exit(1)


# ──────────────────────────────────────────────
# Backups
# ──────────────────────────────────────────────

@cli.group()
def backup():
    """List, view, restore, pin, and prune backups."""
    pass


@backup.command("list")
@click.option("--profile", "-p", default=None, help="Filter by profile name.")
def backup_list(profile):
    """List all backups (most recent first)."""
    bm = BackupManager()
    entries = bm.list_backups(profile=profile)
    
    if not entries:
        if profile:
            click.echo(f"No backups found for profile '{profile}'.")
        else:
            click.echo("No backups found.")
        return
    
    # Header
    header = f"\n{'ID':<35} {'PROFILE':<15} {'CREATED':<19} {'RESULT':<8} {'PINNED':<7} NOTE"
    click.echo(header)
    click.echo("─" * 100)
    
    # Rows
    for entry in entries:
        backup_id = entry.id[:32] + "..." if len(entry.id) > 32 else entry.id
        created = entry.created_at[:19] if entry.created_at else "unknown"
        pinned_str = "yes" if entry.pinned else "no"
        result_str = entry.run_result if entry.run_result else "pending"
        note = entry.note if entry.note else ""
        
        click.echo(f"{backup_id:<35} {entry.profile:<15} {created:<19} {result_str:<8} {pinned_str:<7} {note}")
    
    click.echo()


@backup.command("view")
@click.argument("backup_id")
def backup_view(backup_id):
    """Show files inside a backup zip."""
    bm = BackupManager()
    
    try:
        entry = bm.get_backup(backup_id)
        contents = bm.view_backup_contents(backup_id)
    except ValueError as err:
        click.echo(f"❌  {err}")
        return
    
    # Calculate total size
    total_size = sum(size for _, size in contents)
    
    click.echo(f"\n📦  Contents of {entry.filename}:")
    click.echo("─" * 80)
    
    for filepath, size in contents:
        size_kb = size / 1024
        if size_kb < 1024:
            size_str = f"{size_kb:.1f} KB"
        else:
            size_mb = size_kb / 1024
            size_str = f"{size_mb:.1f} MB"
        click.echo(f"  {filepath:<60} ({size_str:>8})")
    
    click.echo("─" * 80)
    total_mb = total_size / (1024 * 1024)
    if total_mb < 1024:
        total_str = f"{total_mb:.1f} MB"
    else:
        total_gb = total_mb / 1024
        total_str = f"{total_gb:.2f} GB"
    click.echo(f"  Total: {len(contents)} files, {total_str}\n")


@backup.command("restore")
@click.argument("backup_id")
@click.option("--target", default=None, help="Override restore path (default: original target from backup).")
@click.option("--yes", "-y", is_flag=True, help="Skip confirmation prompt.")
def backup_restore(backup_id, target, yes):
    """Restore a backup to the target path."""
    bm = BackupManager()
    
    try:
        entry = bm.get_backup(backup_id)
    except ValueError as err:
        click.echo(f"❌  {err}")
        return
    
    restore_path = target if target else entry.target
    
    # Confirmation
    click.echo(f"\n⚠️  Restore details:")
    click.echo(f"    Backup ID    : {entry.id}")
    click.echo(f"    Created      : {entry.created_at}")
    click.echo(f"    Restore to   : {restore_path}")
    click.echo(f"    Target files : {len(bm.view_backup_contents(backup_id))}")
    
    if not yes:
        if not click.confirm("\n🤔  This will overwrite files at the target path. Continue?"):
            click.echo("Cancelled.")
            return
    
    try:
        bm.restore_backup(backup_id, target_path=restore_path if target else None)
        click.echo(f"\n✅  Backup restored successfully.")
    except (ValueError, OSError) as err:
        click.echo(f"\n❌  Restore failed: {err}")


@backup.command("delete")
@click.argument("backup_id")
@click.option("--force", "-f", is_flag=True, help="Delete even if pinned.")
def backup_delete(backup_id, force):
    """Delete a backup."""
    bm = BackupManager()
    
    try:
        entry = bm.get_backup(backup_id)
    except ValueError as err:
        click.echo(f"❌  {err}")
        return
    
    if entry.pinned and not force:
        click.echo(f"❌  Backup '{backup_id}' is pinned. Use 'mcru backup unpin {backup_id}' first or pass --force.")
        return
    
    if not click.confirm(f"Are you sure you want to delete {backup_id}?", default=False):
        click.echo("Cancelled.")
        return
    
    try:
        bm.delete_backup(backup_id, force=force)
        click.echo(f"✅  Backup deleted.")
    except ValueError as err:
        click.echo(f"❌  {err}")


@backup.command("pin")
@click.argument("backup_id")
@click.option("--note", "-n", default="", help="Optional note/label for the backup.")
def backup_pin(backup_id, note):
    """Pin a backup to prevent automatic deletion."""
    bm = BackupManager()
    
    try:
        bm.pin_backup(backup_id, note=note)
        click.echo(f"✅  Backup pinned: {backup_id}")
        if note:
            click.echo(f"    Note: {note}")
    except ValueError as err:
        click.echo(f"❌  {err}")


@backup.command("unpin")
@click.argument("backup_id")
def backup_unpin(backup_id):
    """Unpin a backup to allow automatic deletion."""
    bm = BackupManager()
    
    try:
        bm.unpin_backup(backup_id)
        click.echo(f"✅  Backup unpinned: {backup_id}")
    except ValueError as err:
        click.echo(f"❌  {err}")


@backup.command("note")
@click.argument("backup_id")
@click.argument("text")
def backup_note(backup_id, text):
    """Set or update the note on a backup."""
    bm = BackupManager()
    
    try:
        bm.set_note(backup_id, text)
        click.echo(f"✅  Note updated: {backup_id}")
        click.echo(f"    Note: {text}")
    except ValueError as err:
        click.echo(f"❌  {err}")


@backup.command("prune")
@click.option("--keep", type=int, default=None, help="Number of backups to keep (delete all others).")
@click.option("--pinned", is_flag=True, help="Also prune pinned backups.")
@click.option("--dry-run", is_flag=True, help="Show what would be deleted without deleting.")
def backup_prune(keep, pinned, dry_run):
    """Delete old backups; --pinned includes pinned ones."""
    bm = BackupManager()
    
    if keep is None:
        click.echo("❌  --keep is required (number of backups to keep).")
        return
    
    if dry_run:
        entries = bm.list_backups()
        candidates = entries if pinned else [e for e in entries if not e.pinned]
        candidates.sort(key=lambda e: e.created_at, reverse=True)
        to_delete = candidates[keep:]
        
        if not to_delete:
            click.echo(f"✅  No backups would be deleted (keeping {keep} backups).")
            return
        
        click.echo(f"\nWould delete {len(to_delete)} backup(s):")
        for entry in to_delete:
            click.echo(f"  - {entry.id}")
        click.echo()
    else:
        deleted = bm.prune_backups(keep=keep, include_pinned=pinned)
        click.echo(f"✅  Pruned {deleted} backup(s).")


if __name__ == "__main__":
    cli()
