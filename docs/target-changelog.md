# Target Changelog

The target changelog feature appends a Markdown entry to a `CHANGELOG.md` file
inside the **target folder** every time a live sync run makes real changes.

It is separate from the [reports](reports.md) system — reports are stored centrally
in `~/.mcru/reports/` and are never modified; the target changelog lives alongside
the synced files and grows with each run.

---

## Overview

- **Disabled by default** — opt in per-profile or per-run
- **Only writes on live runs** — `--dry-run` never touches the changelog
- **Only writes when changes occur** — if no files are added, updated, or removed the changelog is not touched
- **Prepends each new entry** — newest entry is always at the top of the file
- **One file per target folder** — always named `CHANGELOG.md`, created if it doesn't exist
- **Always preserved** — `CHANGELOG.md` is never deleted from target, even when the flag is not active

---

## Enabling the changelog

### Per-run (CLI flag)

Pass `--target-changelog` to `mcru run` for a one-off run:

```bash
mcru run myproject --target-changelog
```

This overrides the profile's saved setting for that run only.

### Per-profile (permanent)

Set `--target-changelog` when creating or updating a profile so every live run
automatically writes the changelog without needing the flag:

```bash
# When creating a new profile
mcru profile add recipes ./my-mod ./target-pack --target-changelog

# When updating an existing profile
mcru profile update myproject ./src ./dist --target-changelog
```

The flag is stored as `"target_changelog": true` in `~/.mcru/profiles.json`.

> **Note:** `profile update` rewrites the full profile. If you only want to toggle
> changelog on an existing profile, make sure to include all other options
> (parsers, mapping, etc.) to avoid losing them.

---

## Where the file is written

`CHANGELOG.md` is created in the **root of the target folder**:

```
<target>/
├── CHANGELOG.md        ← written here
├── minecraft/
│   ├── crafting/
│   └── smelting/
└── farmersdelight/
    └── cooking/
```

---

## Entry format

Each entry is a Markdown section prepended to the top of `CHANGELOG.md`:

```markdown
## 2026-02-28 14:30:22 — myproject

**Summary:** 3 added, 1 updated, 1 removed  
**Source:** `/path/to/source`  
**Target:** `/path/to/target`  
**Parsers:** none  
**Mapping:** mc-arch  

### Added (3)
- `minecraft/crafting/new_recipe.json`
- `farmersdelight/cooking/stew.json`
- `farmersdelight/cooking/salad.json`

### Updated (1)
- `minecraft/smelting/iron.json`

### Removed (1)
- `minecraft/crafting/old_recipe.json`

---
```

Sections that have no entries (e.g. no removals) are omitted entirely.

Possible sections, in order:

| Section | Contents |
|---------|----------|
| `### Added` | Files copied to target for the first time |
| `### Dirs Added` | New directories created in target |
| `### Updated` | Files that existed but had different content |
| `### Removed` | Files deleted from target |
| `### Dirs Removed` | Directories deleted from target |
| `### Errors` | Files that failed with an error during the run |

---

## Interaction with dry-run

`--dry-run` and `--target-changelog` can be combined on the command line, but
the changelog is **never written** during a dry run:

```bash
# Safe — previews changes, changelog untouched
mcru run myproject --dry-run --target-changelog
```

This lets you safely preview what a run would do without creating a misleading
changelog entry.

---

## Interaction with suites

When running a suite with `--target-changelog`, each profile in the suite writes
its own entry to its own target folder independently. Profiles that produce no
changes do not write an entry.

```bash
mcru run all-mods --target-changelog
```

A summary line is printed at the end listing which profiles had their changelog
updated.

If individual profiles in the suite have `"target_changelog": true` in their
saved config, those profiles will always write the changelog regardless of
whether the flag was passed to `mcru run`.

---

## Profile schema

When `target_changelog` is enabled, the profile JSON gains one field:

```json
{
  "name": "myproject",
  "source": "/path/to/source",
  "target": "/path/to/target",
  "parsers": [],
  "description": "",
  "created_at": "2026-02-28T12:00:00",
  "target_changelog": true
}
```

The field is **omitted** (not set to `false`) when the feature is disabled, so
existing profiles remain unchanged.

---

## Checking a profile's changelog setting

```bash
mcru profile show myproject
```

The `Target changelog` field is always displayed:

```
Profile : myproject
────────────────────────────────────────
  Source  : /path/to/source
  Target  : /path/to/target
  Parsers : —
  Mapping : mc-arch
  Target changelog: enabled
  Created : 2026-02-28T12:00:00
```

---

## Tips

- **Version control** — if your target folder is a Git repository, committing
  `CHANGELOG.md` alongside the synced files gives you a human-readable history
  of every sync run.
- **Ignoring the file** — if you do not want `CHANGELOG.md` to appear in your
  target folder's diff, add it to `.gitignore`.
- **Manual edits** — the file is plain Markdown; you can freely edit, reformat,
  or delete entries. `mcru` always prepends and never reads the existing content.
