# mc-recipe-updater

A terminal tool to compare and sync folders using saved profiles.  
Source is always treated as the **correct version**. Target is brought in line with it.

---

## Install

```bash
cd mc-recipe-updater
pip install -e .
```

After this, `mcru` is available as a terminal command from anywhere.

---

## Quick Start

```bash
# Save a profile with a short keyword
mcru add myproject ./src ./dist

# Run it
mcru run myproject

# Preview what would change without touching files
mcru run myproject --dry-run
```

---

## Commands

### `add` — Save a new profile
```bash
mcru add <name> <source> <target> [options]

# Options:
#   -p, --parser  Apply a parser (can be used multiple times)
#   -d, --desc    Description
#   --mapping     Optional mapping preset name

mcru add website ./src /var/www/html --parser normalize_line_endings
mcru add configs ~/dotfiles ~/.config --parser strip_bom
mcru add recipes ./my-mod ./target-pack --mapping mc-arch
```

### `run` — Run a sync job
```bash
mcru run <name> [options]

# Options:
#   --dry-run     Preview changes only, no files touched
#   --no-report   Skip saving the report file
#   --source      Override source for this run only
#   --target      Override target for this run only
#   --mapping     Override mapping preset for this run only

mcru run myproject
mcru run myproject --dry-run
mcru run myproject --target /other/path
mcru run myproject --mapping mc-arch

# Also accepts a suite name — runs all profiles in the suite in order
mcru run full-sync
mcru run full-sync --dry-run
```

### `list` — Show all saved profiles
```bash
mcru list
```

### `remove` — Delete a profile
```bash
mcru remove myproject
```

### `update` — Edit an existing profile
```bash
mcru update myproject ./new-src ./new-dist
mcru update myproject ./new-src ./new-dist --mapping mc-arch
```

### `quick` — One-off run, no profile needed
```bash
mcru quick ./src ./dist --dry-run
mcru quick ./my-mod ./target-pack --mapping mc-arch
```

### `config` — View or open the config directory
```bash
# Print the paths of all config files
mcru config show

# Open the ~/.mcru/ folder in your file explorer
mcru config open

# Reset mapping presets to package defaults
mcru config reset-presets

# Reset ALL configs (profiles, suites, presets, reports) to a clean slate
mcru config reset
```

---

## Suites

A **suite** is an ordered list of profiles that run together as a single job.
All profiles execute in sequence and produce one combined report.

```bash
# Create a suite
mcru suite add full-sync -d "Sync all mods"

# Add profiles to it (in order)
mcru suite add-profile full-sync mod-a
mcru suite add-profile full-sync mod-b
mcru suite add-profile full-sync mod-c

# Run it (same command as a profile)
mcru run full-sync
mcru run full-sync --dry-run
```

### `suite add` — Create a suite
```bash
mcru suite add <name> [-d description]
```

### `suite remove` — Delete a suite
```bash
mcru suite remove <name>
# The profiles inside it are not affected
```

### `suite update` — Update a suite's description
```bash
mcru suite update <name> -d "New description"
```

### `suite list` — Show all suites
```bash
mcru suite list
```

### `suite show` — Show a suite’s ordered profile list
```bash
mcru suite show full-sync
```

### `suite add-profile` — Append a profile to a suite
```bash
mcru suite add-profile <suite> <profile>
```

### `suite remove-profile` — Remove a profile from a suite
```bash
mcru suite remove-profile <suite> <profile>
# The profile itself is not deleted
```

### `suite reorder` — Move a profile to a specific position
```bash
mcru suite reorder <suite> <profile> <position>

# Example: move mod-c to run first
mcru suite reorder full-sync mod-c 1
```

### Suite reports

When a suite finishes, a single combined `.txt` report is saved to `~/.mcru/reports/`.
The file contains one section per profile followed by a **SUITE TOTALS** block summing
added / updated / removed / unchanged / error counts across all profiles.

---

## Mapping mode

- No mapping set (on CLI or profile): normal workflow, all files are matched by relative path.
- Mapping set: source files are categorized and copied into mapped target folders.

### Resolution order

1. `--mapping` on `run`/`quick` (highest priority)
2. profile `mapping_preset` (saved by `add`/`update`)
3. no mapping (default behavior)

### Mapping file

Mappings are read from `~/.mcru/mapping-presets.json`.
This file is automatically seeded from the package defaults on first run.
You can freely edit it to add or modify presets — upgrades will not overwrite your changes.

```json
{
  "version": 1,
  "presets": {
    "mc-arch": {
      "description": "Map multi-platform Minecraft recipe sources into core/fabric/forge target folders.",
      "source_roots": {
        "common": ["common/src/generated/data/*/recipes"],
        "fabric": ["fabric/src/main/resources/data/*/recipes"],
        "forge_like": {
          "candidates": [
            "forge/src/main/resources/data/*/recipes",
            "neoforge/src/main/resources/data/*/recipes"
          ]
        }
      },
      "target_roots": {
        "common": "core",
        "fabric": "fabric",
        "forge_like": "forge"
      },
      "category_map": {
        "common": "common",
        "fabric": "fabric",
        "forge_like": "forge_like"
      },
      "omit_globs": [],
      "rules": {
        "forge_like_conflict": "error_if_multiple",
        "delete_mode": "global_target"
      }
    }
  }
}
```

### Omit source folders/files

Use `omit_globs` to skip matching paths or path segments from source.

```json
"omit_globs": [
  "**/minecraft/**",
  "*_backup",
  "temp"
]
```

---

## Parsers

Parsers transform file **content before hashing**, so minor differences  
(like line endings or BOM markers) don't count as real changes.

| Parser                   | What it does                              |
|--------------------------|-------------------------------------------|
| `strip_bom`              | Removes UTF-8 BOM from file start         |
| `normalize_line_endings` | Converts CRLF / CR → LF                   |
| `lowercase_names`        | Lowercases file content before hashing    |

Use multiple:
```bash
mcru add myproject ./src ./dist \
  --parser strip_bom \
  --parser normalize_line_endings
```

To add a custom parser, open `registry.py` and add your function.
To add a mapping preset, edit `~/.mcru/mapping-presets.json`.

---

## Development Environment

To set up the development environment:

```bash
# Clone the repository (if not already done)
git clone <repo-url>
cd mc-recipe-updater

# Create a virtual environment
python -m venv venv

# Activate it
# On Windows:
venv\Scripts\activate
# On macOS/Linux:
source venv/bin/activate

# Install in editable mode with dev dependencies
pip install -e .

# Deactivate venv
deactivate
```

Now you can run `mcru` from anywhere, and changes to the source code will be reflected immediately.

---

## Where data is stored

All user data lives under `~/.mcru/`, created automatically on first run.

| Path | Contents |
|------|----------|
| `~/.mcru/profiles.json` | All saved profiles |
| `~/.mcru/suites.json` | All saved suites |
| `~/.mcru/mapping-presets.json` | Mapping presets (seeded from package defaults) |
| `~/.mcru/reports/` | Timestamped report files |

> **Note:** `mapping-presets.json` is copied from the package defaults the first time you run `mcru`.
> Upgrades will never overwrite your local copy. To reset presets to defaults, run `mcru config reset-presets`.
> To reset all configs (including all profiles and reports), run `mcru config reset`.

---

## Package as a standalone binary (optional)

```bash
pip install pyinstaller
pyinstaller --onefile cli.py --name mcru
# Output: dist/mcru  ← single binary, no Python needed
```
