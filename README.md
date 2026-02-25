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

mcru add website ./src /var/www/html --parser normalize_line_endings
mcru add configs ~/dotfiles ~/.config --parser strip_bom
```

### `run` — Run a sync job
```bash
mcru run <name> [options]

# Options:
#   --dry-run     Preview changes only, no files touched
#   --no-report   Skip saving the report file
#   --source      Override source for this run only
#   --target      Override target for this run only

mcru run myproject
mcru run myproject --dry-run
mcru run myproject --target /other/path
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
```

### `quick` — One-off run, no profile needed
```bash
mcru quick ./src ./dist --dry-run
```

---

## Parsers

Parsers transform file **content before hashing**, so minor differences  
(like line endings or BOM markers) don't count as real changes.

| Parser                   | What it does                              |
|--------------------------|-------------------------------------------|
| `strip_bom`              | Removes UTF-8 BOM from file start         |
| `normalize_line_endings` | Converts CRLF / CR → LF                   |
| `strip_trailing_whitespace` | Strips trailing spaces from each line  |

Use multiple:
```bash
foldersyncer add myproject ./src ./dist \
  --parser strip_bom \
  --parser normalize_line_endings
```

To add a custom parser, open `parsers/registry.py` and add your function.

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

| Path | Contents |
|------|----------|
| `~/.foldersyncer/profiles.json` | All saved profiles |
| `~/.foldersyncer/reports/` | Timestamped report files |

---

## Package as a standalone binary (optional)

```bash
pip install pyinstaller
pyinstaller --onefile cli.py --name foldersyncer
# Output: dist/foldersyncer  ← single binary, no Python needed
```
