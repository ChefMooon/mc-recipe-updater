# mc-recipe-updater (`mcru`)

A terminal tool to compare and sync folders using saved profiles.  
Source is always treated as the **correct version**. Target is brought in line with it.

Available in two modes:
- **CLI** (`mcru`) — command-line interface for scripting and automation
- **TUI** (`mcru-tui`, `mcrui`) — interactive terminal interface

> **Docs:** [Architecture & full reference](docs/architecture.md) · [TUI Reference](docs/tui.md) · [Command Reference](docs/commands.md) · [Folder Mapping](docs/folder-mapping.md) · [Suites](docs/suites.md) · [Reports](docs/reports.md)

---

## Install

```bash
cd mc-recipe-updater
pip install -e .
```

After this, both `mcru` and `mcru-tui`/`mcrui` are available as terminal commands from anywhere.

---

## Getting Started

### CLI Mode (Command Line)

```bash
mcru --help          # View all CLI commands
```

### TUI Mode (Interactive)

```bash
mcru-tui
```

See the [TUI reference](docs/tui.md) for available workflows and navigation.

> Full flag and option reference: [docs/commands.md](docs/commands.md)

Try a saved profile or a one-off preview:

```bash
mcru run myproject --dry-run
mcru quick ./src ./dist --dry-run
```

---

## Commands

> Full flag and option reference: [docs/commands.md](docs/commands.md)

| Command | Description |
|---------|-------------|
| `mcru run <name>` | Run a profile or suite (`--dry-run` to preview) |
| `mcru quick <src> <tgt>` | One-off sync without saving a profile |
| `mcru profile ...` | Create and manage sync profiles |
| `mcru suite ...` | Create and manage suites |
| `mcru backup ...` | List, view, restore, pin, and prune backups |
| `mcru config ...` | View, open, or reset mcru configuration and user data |
| `mcru reports ...` | List, view, search, and prune saved run reports |

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

## Backups

Before each sync run (including `mcru quick`), mcru snapshots the entire target folder as a `.zip` file in `~/.mcru/backups/` when backups are enabled. After a successful run, automatic rotation keeps up to 10 **unpinned** backups by default; pinned backups are excluded from this limit.

- **Pin a backup** to prevent auto-deletion: `mcru backup pin <id>`
- **Restore a backup**: `mcru backup restore <id>`
- **List all backups**: `mcru backup list`
- **Disable backups globally**: `mcru config set backup.enabled false`
- **Override per-run**:
  - `mcru run myprofile --no-backup` — skip backup on this run
  - `mcru run myprofile --backup` — force backup even if globally disabled

Backups are never created in `--dry-run` mode. See [docs/backups.md](docs/backups.md) for full reference, including rotation logic, restore workflow, and troubleshooting.

---

## Where Data is Stored

All user data lives under `~/.mcru/`, created automatically on first run.

| Path | Contents |
|------|----------|
| `~/.mcru/profiles.json` | All saved profiles |
| `~/.mcru/suites.json` | All saved suites |
| `~/.mcru/config.json` | Global settings (backup preferences, etc.) |
| `~/.mcru/mapping-presets.json` | Mapping presets (seeded from package, freely editable) |
| `~/.mcru/backups/` | Timestamped `.zip` snapshot files |
| `~/.mcru/backups.json` | Backup metadata registry |
| `~/.mcru/reports/` | Timestamped `.txt` report files |

> `mapping-presets.json` is copied from the package defaults only once — upgrades never overwrite your local copy.
>
> To reset only mapping presets to package defaults: `mcru config reset-presets`.
>
> To reset all mcru user data, including profiles, suites, reports, backups, and custom presets: `mcru config reset`. This is destructive; copy anything you want to keep first.

For module details and data flow, see the [architecture reference](docs/architecture.md).

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
