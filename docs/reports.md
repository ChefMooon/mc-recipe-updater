# Reports

Every `mcru run` (profile or suite) saves a timestamped `.txt` report to
`~/.mcru/reports/`. The `mcru reports` command group lets you browse, inspect,
search, and clean up those files without leaving the terminal.

---

## Where reports live

```
~/.mcru/reports/
├── myproject_20260228_120000.txt
├── all-mods_20260228_143022.txt
└── ...
```

**Filename pattern:** `<profile-or-suite-name>_YYYYMMDD_HHMMSS.txt`

Reports are written by `Reporter` (single profile) and `SuiteReporter` (suite).
They are never modified after creation — each run always produces a new file.

---

## Quick reference

| Command | Description |
|---------|-------------|
| `mcru reports show` | Show reports directory path and count |
| `mcru reports list` | List all reports (with filtering and sort options) |
| `mcru reports open` | Open the reports folder in the file explorer |
| `mcru reports view <name>` | Print a report's contents to the terminal |
| `mcru reports delete <name>` | Delete one or more reports by filename |
| `mcru reports search <query>` | Find reports by profile or suite name |
| `mcru reports prune` | Delete old reports in bulk by count, age, or all |

---

## Commands

### Show

```bash
mcru reports show
```

Prints the absolute path of `~/.mcru/reports/` and the number of `.txt` files
currently saved there.

```
📁  Reports directory : C:\Users\you\.mcru\reports
    8 report(s) saved
```

---

### List

```bash
mcru reports list [--limit N] [--sort date|name|size]
```

Prints a table of all saved reports:

```
FILENAME                                          SIZE      DATE                 PROFILE / SUITE
────────────────────────────────────────────────────────────────────────────────────────────────────
all-mods_20260228_143022.txt                    18.5 KB   2026-02-28 14:30:22  all-mods
myproject_20260228_120000.txt                    2.7 KB   2026-02-28 12:00:00  myproject
myproject_20260227_093011.txt                    2.6 KB   2026-02-27 09:30:11  myproject
```

**Options:**

| Flag | Default | Description |
|------|---------|-------------|
| `-l, --limit N` | all | Show only the N most recent reports |
| `--sort date` | ✓ | Newest first |
| `--sort name` | | Alphabetical by profile/suite name |
| `--sort size` | | Largest first |

```bash
mcru reports list --limit 5
mcru reports list --sort name
mcru reports list --limit 20 --sort size
```

---

### Open

```bash
mcru reports open
```

Opens `~/.mcru/reports/` in the system file explorer (Explorer on Windows,
Finder on macOS, `xdg-open` on Linux).

---

### View

```bash
mcru reports view <name>
```

Prints the full text of a report to the terminal. `NAME` is the filename with
or without the `.txt` extension.

```bash
mcru reports view myproject_20260228_120000
mcru reports view myproject_20260228_120000.txt
```

Useful for quickly reading a past run without opening the folder.

---

### Delete

```bash
mcru reports delete <name> [<name> ...] [-y]
```

Deletes one or more report files. Always shows the list of files to be deleted
and asks for confirmation unless `--yes` is passed.

```bash
# Delete a single report
mcru reports delete myproject_20260227_093011

# Delete several at once
mcru reports delete report1 report2 report3

# Skip confirmation
mcru reports delete myproject_20260227_093011 --yes
```

---

### Search

```bash
mcru reports search <query>
```

Finds reports whose embedded profile or suite name contains `query`
(case-insensitive substring match).

```bash
mcru reports search myproject
mcru reports search suite
mcru reports search mod-a
```

Example output:

```
Found 3 report(s) matching 'myproject':

  myproject_20260228_120000.txt  (2.7 KB, 2026-02-28 12:00:00)
  myproject_20260227_210533.txt  (2.7 KB, 2026-02-27 21:05:33)
  myproject_20260227_093011.txt  (2.6 KB, 2026-02-27 09:30:11)
```

---

### Prune

```bash
mcru reports prune [--keep N] [--older-than DAYS] [--all] [--dry-run] [-y]
```

Deletes reports in bulk. At least one strategy flag is required.

**Strategies:**

| Flag | Behaviour |
|------|-----------|
| `--keep N` | Keep the N most recent reports; delete everything older |
| `--older-than DAYS` | Delete any report whose timestamp is older than DAYS days |
| `--all` | Delete every report in the directory |

Strategies are **additive** (union): combining `--keep` and `--older-than` deletes
reports that match *either* condition.

**Safety flags:**

| Flag | Behaviour |
|------|-----------|
| `--dry-run` | Show what would be deleted without deleting anything |
| `-y, --yes` | Skip the confirmation prompt |

Prune always prints the list of files to be deleted and the space that would be
freed before doing anything. `--dry-run` stops after the preview.

```bash
# Keep last 10 reports
mcru reports prune --keep 10

# Delete reports older than 30 days
mcru reports prune --older-than 30

# Keep last 5 AND remove anything older than 90 days
mcru reports prune --keep 5 --older-than 90

# Wipe everything
mcru reports prune --all

# Preview before committing
mcru reports prune --keep 10 --dry-run

# Non-interactive (CI / scripts)
mcru reports prune --older-than 60 --yes
```

Example dry-run output:

```
Would delete 3 report(s), freeing ~17.0 KB:
  test-1_20260226_104244.txt
  test-suite_20260226_114237.txt
  test-suite_20260226_114329.txt

(Dry run — no files were deleted.)
```

---

## Tips

- **Routine cleanup** — run `mcru reports prune --older-than 30` periodically to
  keep the reports folder from growing indefinitely.
- **Quick audit** — `mcru reports list --limit 5` gives an at-a-glance view of
  your most recent runs.
- **Compare runs** — use `mcru reports search <profile>` to find all historical
  runs for a specific profile, then `mcru reports view <name>` to read each one.
- **Non-interactive scripts** — pass `--yes` to `delete` and `prune` to suppress
  confirmation prompts in automated environments.
