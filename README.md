# mc-recipe-updater (`mcru`)

A terminal tool to compare and sync folders using saved profiles.  
Source is always treated as the **correct version**. Target is brought in line with it.

> **Docs:** [Architecture & full reference](docs/architecture.md) · [Command Reference](docs/commands.md) · [Folder Mapping](docs/folder-mapping.md) · [Suites](docs/suites.md)

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
# Save a profile
mcru profile add myproject ./src ./dist

# Run it
mcru run myproject

# Preview changes without touching files
mcru run myproject --dry-run

# One-off run without saving a profile
mcru quick ./src ./dist --dry-run
```

---

## Commands

> Full flag and option reference: [docs/commands.md](docs/commands.md)

| Command | Description |
|---------|-------------|
| `mcru profile add <name> <src> <tgt>` | Save a new sync profile |
| `mcru profile list` | Show all saved profiles |
| `mcru profile show <name>` | Show details for a single profile |
| `mcru profile remove <name>` | Delete a profile |
| `mcru profile update <name> <src> <tgt>` | Edit a saved profile |
| `mcru run <name>` | Run a profile or suite (`--dry-run` to preview) |
| `mcru quick <src> <tgt>` | One-off sync without saving a profile |
| `mcru suite add <name>` | Create a new suite |
| `mcru suite list` | Show all suites |
| `mcru suite show <name>` | Show details for a single suite |
| `mcru suite add-profile <suite> <profile>` | Add a profile to a suite |
| `mcru suite remove-profile <suite> <profile>` | Remove a profile from a suite |
| `mcru suite reorder <suite> <profile> <pos>` | Reorder profiles in a suite |
| `mcru suite update <name>` | Update a suite's description |
| `mcru suite remove <name>` | Delete a suite |
| `mcru config show` | Show config directory paths |
| `mcru config open` | Open the config directory |
| `mcru config reset-presets` | Reset mapping presets to defaults |
| `mcru config reset` | Reset all configuration |

---

## Mapping Mode

When a mapping preset is set, source files are categorised and routed into mapped target folders instead of being mirrored by relative path.

**Resolution order:**
1. `--mapping` on `run` / `quick` (highest priority)
2. `mapping_preset` saved in the profile
3. No mapping — default path-mirroring behaviour

```bash
mcru profile add recipes ./my-mod ./target-pack --mapping mc-arch
mcru run recipes
```

See [docs/folder-mapping.md](docs/folder-mapping.md) for preset schema, `omit_globs`, and how to write custom presets.

---

## Parsers

Parsers transform file content **before hashing** so minor encoding differences don't register as real changes.

| Parser | What it does |
|--------|--------------|
| `strip_bom` | Removes UTF-8 BOM from file start |
| `normalize_line_endings` | Converts CRLF / CR to LF |
| `strip_trailing_whitespace` | Strips trailing whitespace from each line |

```bash
mcru profile add myproject ./src ./dist \
  --parser strip_bom \
  --parser normalize_line_endings
```

To add a custom parser, see the [architecture reference](docs/architecture.md#registrypy--parser-registry).

---

## Where Data is Stored

All user data lives under `~/.mcru/`, created automatically on first run.

| Path | Contents |
|------|----------|
| `~/.mcru/profiles.json` | All saved profiles |
| `~/.mcru/suites.json` | All saved suites |
| `~/.mcru/mapping-presets.json` | Mapping presets (seeded from package, freely editable) |
| `~/.mcru/reports/` | Timestamped `.txt` report files |

> `mapping-presets.json` is copied from the package defaults only once — upgrades never overwrite your local copy.  
> To reset presets: `mcru config reset-presets`  
> To reset everything: `mcru config reset`

---

## Architecture

```
cli.py       Command layer — all user-facing Click commands
config.py    ConfigManager — reads/writes profiles, suites, presets
syncer.py    FolderSyncer — MD5-based diff + sync engine
reporter.py  Reporter / SuiteReporter — terminal output and .txt reports
registry.py  Parser registry — pluggable content transforms (bytes to bytes)
```

See [docs/architecture.md](docs/architecture.md) for the full breakdown including data flow, module internals, schema details, and error handling.

---

## Development Setup

```bash
python -m venv venv

# Windows
venv\Scripts\activate
# macOS / Linux
source venv/bin/activate

pip install -e .
```

Changes to source take effect immediately without reinstalling.

---

## Package as a Standalone Binary (optional)

```bash
pip install pyinstaller
pyinstaller --onefile cli.py --name mcru
# Output: dist/mcru - single binary, no Python needed
```
