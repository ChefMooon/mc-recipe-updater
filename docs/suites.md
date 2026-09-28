# Suites

A **suite** is a named, ordered list of profiles that run together as a single job.
Instead of invoking `mcru run` multiple times, define a suite once and run everything
with a single command. The result is one combined terminal summary and one combined
report file.

---

## When to use suites

- You maintain several related mods and want to sync all of them in one step.
- You have a fixed order in which profiles should run (e.g. common data before
  platform-specific overrides).
- You want a single report that shows the full picture of a multi-profile sync.

---

## Quick start

```bash
# 1. Create profiles as normal
mcru add mod-a ./mod-a-src ./mod-a-target --mapping mc-arch
mcru add mod-b ./mod-b-src ./mod-b-target --mapping mc-arch
mcru add mod-c ./mod-c-src ./mod-c-target

# 2. Create a suite
mcru suite add all-mods -d "Sync all mods in release order"

# 3. Add profiles in the order they should run
mcru suite add-profile all-mods mod-a
mcru suite add-profile all-mods mod-b
mcru suite add-profile all-mods mod-c

# 4. Run the suite the same way you run a profile
mcru run all-mods
mcru run all-mods --dry-run
```

---

## Suite schema

Suites are stored in `~/.mcru/suites.json`:

```json
{
  "suites": [
    {
      "name": "all-mods",
      "description": "Sync all mods in release order",
      "created_at": "2026-02-26T12:00:00",
      "profiles": ["mod-a", "mod-b", "mod-c"]
    }
  ]
}
```

- `name` — unique identifier, used with `mcru run`.
- `description` — optional, shown in `mcru suite list`.
- `created_at` — set automatically.
- `profiles` — **ordered** list of profile names. Profiles run in this order.

---

## Managing suites

### Create
```bash
mcru suite add <name> [-d description]
```
Creates an empty suite. Add profiles to it afterwards.

### Delete
```bash
mcru suite remove <name>
```
Deletes the suite definition. The profiles inside it are **not** affected.

### Update description
```bash
mcru suite update <name> -d "New description"
```
Updates the suite's description without touching its profile list or creation date.

### List all suites
```bash
mcru suite list
```
Prints a table of all suites with their profile count and description.

### Inspect a suite
```bash
mcru suite show <name>
```
Prints the suite's ordered profile list with 1-based position numbers.
Profiles that no longer exist are flagged with a warning.

### Add a profile
```bash
mcru suite add-profile <suite> <profile>
```
Appends the profile to the end of the suite's list. The profile must exist.

### Remove a profile
```bash
mcru suite remove-profile <suite> <profile>
```
Removes the profile from the suite. The profile itself is not deleted.

Deleting a profile with `mcru profile remove` removes its references from every
suite. The order of the remaining profiles is preserved.

### Change execution order
```bash
mcru suite reorder <suite> <profile> <position>
```
Moves the named profile to the given 1-based position. All other profiles
shift accordingly.

```bash
# Before: mod-a, mod-b, mod-c
mcru suite reorder all-mods mod-c 1
# After:  mod-c, mod-a, mod-b
```

---

## Running a suite

`mcru run` auto-detects whether the name refers to a profile or a suite.
Profile lookup happens first; suite lookup happens second.

```bash
mcru run all-mods            # live run
mcru run all-mods --dry-run  # preview — no files touched
mcru run all-mods --no-report  # skip saving the report file
```

### One-off overrides

The `--source`, `--target`, and `--mapping` flags on `mcru run` apply to
**every profile** in the suite for that run only. The saved profile definitions
are not modified.

```bash
# Run the suite but override the mapping for every profile
mcru run all-mods --mapping mc-arch-recipes-split
```

### Error handling

Members that cannot run are **skipped with a reason**. This includes missing
profiles, invalid sync paths, missing target folders, mapping lookup errors,
and a decision to abort after backup creation fails. The remaining profiles
continue. Skipped names and reasons appear in the terminal summary and saved
suite report. A sync that starts but raises an error is reported separately as
a failed profile, not as a skipped member.

The report outcome is `success` when every member runs successfully, `partial`
when at least one member runs but the suite is incomplete or has a partial sync
result, and `failed` when no member runs or the run results indicate failure
without retained changes. A suite with no configured profiles is also failed.

Any `partial` or `failed` suite run exits with status `1`; only `success` exits
with status `0`. This lets scripts distinguish a complete suite run from one
that skipped or failed a member.

---

## Report format

After a suite run, a single combined `.txt` file is saved to `~/.mcru/reports/`
with the filename pattern `<suite-name>_YYYYMMDD_HHMMSS.txt`.

The file is structured as follows:

```
mcru Suite Report
============================================================
Suite    : all-mods
Date     : 2026-02-26T12:00:00
Mode     : LIVE
Outcome  : partial
Profiles : 2
============================================================

------------------------------------------------------------
Profile  : mod-a
Source   : /path/to/mod-a-src
Target   : /path/to/mod-a-target
Parsers  : none
Mapping  : mc-arch
------------------------------------------------------------

Added (2):
  + data/mymod/recipes/foo.json
  + data/mymod/recipes/bar.json

Updated (0):
  (none)

Removed (1):
  - data/mymod/recipes/old.json

Unchanged (14):
  ...

------------------------------------------------------------
Profile  : mod-b
...

============================================================
SUITE TOTALS
============================================================
Added    : 3
Updated  : 1
Removed  : 1
Unchanged: 42
Errors   : 0

============================================================
Skipped profiles (1):
  missing-profile: Profile not found
```

The terminal output mirrors this structure: a banner for the suite, one
colour-coded block per profile, skipped-member details when applicable, and a
`SUITE TOTALS` section at the end.

---

## Tips

- **Shared mapping** — if all profiles in a suite use the same mapping, pass
  `--mapping` at run time rather than saving it in each profile individually.
- **Dry-run first** — `mcru run <suite> --dry-run` is the safest way to preview
  a multi-profile operation before committing.
- **Ordering matters** — if profiles share a target directory, run the most
  authoritative profile last so its version of any file wins.
