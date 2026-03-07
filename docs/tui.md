# mcru TUI — Interactive Terminal User Interface

Complete reference and user guide for the `mcru-tui` interactive mode.

---

## Overview

`mcru-tui` is a terminal user interface powered by [Textual](https://textualize.io/textual/) that provides an interactive, menu-driven alternative to the CLI. It offers the same functionality as `mcru` but with:
- Animated home screen with ASCII art
- Keyboard-navigable command menus
- Real-time sync progress tracking
- Visual result summaries
- Report browsing and search
- Configuration management

All profiles, suites, and reports saved in the TUI are automatically available in the CLI (and vice versa), since they share the same `~/.mcru/` configuration directory.

---

## Getting Started

### Launch the TUI

```bash
mcru-tui
```

The home screen will display:
- Animated ASCII art title
- List of available commands (Profile, Suite, Run, Reports, Config, Quit)
- Command help text

### Navigation

- **Arrow Up/Down** — Move selection in command list
- **Enter** — Select highlighted command
- **Single key** — Quick command access:
  - `p` → Profile
  - `s` → Suite
  - `r` → Run
  - `h` → Reports
  - `b` → Backups
  - `c` → Config
  - `q` → Quit, Escape → Back (context-dependent)

---

## Home Screen

**Purpose:** Entry point for all TUI operations.

**Features:**
- Animated ASCII art splash at top (cycles through frames)
- List of available commands with descriptions
- Arrow key navigation between commands
- Quick single-key access

**Commands:**
| Command | Shortcut | Purpose | Phase |
|---------|----------|---------|-------|
| Profile | `p` | Manage sync profiles | 2 |
| Suite | `s` | Manage profile suites | 3 |
| Run | `r` | Execute sync operations | 4 |
| Reports | `h` | View historical reports | 5 |
| Backups | `b` | Backup management (CLI) | 5+ |
| Config | `c` | Settings and presets | 6 |
| Quit | `q` | Exit TUI | 1 |

**Navigation:**
- Arrow keys to move selection
- Enter to execute
- Single-key shortcuts for quick access

---

## Screens (Implementation Phases)

### Phase 1: Basic Setup (Complete)

✅ Home screen with ASCII art and command navigation  
✅ Placeholder screens for all features  
✅ Entry point registration  
✅ Threading utilities for background operations

### Phase 2: Profile Management (Future)

> Planned features for profile screen

- **List profiles** — Table view with Name, Source, Target, Parsers columns
- **Add profile** — Form to create new profile (name, paths, parsers, mapping preset)
- **Edit profile** — Modify existing profile fields
- **Delete profile** — Remove profile with confirmation
- **Verify profile** — Check that source/target paths exist

**Key bindings:**
- `a` → Add profile
- `e` → Edit selected
- `d` → Delete selected
- `v` → Verify paths

### Phase 3: Suite Management (Future)

> Planned features for suite screen

- **List suites** — Table view with Name, Profile Count, Description
- **Add suite** — Create new suite (name, optional description)
- **Edit suite** — Modify suite description
- **Delete suite** — Remove suite with confirmation
- **Manage profiles** — Add/remove/reorder profiles in suite
- **Show profile order** — Display ordered profile list

**Key bindings:**
- `a` → Add suite
- `e` → Edit selected
- `d` → Delete selected
- `m` → Manage profiles in suite

### Phase 4: Sync Execution (Future)

> Planned features for run/sync screen

**Pre-execution:**
- Profile/Suite selector (dropdown or searchable list)
- Options panel:
  - [ ] Dry-run (preview only, no file changes)
  - Override source path (optional)
  - Override target path (optional)
  - Override mapping preset (optional)
- Start button

**During execution:**
- Animated progress spinner
- Current operation label (e.g., "Scanning source...")
- File count: current/total
- Percentage complete (if calculable)

**On completion:**
- Result summary:
  - ✅ Added files count
  - 🔄 Updated files count
  - ❌ Removed files count
  - ✓ Unchanged files count
  - ⚠ Errors count (if any)
- Option to view full error details (if errors occurred)
- Option to save report (auto-saved by default)
- Back button to select another profile/suite

**Key bindings:**
- `Space` → Start sync
- `Escape` → Cancel (if running), Back (if complete)

### Phase 5: Reports Viewing (Future)

> Planned features for reports screen

- **List recent reports** — Table with Profile/Suite, Timestamp, Added/Updated/Removed counts
- **Search/filter** — By profile name, date range, result type
- **View full report** — Scrollable text view of complete report
- **Delete report** — Remove individual reports or bulk prune old reports

**Key bindings:**
- `/` → Search/filter
- `v` → View selected report
- `d` → Delete selected report
- `p` → Prune old reports

### Phase 5+: Backup Management (Complete - CLI Focus)

Full backup management is implemented via CLI. The TUI provides a placeholder information screen directing users to CLI commands:
- `mcru backup list` — List all backups
- `mcru backup view <id>` — View backup file listing
- `mcru backup restore <id>` — Restore a backup
- `mcru backup pin <id>` — Protect from auto-deletion
- `mcru backup delete <id>` — Remove backup
- `mcru backup prune` — Clean up old backups

See [docs/backups.md](backups.md) for complete CLI reference.

### Phase 6: Configuration (Future)

> Planned features for config screen

- **Show paths:**
  - `~/.mcru/` — Config directory
  - `~/.mcru/profiles.json` — Profiles file
  - `~/.mcru/suites.json` — Suites file
  - `~/.mcru/mapping-presets.json` — Mapping presets
  - `~/.mcru/reports/` — Reports directory

- **Quick actions:**
  - Open config directory (in file explorer)
  - View mapping presets
  - Reset mapping presets to defaults
  - Reset all (`~/.mcru/` wiped and re-initialized)

**Key bindings:**
- `o` → Open directory
- `v` → View presets
- `r` → Reset presets
- `R` → Reset all (with confirmation)

---

## Threading Model

The TUI uses Python threading to keep the interface responsive during long sync operations.

**Design:**
```
Main thread (Textual event loop)
  ├─ Handles user input
  ├─ Renders UI
  └─ Receives messages from background threads

Background thread (MCRU)
  ├─ Runs syncer.run() (can take seconds/minutes)
  ├─ Posts progress callbacks
  └─ Posts completion with results
```

**Thread safety:** Textual's `PostMessage` system ensures that all UI updates happen on the main thread, even when data is generated by background threads.

**Example (from `tui/utils.py`):**
```python
syncer = ThreadedSyncer(config, dry_run=False)
syncer.on_complete = lambda results, error: self.handle_sync_complete(results, error)
syncer.start()  # Runs in background
# UI remains responsive
```

---

## Performance Considerations

**Large profiles:**
- Source/target with thousands of files: sync may take several seconds
- TUI will show progress spinner to indicate work is happening
- No UI blocks; spinner proves responsiveness

**Responsiveness:**
- All file I/O (reading, hashing, writing) runs in background thread
- Terminal remains interactive even with large operations
- Progress updates streamed to UI as files are processed

**Memory:**
- In-memory structures for sync are identical to CLI (`~O(file_count)` hashes and paths)
- TUI display buffers are minimal (single screen at a time)
- No significant overhead vs CLI

---

## Terminal Requirements

**Minimum terminal size:** 80x24 (standard VT100)  
**Recommended:** 100x30 or larger for comfortable navigation

**Feature support:**
- 16-bit color support recommended (most modern terminals)
- Mouse input supported (optional; keyboard-only navigation always works)
- Unicode support required for ASCII art and borders

**Tested on:**
- Windows Terminal (Windows 10+)
- macOS Terminal / iTerm2
- Linux: xterm, urxvt, GNOME Terminal, Konsole, etc.

**Known issues:**
- Very small terminals (<60 width) may wrap text awkwardly
- High-latency SSH connections may see delayed input rendering

---

## Keyboard Reference

### Global Bindings (All Screens)

| Key | Action |
|-----|--------|
| `q` | Quit (from home) / Back (from other screens) |
| `Escape` | Back to home |

### Home Screen

| Key | Action |
|-----|--------|
| `↑` / `↓` | Navigate command list |
| `Enter` | Execute selected command |
| `p` | Profile screen |
| `s` | Suite screen |
| `r` | Run screen |
| `h` | Reports screen |
| `c` | Config screen |
| `q` | Quit |

### Profile Screen (Phase 2)

| Key | Action |
|-----|--------|
| `↑` / `↓` | Navigate profile list |
| `a` | Add profile |
| `e` | Edit selected |
| `d` | Delete selected |
| `v` | Verify paths |

### Suite Screen (Phase 3)

| Key | Action |
|-----|--------|
| `↑` / `↓` | Navigate suite list |
| `a` | Add suite |
| `e` | Edit selected |
| `d` | Delete selected |
| `m` | Manage profiles |

### Run Screen (Phase 4)

| Key | Action |
|-----|--------|
| `↑` / `↓` | Navigate profile/suite list |
| `Space` | Start sync |
| `Escape` | Cancel (during run) / Back (after completion) |

### Reports Screen (Phase 5)

| Key | Action |
|-----|--------|
| `↑` / `↓` | Navigate report list |
| `/` | Search/filter reports |
| `v` | View selected report |
| `d` | Delete selected |
| `p` | Prune old reports |

### Backups Screen (Placeholder)

Simple placeholder directing to CLI. Use: `mcru backup --help`

**Keybindings:**

| Key | Action |
|-----|--------|
| `Escape` | Back to home screen |

### Config Screen (Phase 6)

| Key | Action |
|-----|--------|
| `o` | Open config directory |
| `v` | View mapping presets |
| `r` | Reset presets |
| `R` | Reset all (with confirmation) |

---

## Troubleshooting

### Terminal doesn't render ASCII art properly

**Symptom:** Garbled characters or missing boxes in home screen

**Fix:**
1. Ensure terminal supports Unicode: `echo "✓ Unicode works"`
2. Try a different terminal emulator
3. Check locale: `echo $LANG` (should include UTF-8)

### UI is slow or laggy

**Symptom:** Typing is delayed or rendering glitches

**Fix:**
1. Increase terminal window size (very small terminals = slower rendering)
2. Check system CPU/memory usage
3. For SSH: try local TUI instead of remote session

### Colors look wrong

**Symptom:** Text is hard to read or colors are inverted

**Fix:**
1. Textual auto-detects terminal color support
2. Try setting: `export FORCE_COLOR=1; mcru-tui`
3. Check terminal color settings (24-bit truecolor vs 8-bit palette)

### Mouse doesn't work

**Symptom:** Mouse clicks don't navigate

**Fix:**
1. Not all terminals support mouse input in TUI mode
2. Use keyboard navigation (always functional)
3. Try: `export TERM=xterm-256color; mcru-tui`

### Profiles won't load

**Symptom:** Profile list is empty or error on screen

**Fix:**
1. Create a profile from CLI first: `mcru profile add test ./src ./dst`
2. Check `~/.mcru/profiles.json` exists and is valid JSON
3. Try reset: `mcru config reset` (deletes all data) or `mcru profile list` to verify

---

## Configuration

TUI reads from the same `~/.mcru/` directory as CLI. No separate TUI configuration is needed.

**Configuration files (shared with CLI):**
- `~/.mcru/profiles.json` — Profiles
- `~/.mcru/suites.json` — Suites
- `~/.mcru/mapping-presets.json` — Mapping presets
- `~/.mcru/reports/` — Report history

**Environment variables:**
- `MCRU_MAPPING_FILE` — Override mapping presets location (same as CLI)
- `FORCE_COLOR=1` — Force color output (if auto-detection fails)
- `TERM` — Terminal type (auto-detected; usually no need to set)

---

## Future Enhancements

**Planned features:**
- [ ] **Drag-drop suite reordering** — Visual profile ordering in suite screen
- [ ] **Favorites sidebar** — Quick access to most-used profiles
- [ ] **Dashboard view** — Summary of recent runs and upcoming schedules
- [ ] **Undo/Redo** — Revert sync operations
- [ ] **Scheduled runs** — Background sync on timer
- [ ] **Diff viewer** — Visual diff before confirmation
- [ ] **Profile templates** — Quick-start presets
- [ ] **Plugin system** — Custom screens and commands

**Architecture supports these via:**
- ConfigManager extensibility
- Screen plugin pattern
- Widget composition

---

## See Also

- [docs/architecture.md](architecture.md) — Overall program architecture and data flow
- [docs/commands.md](commands.md) — CLI reference (profiles, suites, runs, config)
- [docs/folder-mapping.md](folder-mapping.md) — Mapping presets detailed reference
- [README.md](../README.md) — Quick start and overview
