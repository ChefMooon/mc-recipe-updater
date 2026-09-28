"""
Backups Documentation — System Design

This module documents the mcru backup system design, storage, configuration,
and usage patterns.
"""

# Backups

Persistent ZIP backups are optional and enabled by default. When enabled, mcru takes a full snapshot of the **entire target folder** before each sync run (including `mcru quick`). Backups are stored in `~/.mcru/backups/` and are rotated after successful runs — by default, the last 10 non-pinned backups are kept. Control backups globally with `backup.enabled` or override the setting for a run with `--backup` or `--no-backup`.

Backups allow you to:
- Restore files from a previous snapshot
- Pin important backups to prevent auto-deletion
- Label backups with notes for easy identification
- View what files were in each backup without extracting

## Automatic Sync Rollback

Automatic transaction rollback is separate from persistent ZIP backups and works even when persistent backups are disabled. During a live sync, if a filesystem mutation fails and the failure is caught, mcru stops applying changes and attempts to reverse mutations already made in that run.

- If rollback completes, the target is restored to its pre-run state and the run is reported as `failed`.
- If rollback is incomplete, the run is reported as `partial`; transaction recovery data is retained and its location is surfaced in the failure details.
- If the run had an associated persistent backup, that backup is marked `failed`. The failed run does not trigger successful-run rotation; the backup remains subject to rotation during a later successful run.
- Cancellation behavior is unchanged: completed changes are not rolled back.

Transaction rollback covers caught live sync mutation failures only. It does not cover process termination, power loss, or concurrent external edits to the target.

## Overview

### What Gets Backed Up

- **Full target snapshot**: Every file and subdirectory in the target folder is captured as-is.
- **Timing**: Backups are created *before* the sync runs, so they represent the state just before changes.
- **Naming**: Backups are named by profile name and timestamp, e.g. `backup_recipes_20250307_143022.zip`.

### When Backups Are Created

- **Before every `mcru run`**: A backup is created for the target folder of the profile being synced.
- **Before every `mcru quick`**: A backup is created for the temporary target being synced.
- **Never on dry-run**: `--dry-run` skips backup creation.
- **Override per-run**: Use `--backup` or `--no-backup` flags to enable/disable backups for a single run.

### Automatic Rotation

After a successful sync run, backups are automatically pruned:
1. **Count non-pinned backups** in the registry.
2. **If count exceeds the limit** (default 10), delete the oldest non-pinned backups until within limit.
3. **Pinned backups are preserved** and don't count toward the limit.

When a run fails, its associated backup is marked `failed` and is not rotated as part of that failed run. It counts toward the rotation limit and may be pruned by a later successful run's normal rotation.

## Storage

### Paths

```
~/.mcru/backups/                    — Directory containing all .zip backup files
~/.mcru/backups.json                — Backup metadata registry (single source of truth)
```

### Zip File Naming

```
backup_<profile-or-"quick">_<YYYYMMDD_HHMMSS>.zip
```

**Examples:**
- `backup_recipes_20250307_143022.zip` — backup of "recipes" profile on 2025-03-07 at 14:30:22
- `backup_quick_20250307_150901.zip` — quick sync backup on 2025-03-07 at 15:09:01

### `backups.json` Schema

```json
[
  {
    "id": "backup_recipes_20250307_143022",
    "filename": "backup_recipes_20250307_143022.zip",
    "profile": "recipes",
    "target": "/path/to/target/folder",
    "created_at": "2025-03-07T14:30:22",
    "run_result": "success",
    "pinned": false,
    "note": ""
  }
]
```

**Field Descriptions:**
- `id`: Unique backup identifier (also the zip filename stem). Used in CLI commands.
- `filename`: Full filename of the zip file.
- `profile`: Name of the profile this backup is for (or `"quick"` for ad-hoc syncs).
- `target`: Absolute path to the target folder at backup time.
- `created_at`: ISO 8601 timestamp of when the backup was created.
- `run_result`: Status of the sync run — `"pending"` (before run), `"success"`, or `"failed"`.
- `pinned`: Boolean; if true, the backup is protected from automatic deletion.
- `note`: Optional user-provided label for the backup (max ~100 chars).

## Configuration

### Global Config File

`~/.mcru/config.json` stores global mcru settings, including backup preferences:

```json
{
  "backup": {
    "enabled": true,
    "max_backups": 10
  }
}
```

**Fields:**
- `backup.enabled` (boolean, default: `true`): Enable/disable backups globally.
  - If `false`, no backups are created by default.
  - Can be overridden per-run with `--backup` or `--no-backup` flags.
- `backup.max_backups` (integer, default: `10`, minimum: `1`): Number of non-pinned backups to keep.
  - Pinned backups are excluded from the limit.
  - Rotation runs after each successful sync.

### Setting Config Values

Use `mcru config set` to change settings:

```bash
# Enable/disable backups globally
mcru config set backup.enabled true
mcru config set backup.enabled false

# Change max backup count
mcru config set backup.max_backups 20
```

### Viewing Current Config

```bash
mcru config show        # Show config file paths and current backup settings
mcru config get backup  # Show the entire backup config block
```

