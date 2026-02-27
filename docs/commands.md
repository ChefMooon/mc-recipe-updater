# Command Reference

Full flag and option reference for every `mcru` command.

---

## Profile Commands

### `mcru profile add` — Save a new profile

```bash
mcru profile add <name> <source> <target> [options]
```

| Flag | Description |
|------|-------------|
| `-p, --parser <name>` | Apply a content parser before hashing (repeatable) |
| `-d, --desc <text>` | Optional description |
| `--mapping <preset>` | Mapping preset name |

```bash
mcru profile add myproject ./src ./dist
mcru profile add recipes ./my-mod ./target-pack --mapping mc-arch
mcru profile add configs ~/dotfiles ~/.config --parser strip_bom --parser normalize_line_endings
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

`--source`, `--target`, and `--mapping` apply to every profile when running a suite. Saved profile definitions are never modified.

```bash
mcru run myproject
mcru run myproject --dry-run
mcru run myproject --target /other/path
mcru run full-sync --mapping mc-arch
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

## Suite Commands

See [suites.md](suites.md) for a full guide including schemas, report format, and error handling.

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
