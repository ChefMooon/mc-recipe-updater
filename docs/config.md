# Config

The `mcru config` command group lets you inspect, open, and reset the
configuration files that `mcru` stores in `~/.mcru/`.

---

## Config directory layout

```
~/.mcru/
├── profiles.json          — saved profiles
├── suites.json            — saved suites
├── mapping-presets.json   — built-in and custom mapping presets
└── reports/               — timestamped run report files
```

All files are plain JSON and can be edited manually, though using the CLI
commands is recommended to avoid formatting errors.

---

## Quick reference

| Command | Description |
|---------|-------------|
| `mcru config show` | Print paths of all config files and directories |
| `mcru config open` | Open the config directory in the file explorer |
| `mcru config reset-presets` | Restore bundled mapping presets without touching profiles or reports |
| `mcru config reset` | Delete and recreate the entire config directory |

---

## Commands

### Show

```bash
mcru config show
```

Prints the absolute path of `~/.mcru/` and the path of each config file inside it.

```
📁  Config directory : C:\Users\you\.mcru
    profiles.json
    suites.json
    mapping-presets.json
    reports/
```

Useful for quickly finding where files live, or for copying paths to open them
in an editor.

---

### Open

```bash
mcru config open
```

Opens the `~/.mcru/` directory in the system file explorer (Explorer on Windows,
Finder on macOS, `xdg-open` on Linux).

---

### Reset presets

```bash
mcru config reset-presets
```

Deletes `~/.mcru/mapping-presets.json` and re-seeds it from the bundled package
defaults.

Use this when:
- You have made manual edits to `mapping-presets.json` that broke a preset.
- You want to restore the original built-in presets after deleting them.
- A package update ships new default presets and you want a clean slate.

**Profiles, suites, and reports are not affected.**

---

### Reset

```bash
mcru config reset
```

Prompts for confirmation, then **deletes the entire `~/.mcru/` directory** and
recreates it from scratch with only the default mapping presets.

> **Warning:** This is irreversible. All profiles, suites, custom presets, and
> reports are permanently deleted.

Use this when:
- You want to start completely fresh.
- Your config files are in an unrecoverable state.

```bash
mcru config reset
# Prompts: "This will permanently delete all profiles, suites, presets, and
#           reports. Type YES to confirm:"
```

Pass `-y` / `--yes` to skip the confirmation prompt in scripts.

---

## Tips

- **Prefer `reset-presets` over `reset`** when only your mapping presets are
  broken — it leaves profiles, suites, and reports untouched.
- **Back up before `reset`** — copy `~/.mcru/profiles.json` and
  `~/.mcru/suites.json` somewhere safe if you want to restore them afterwards.
- **Manual edits** — if you edit `profiles.json` or `suites.json` directly,
  run `mcru profile list` or `mcru suite list` afterwards to verify the files
  parsed correctly.
- **Locate files quickly** — use `mcru config show` to get the exact paths,
  then open them in your editor of choice.