## Rotation Logic

### How It Works

1. After a successful sync run completes, `rotate_backups(max_backups)` is called automatically.
2. Count all non-pinned backups in backups.json.
3. If count > `max_backups`, sort non-pinned backups by `created_at` (oldest first).
4. Delete the oldest non-pinned backups until count ≤ `max_backups`.
5. Update backups.json.

### Examples

**Scenario 1: No Pinned Backups**
- Config: `max_backups = 10`
- Current backups: 12 (all unpinned)
- Action: Delete the 2 oldest backups → 10 remain

**Scenario 2: With Pinned Backups**
- Config: `max_backups = 10`
- Current backups: 12 (2 pinned, 10 unpinned)
- Action: No unpinned backups are deleted because the unpinned count is already at the limit → 10 unpinned + 2 pinned = 12 remain.
- If there are 15 backups (3 pinned, 12 unpinned), rotation deletes the 2 oldest unpinned backups → 10 unpinned + 3 pinned = 13 remain.

### Failed Runs

If a sync run **fails**, its associated backup is marked with `"run_result": "failed"` and is kept by that run. Failed runs do not trigger rotation; the backup still counts toward `max_backups` and may be pruned by a later successful run's rotation like any other unpinned backup.

## Pinning

### What Is Pinning?

Pinned backups are protected from automatic deletion during rotation and pruning operations. Use pinning to preserve important snapshots, such as:
- Before a major update
- Known good state
- Before schema migration

### Pin/Unpin/Note Commands

```bash
# Pin a backup
mcru backup pin backup_recipes_20250307_143022

# Pin with a label
mcru backup pin backup_recipes_20250307_143022 --note "before v2 migration"

# Update the note on an already-pinned backup
mcru backup note backup_recipes_20250307_143022 "updated note text"

# Unpin a backup
mcru backup unpin backup_recipes_20250307_143022
```

### Force Delete a Pinned Backup

To delete a pinned backup, either `unpin` it first or use `--force`:

```bash
# Option 1: Unpin then delete
mcru backup unpin <id>
mcru backup delete <id>

# Option 2: Force delete
mcru backup delete <id> --force
```

## CLI Reference

All backup commands are accessed via the `mcru backup` command group.

### `mcru backup list [--profile <name>]`

List all backups, most recent first.

**Options:**
- `--profile <name>`, `-p <name>`: Filter to a single profile.

**Example Output:**
```
ID                                PROFILE    CREATED              RESULT  PINNED NOTE
backup_recipes_20250307_143022    recipes    2025-03-07 14:30:22  success no
backup_quick_20250307_150901      quick      2025-03-07 15:09:01  failed  yes    before v2 migration
```

### `mcru backup view <id>`

Show all files stored in a backup zip without extracting it.

**Usage:**
```bash
mcru backup view backup_recipes_20250307_143022
```

**Example Output:**
```
📦  Contents of backup_recipes_20250307_143022.zip:
──────────────────────────────────────────────────────────────────────────────
  recipes/config.json                                          (2.1 KB)
  recipes/data/items.json                                      (14.8 KB)
  recipes/data/crafting/recipe_1.json                          (1.2 KB)
  ...
──────────────────────────────────────────────────────────────────────────────
  Total: 47 files, 1.2 MB
```

### `mcru backup restore <id> [--target <path>] [--yes]`

Restore a backup to the target path.

**Options:**
- `--target <path>`: Override the target restore path (default: original target from backup metadata).
- `--yes`, `-y`: Skip confirmation prompt.

**Usage:**
```bash
# Restore to original location
mcru backup restore backup_recipes_20250307_143022

# Restore to a different location
mcru backup restore backup_recipes_20250307_143022 --target /path/to/new/location

# Restore without confirmation
mcru backup restore backup_recipes_20250307_143022 --yes
```

**Behavior:**
1. Prints backup details and target path.
2. Prompts for confirmation (unless `--yes` passed).
3. Extracts the zip to the target path, overwriting files with matching paths. Files in the target that are absent from the archive are left in place; manual restore is an overlay, not an exact rollback.
4. Prints success message with file count.

### `mcru backup delete <id> [--force]`

Delete a backup.

**Options:**
- `--force`, `-f`: Delete even if the backup is pinned.

**Usage:**
```bash
mcru backup delete backup_recipes_20250307_143022
mcru backup delete backup_recipes_20250307_143022 --force
```

**Behavior:**
1. If backup is pinned and `--force` is not set, prints an error and refuses deletion.
2. Prompts for confirmation.
3. Deletes the zip file and removes metadata from backups.json.

### `mcru backup pin <id> [--note "text"]`

Pin a backup to prevent auto-deletion.

**Options:**
- `--note "text"`, `-n "text"`: Set or update a label for the backup.

**Usage:**
```bash
mcru backup pin backup_recipes_20250307_143022
mcru backup pin backup_recipes_20250307_143022 --note "before schema v2"
```

### `mcru backup unpin <id>`

Unpin a backup to allow auto-deletion.

