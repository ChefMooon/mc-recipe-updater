# Command Reference

Full flag and option reference for every `mcru` command.

---

## Commands

- **[Run](#mcru-run--run-a-profile-or-suite)** — Execute a saved profile or suite with optional overrides
- **[Quick](#mcru-quick--one-off-run-without-saving-a-profile)** — One-off sync without saving a profile
- **[Profile](#profile-commands)** — Save and manage folder sync profiles with source/target paths and options
- **[Suite](#suite-commands)** — Create and manage ordered groups of profiles to run in sequence
- **[Config](#config-commands)** — View, manage, and reset configuration files and presets
- **[Reports](#reports-commands)** — List, view, search, and prune saved run reports

## Feature Guides

- **[Target Changelog](target-changelog.md)** — Automatically maintain a `CHANGELOG.md` inside the target folder

## Common Flags

| Flag | Description | Applies To |
|------|-------------|-----------|
| `-p, --parser <name>` | Content parser (repeatable) | `profile add` \| `profile update` \| `quick` |
| `-d, --desc <text>` | Description text | `profile add` \| `profile update` \| `suite add` \| `suite update` |
| `--mapping <preset>` | Mapping preset name | `profile add` \| `profile update` \| `run` \| `quick` |
| `--dry-run` | Preview changes only | `run` \| `quick` |
| `--source <path>` | Override source folder | `run` |
| `--target <path>` | Override target folder | `run` |
| `--no-report` | Skip saving report file | `run` |
| `--target-changelog` | Prepend entry to `CHANGELOG.md` in target folder | `profile add` \| `profile update` \| `run` |

---

## `mcru run` — Run a profile or suite

```bash
mcru run <name> [options]
```

Accepts a **profile name** or a **suite name** — profile lookup happens first, suite lookup second.

| Flag | Description |
|------|-------------|
| `--dry-run` | Preview changes only, no files written |
| `--no-report` | Skip saving the `.txt` report file |
| `--source <path>` | Override source folder for this run only |
| `--target <path>` | Override target folder for this run only |
| `--mapping <preset>` | Override mapping preset for this run only |
| `--target-changelog` | Prepend a Markdown entry to `CHANGELOG.md` in the target folder (live runs only) |

`--source`, `--target`, and `--mapping` apply to every profile when running a suite. Saved profile definitions are never modified.

`--target-changelog` can also be set permanently per-profile with `profile add --target-changelog`; the CLI flag overrides the profile setting.

See [target-changelog.md](target-changelog.md) for a full guide including entry format, suite behaviour, and tips.

```bash
mcru run myproject
mcru run myproject --dry-run
mcru run myproject --target /other/path
mcru run full-sync --mapping mc-arch
mcru run myproject --target-changelog
```

---

## `mcru quick` — One-off run without saving a profile

```bash
mcru quick <source> <target> [options]
```

| Flag | Description |
|------|-------------|
| `--dry-run` | Preview only |
| `-p, --parser <name>` | Parser (repeatable) |
| `--mapping <preset>` | Mapping preset name |

```bash
mcru quick ./src ./dist --dry-run
mcru quick ./my-mod ./target-pack --mapping mc-arch
```

Quick runs do not save a report file.

---

## Profile Commands

See [profiles.md](profiles.md) for a full guide including profile schema, report format, and tips.

### Quick Reference

| Command | Description |
|---------|-------------|
| `mcru profile add <name> <source> <target>` | Save a new profile |
| `mcru profile list` | List all saved profiles |
| `mcru profile show <name>` | Inspect a single profile |
| `mcru profile verify <name>` | Validate that source and target folders exist |
| `mcru profile remove <name>` | Delete a profile |
| `mcru profile update <name> <source> <target>` | Overwrite a saved profile |

### `mcru profile add` — Save a new profile

```bash
mcru profile add <name> <source> <target> [options]
```

| Flag | Description |
|------|-------------|
| `-p, --parser <name>` | Apply a content parser before hashing (repeatable) |
| `-d, --desc <text>` | Optional description |
| `--mapping <preset>` | Mapping preset name |
| `--target-changelog` | Enable changelog writing for every live run of this profile |

```bash
mcru profile add myproject ./src ./dist
mcru profile add recipes ./my-mod ./target-pack --mapping mc-arch
mcru profile add configs ~/dotfiles ~/.config --parser strip_bom --parser normalize_line_endings
mcru profile add recipes ./my-mod ./target-pack --target-changelog
```

---

### `mcru profile list` — Show all saved profiles

```bash
mcru profile list
```

Prints a table with name, source, target, parsers, and mapping preset for every saved profile.

---

### `mcru profile show` — Inspect a single profile

```bash
mcru profile show <name>
```

Prints all details for the named profile: source, target, parsers, mapping preset, and creation timestamp.

---

### `mcru profile verify` — Validate profile paths

```bash
mcru profile verify <name>
```

Verifies that the source and target folders configured in the profile actually exist. Useful before running a profile to catch path issues early.

```bash
mcru profile verify myproject
```

Output example:
```
Profile: myproject
────────────────────────────────────
✅  Source: /home/user/src
✅  Target: /home/user/dist

✅  Profile 'myproject' is valid.
```

---

### `mcru profile remove` — Delete a profile

```bash
mcru profile remove <name>
```

---

### `mcru profile update` — Edit a saved profile

```bash
mcru profile update <name> <source> <target> [options]
```

Overwrites the saved profile (same options as `add`). The `created_at` timestamp is preserved.

| Flag | Description |
|------|-------------|
| `-p, --parser <name>` | Parser (repeatable) |
| `-d, --desc <text>` | Description |
| `--mapping <preset>` | Mapping preset name |
| `--target-changelog` | Enable changelog writing for every live run of this profile |

---

## Suite Commands

See [suites.md](suites.md) for a full guide including schemas, report format, and error handling.

### Quick Reference

| Command | Description |
|---------|-------------|
| `mcru suite add <name>` | Create an empty suite |
| `mcru suite remove <name>` | Delete a suite |
| `mcru suite update <name>` | Update a suite's description |
| `mcru suite list` | List all suites |
| `mcru suite show <name>` | Inspect a suite and its profile order |
| `mcru suite add-profile <suite> <profile>` | Append a profile to a suite |
| `mcru suite remove-profile <suite> <profile>` | Remove a profile from a suite |
| `mcru suite reorder <suite> <profile> <position>` | Change a profile's execution order |

### `mcru suite add` — Create a suite

```bash
mcru suite add <name> [-d description]
```

Creates an empty suite. Add profiles to it with `suite add-profile`.

### `mcru suite remove` — Delete a suite

```bash
mcru suite remove <name>
```

Deletes the suite. The profiles inside it are **not** affected.

### `mcru suite update` — Update a suite's description

```bash
mcru suite update <name> -d "New description"
```

### `mcru suite list` — Show all suites

```bash
mcru suite list
```

Prints a table of all suites with their profile count and description.

### `mcru suite show` — Inspect a suite

```bash
mcru suite show <name>
```

Prints the ordered profile list with 1-based positions. Profiles that no longer exist are flagged.

### `mcru suite add-profile` — Append a profile

```bash
mcru suite add-profile <suite> <profile>
```

Appends the profile to the end of the suite's list. The profile must already exist.

### `mcru suite remove-profile` — Remove a profile from a suite

```bash
mcru suite remove-profile <suite> <profile>
```

Removes the profile from the suite's list. The profile itself is not deleted.

### `mcru suite reorder` — Change execution order

```bash
mcru suite reorder <suite> <profile> <position>
```

Moves the named profile to the given 1-based position. All other profiles shift accordingly.

```bash
# Before: mod-a, mod-b, mod-c
mcru suite reorder all-mods mod-c 1
# After:  mod-c, mod-a, mod-b
```

---

## Config Commands

See [config.md](config.md) for a full guide including config directory layout and reset strategy details.

### Quick Reference

| Command | Description |
|---------|-------------|
| `mcru config show` | Print paths of all config files and directories |
| `mcru config open` | Open the config directory in the file explorer |
| `mcru config reset-presets` | Restore bundled mapping presets without touching profiles or reports |
| `mcru config reset` | Delete and recreate the entire config directory |

### `mcru config show`

Prints the absolute paths of all config files:

```
~/.mcru/
    profiles.json
    suites.json
    mapping-presets.json
    reports/
```

### `mcru config open`

Opens the `~/.mcru/` directory in the system file explorer (Windows Explorer, Finder, or `xdg-open`).

### `mcru config reset-presets`

Deletes `~/.mcru/mapping-presets.json` and re-seeds it from the bundled package defaults.  
Use this to restore presets after manual edits go wrong, without touching profiles or reports.

### `mcru config reset`

Prompts for confirmation, then deletes the entire `~/.mcru/` directory and recreates it from scratch.  
**All profiles, suites, custom presets, and reports are permanently deleted.**

---

## Reports Commands

See [reports.md](reports.md) for a full guide including report file format and prune strategy details.

### Quick Reference

| Command | Description |
|---------|-------------|
| `mcru reports show` | Show reports directory path and count |
| `mcru reports list` | List all reports (with filtering and sort options) |
| `mcru reports open` | Open the reports folder in the file explorer |
| `mcru reports view <name>` | Print a report's contents to the terminal |
| `mcru reports delete <name>` | Delete one or more reports by filename |
| `mcru reports search <query>` | Find reports by profile or suite name |
| `mcru reports prune` | Delete old reports in bulk by count, age, or all |

### `mcru reports show`

```bash
mcru reports show
```

Prints the absolute path of the reports directory and current report count.

### `mcru reports list` — List saved reports

```bash
mcru reports list [options]
```

| Flag | Description |
|------|-------------|
| `-l, --limit N` | Show only the N most recent reports (default: all) |
| `--sort <date\|name\|size>` | Sort order (default: `date`, newest first) |

```bash
mcru reports list
mcru reports list --limit 10
mcru reports list --sort size
```

### `mcru reports open`

```bash
mcru reports open
```

Opens `~/.mcru/reports/` in the system file explorer.

### `mcru reports view` — Display a report

```bash
mcru reports view <name>
```

Prints the full contents of the named report to the terminal. `NAME` is the filename with or without the `.txt` extension.

```bash
mcru reports view myproject_20260228_120000
mcru reports view myproject_20260228_120000.txt
```

### `mcru reports delete` — Delete reports by name

```bash
mcru reports delete <name> [<name> ...] [options]
```

| Flag | Description |
|------|--------------|
| `-y, --yes` | Skip confirmation prompt |

```bash
mcru reports delete myproject_20260228_120000
mcru reports delete report1 report2 report3 --yes
```

### `mcru reports search` — Find reports by profile or suite name

```bash
mcru reports search <query>
```

Case-insensitive substring search against the profile or suite name embedded in the report filename.

```bash
mcru reports search myproject
mcru reports search suite
```

### `mcru reports prune` — Delete old reports in bulk

```bash
mcru reports prune [options]
```

At least one strategy flag is required. Strategies are **additive** (union): combining `--keep` and `--older-than` deletes reports matching either condition.

| Flag | Description |
|------|-------------|
| `--keep N` | Keep only the N most recent reports; delete the rest |
| `--older-than DAYS` | Delete reports older than DAYS days |
| `--all` | Delete all reports |
| `--dry-run` | Preview what would be deleted without deleting |
| `-y, --yes` | Skip confirmation prompt |

Always previews the deletion list before asking for confirmation. `--dry-run` stops before the confirmation prompt.

```bash
mcru reports prune --keep 10
mcru reports prune --older-than 30
mcru reports prune --keep 5 --older-than 90
mcru reports prune --all
mcru reports prune --keep 10 --dry-run
```
