# mc-recipe-updater (`mcru`)

A terminal tool to compare and sync folders using saved profiles.  
Source is always treated as the **correct version**. Target is brought in line with it.

Available in two modes:
- **CLI** (`mcru`) — command-line interface for scripting and automation
- **TUI** (`mcru-tui`) — interactive terminal UI with ASCII art and menu-driven navigation

> **Docs:** [Architecture & full reference](docs/architecture.md) · [TUI Reference](docs/tui.md) · [Command Reference](docs/commands.md) · [Folder Mapping](docs/folder-mapping.md) · [Suites](docs/suites.md) · [Reports](docs/reports.md)

---

## Install

```bash
cd mc-recipe-updater
pip install -e .
```

After this, both `mcru` and `mcru-tui` are available as terminal commands from anywhere.

---

## Getting Started

### CLI Mode (Command Line)

```bash
mcru --help          # View all CLI commands
```

### TUI Mode (Interactive)

```bash
mcru-tui             # Launch the interactive terminal UI
```

The TUI provides:
- Animated home screen with command navigation
- Profile, suite, and run management
- Real-time sync progress and results
- ReLI Commands

> Full flag and option reference: [docs/commands.md](docs/commands.md)

| Command | Description |
|---------|-------------|
| `mcru run <name>` | Run a profile or suite (`--dry-run` to preview) |
| `mcru quick <src> <tgt>` | One-off sync without saving a profile |
| `mcru profile ...` | Create and manage sync profiles |
| `mcru suite ...` | Create and manage suites |
| `mcru config ...` | View, open, or reset the config directory |
| `mcru reports ...` | List, view, search, and prune saved run reports |

## Entry Points

| Command | Interface | Use Case |
|---------|-----------|----------|
| `mcru` | CLI | Scripting, automation, headless environments |
| `mcru-tui` | TUI | Interactive use, guided workflows, visual feedback

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
| `mcru run <name>` | Run a profile or suite (`--dry-run` to preview) |
| `mcru quick <src> <tgt>` | One-off sync without saving a profile |
| `mcru profile ...` | Create and manage sync profiles |
| `mcru suite ...` | Create and manage suites |
| `mcru config ...` | View, open, or reset the config directory |
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
> To reset ev   Command layer — all user-facing Click commands
config.py       ConfigManager — reads/writes profiles, suites, presets
syncer.py       MCRU — MD5-based diff + sync engine
reporter.py     Reporter / SuiteReporter — terminal output and .txt reports
registry.py     Parser registry — pluggable content transforms (bytes to bytes)
tui/            TUI layer — interactive terminal interface (Textual)
  app.py          Main TUI application
  screens/        Individual UI screens (profiles, suites, sync, reports, config)
  widgets/        Reusable TUI components
  utils.py        Threading and formatting utilities

```
cli.py       Command layer — all user-facing Click commands
config.py    ConfigManager — reads/writes profiles, suites, presets
syncer.py    MCRU — MD5-based diff + sync engine
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