**Usage:**
```bash
mcru backup unpin backup_recipes_20250307_143022
```

### `mcru backup note <id> <text>`

Set or update the note on a backup.

**Usage:**
```bash
mcru backup note backup_recipes_20250307_143022 "important backup before migration"
```

### `mcru backup prune [--keep <n>] [--pinned] [--dry-run]`

Delete old backups, keeping only the most recent N. Optionally include pinned backups.

**Options:**
- `--keep <n>`: Number of backups to keep (required). All others are deleted.
- `--pinned`: Also prune pinned backups (normally they are preserved).
- `--dry-run`: Show what would be deleted without actually deleting.

**Usage:**
```bash
# Keep only the 5 most recent backups, delete all others (except pinned)
mcru backup prune --keep 5

# Keep 5, including pinned (dangerous!)
mcru backup prune --keep 5 --pinned

# Preview what would be deleted
mcru backup prune --keep 5 --dry-run
```

## Per-Run Flags

Both `mcru run` and `mcru quick` support backup overrides:

### `--backup`

Force backup on this run even if `backup.enabled` is false globally.

```bash
mcru run myprofile --backup
mcru quick ./src ./dst --backup
```

### `--no-backup`

Skip backup on this run even if `backup.enabled` is true globally.

```bash
mcru run myprofile --no-backup
mcru quick ./src ./dst --no-backup
```

**Note:** `--dry-run` always skips backups regardless of these flags.

## Restore Workflow

### Step-by-Step Example

You want to restore a backup from March 7 at 14:30:

```bash
# 1. List backups and find the one you want
mcru backup list --profile recipes
# Output shows: backup_recipes_20250307_143022

# 2. Optionally view what's in it
mcru backup view backup_recipes_20250307_143022

# 3. Restore it (will prompt for confirmation)
mcru backup restore backup_recipes_20250307_143022

# 4. Or restore to a temporary location to inspect first
mcru backup restore backup_recipes_20250307_143022 --target /tmp/backup_inspect

# 5. If satisfied, you can move/copy the restored files
```

## Edge Cases & Error Handling

### Target Does Not Exist at Backup Time

**Behavior:** Backup creation is skipped silently, a warning is logged, and the sync run continues.

**Why:** The sync only needs the target folder to exist after being created during config, not at backup time if the user is testing with a temporary target path.

### Not Enough Disk Space to Create Backup

**Behavior:** An `OSError` is raised. mcru prints an error message and asks if you want to continue without a backup (with a `--yes` flag to suppress the prompt).

**Example:**
```
❌  Backup failed: No space left on device
Continue without backup? [Y/n]:
```

### Corrupted Zip on Restore

**Behavior:** If the zip file is corrupted, restore will catch `zipfile.BadZipFile` and print a clear error:

```
❌  Restore failed: Corrupted backup file: ...
```

The target folder is left untouched.

### `backups.json` Missing or Malformed

**Behavior:** When loading the registry, if backups.json is missing or contains invalid JSON, BackupManager logs a warning and reinitializes it with an empty list:

```
⚠️  backups.json is malformed: ..., reinitializing
```

### Backup ID Not Found

**Behavior:** Commands that reference a backup ID (e.g., `mcru backup restore <id>`) will print:

```
❌  Backup not found: <id>
```

With a suggestion to run `mcru backup list` to see available backups.

### Pinned Backup Delete Without `--force`

**Behavior:** Attempting to delete a pinned backup without `--force` prints:

```
❌  Backup '<id>' is pinned. Use 'mcru backup unpin <id>' first or pass --force.
```

## Best Practices

1. **Pin before major changes**: If you're about to perform a significant update, pin the current backup with a descriptive note.
   ```bash
   mcru backup pin $(mcru backup list | head -1 | awk '{print $1}') --note "before major mod update"
   ```

2. **Use `--dry-run` first**: If you're nervous about a sync, run with `--dry-run` to preview changes without triggering a backup or actual sync.
   ```bash
   mcru run myprofile --dry-run
   ```

3. **Periodically review and prune**: Use `mcru backup list` and `mcru backup prune --dry-run` to keep disk usage under control.

4. **Check disk space**: Before running large syncs, ensure you have enough space for both the target and the backup zip.

5. **Use notes liberally**: Add descriptive notes to help future-you understand why a backup is important.
   ```bash
   mcru backup note <id> "stable version, all recipes tested"
   ```

## Troubleshooting

### I accidentally synced to the wrong target. Can I restore?

Yes! Find the backup before the incorrect sync:

```bash
mcru backup list
# Find the backup ID you want to restore
mcru backup restore <id>
```

### Backups are consuming too much disk space. How do I clean up?

Lower the `max_backups` setting or manually prune:

```bash
# Keep only 5 most recent backups
mcru backup prune --keep 5

# Disable backups entirely (not recommended)
mcru config set backup.enabled false
```

### How do I disable backups completely?

```bash
mcru config set backup.enabled false
```

Or skip backups for a single run:

```bash
mcru run myprofile --no-backup
```

### Can I backup a backup? (backup inception)

No, backups are only created of target folders being synced, not of other backups.
