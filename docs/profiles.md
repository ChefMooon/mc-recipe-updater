# Profiles

A **profile** is a saved sync configuration that pairs a source folder with a
target folder, an optional mapping preset, and optional content parsers.
Saving a profile means you never have to type paths or flags again — just
`mcru run <name>`.

---

## When to use profiles

- You sync the same source → target pair repeatedly.
- You want a short, memorable name for a long or complex sync command.
- You need to group multiple syncs into a suite for one-command execution.

---

## Quick start

```bash
# 1. Save a profile
mcru profile add myproject ./src ./dist

# 2. Run it any time
mcru run myproject

# 3. Preview without writing files
mcru run myproject --dry-run
```

---

## Profile schema

Profiles are stored in `~/.mcru/profiles.json`:

```json
{
  "profiles": [
    {
      "name": "myproject",
      "description": "Main mod recipe sync",
      "source": "./src",
      "target": "./dist",
      "parsers": [],
      "mapping": "mc-arch",
      "created_at": "2026-02-26T12:00:00"
    }
  ]
}
```

- `name` — unique identifier, used with `mcru run`.
- `description` — optional, shown in `mcru profile list`.
- `source` — path to the source folder.
- `target` — path to the target folder.
- `parsers` — list of content parser names applied before hashing (may be empty).
- `mapping` — mapping preset name, or `null` if none.
- `created_at` — set automatically; preserved across `profile update`.

---

## Managing profiles

### Add a profile
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

### List all profiles
```bash
mcru profile list
```
Prints a table with name, source, target, parsers, mapping preset, and description
for every saved profile.

### Inspect a profile
```bash
mcru profile show <name>
```
Prints all details for the named profile, including the creation timestamp.

### Delete a profile
```bash
mcru profile remove <name>
```
Removes the profile from `profiles.json`. Any suites that reference it will flag
the missing profile when inspected or run.

### Update a profile
```bash
mcru profile update <name> <source> <target> [options]
```
Overwrites the saved profile with new values (same options as `add`).
The `created_at` timestamp is preserved.

```bash
mcru profile update myproject ./new-src ./new-dist --mapping mc-arch
```

---

## Running a profile

```bash
mcru run myproject            # live run
mcru run myproject --dry-run  # preview — no files written
mcru run myproject --no-report  # skip saving the report file
```

### One-off overrides

Pass `--source`, `--target`, or `--mapping` to override saved values for a
single run without modifying the profile:

```bash
mcru run myproject --target /other/path
mcru run myproject --mapping mc-arch-recipes-split
```

---

## Report format

After a profile run, a `.txt` file is saved to `~/.mcru/reports/` with the
filename pattern `<profile-name>_YYYYMMDD_HHMMSS.txt`.

```
mcru Report
============================================================
Profile  : myproject
Date     : 2026-02-28T12:00:00
Mode     : LIVE
Source   : /path/to/src
Target   : /path/to/dist
Parsers  : none
Mapping  : mc-arch
============================================================

Added (2):
  + data/mymod/recipes/foo.json
  + data/mymod/recipes/bar.json

Updated (1):
  ~ data/mymod/recipes/baz.json

Removed (0):
  (none)

Unchanged (14):
  ...
```

Pass `--no-report` to skip saving the file. Quick runs (`mcru quick`) never
save a report file.

See [reports.md](reports.md) for full details on browsing and managing saved reports.

---

## Tips

- **Use `--dry-run` first** — always safe to preview before a live run,
  especially when changing a mapping preset.
- **Group related profiles** — if you sync several mods together, add them to
  a [suite](suites.md) and run everything with one command.
- **Parsers are ordered** — when specifying multiple `--parser` flags, they are
  applied in the order given before hashing.
- **Paths are stored as-is** — relative paths are relative to the working
  directory at run time, not at profile creation time. Use absolute paths for
  portability.
