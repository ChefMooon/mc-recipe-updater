# mcru TUI — Interactive Terminal User Interface

Complete reference and user guide for the `mcru-tui` interactive mode.

Baseline cross-screen standards (keybinding fallback policy, phase model, and testing expectations) are maintained in [docs/tui-screen-standards.md](docs/tui-screen-standards.md).

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
| Backups | `b` | Manage backups | 5+ |
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
✅ Implemented screens for all core features  
✅ Entry point registration  
✅ Threading utilities for background operations

### Phase 2: Profile Management (Complete)

- **List profiles** — Panel view with selectable profile names and full details
- **Add profile** — Modal form to create a profile with paths, parsers, mapping preset, and changelog setting
- **Edit profile** — Modify existing profile fields, including rename
- **Delete profile** — Remove profile with confirmation
- **Verify profile** — Check that source/target paths exist

**Key bindings:**
- `a` → Add profile
- `e` → Edit selected
- `d` → Delete selected
- `v` → Verify paths

### Phase 3: Suite Management (Complete)

- **List suites** — Panel view with selectable suite names and full details
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

### Phase 4: Sync Execution (Complete)

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

### Phase 5: Reports Viewing (Complete)

- **List recent reports** — Table with Profile/Suite, Timestamp, Added/Updated/Removed counts
- **Search/filter** — By profile name, date range, result type
- **View full report** — Scrollable text view of complete report
- **Delete report** — Remove individual reports or bulk prune old reports

**Key bindings:**
- `/` → Search/filter
- `v` → View selected report
- `d` → Delete selected report
- `p` → Prune old reports

### Phase 5+: Backup Management (Complete)

Full backup management is available in the TUI:
- **List backups** — View backup entries with profile, date, and pinned state
- **View contents** — Inspect files inside a backup zip
- **Restore backup** — Restore selected backup with confirmation
- **Pin/unpin backup** — Protect important backups from normal pruning
- **Delete backup** — Remove selected backup with confirmation
- **Prune backups** — Keep the newest N backups, with preview and confirmation

See [docs/backups.md](backups.md) for complete CLI reference.

### Phase 6: Configuration (Complete)

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
| `s` | Cycle sort mode |
| `Shift+s` | Save sort order |
| `Ctrl+1/2/3` | Jump to section 1 (list) / 2 (details) / 3 (actions) |
| `Alt+1/2/3`, `F1/F2/F3` | Alternative section navigation keys |
| `Escape` / `q` | Back to home screen |
| `Ctrl+C` | Quit TUI immediately |

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
| `↑` / `↓` | Navigate profile/suite list (section 1) or navigate options (section 2, if focused there) |
| `Space` | Start sync (unless focused on a checkbox option, then toggles the checkbox) |
| `Tab` | Toggle Profile/Suite mode before running |
| `r` | Re-run after completion |
| `Ctrl+1/2/3` | Jump to section 1/2/3 |
| `Alt+1/2/3`, `F1/F2/F3` | Alternative section navigation keys |
| `Escape` | Cancel (during run) / Back to selection (after completion) |

**Option Navigation Details (Section 2):**
When focus is in the Options panel (section 2), use `Up` and `Down` arrows to cycle through available run options:
- **Dry run** (checkbox)
- **Create backups** (checkbox)
- **Force target changelog** (checkbox)
- **Source override** (text input)
- **Target override** (text input)
- **Mapping override** (text input)

Navigation wraps around: pressing Down on the last option cycles to the first, and Up on the first cycles to the last.

**Checkbox Behavior:**
When focus is on a checkbox option, press `Space` to toggle the option value (e.g., enable/disable dry run). This does **not** start the sync—it only toggles the checkbox. To start the sync, press `Space` while focus is on the profile/suite list (section 1), or click the Start button.

### Reports Screen (Phase 5)

| Key | Action |
|-----|--------|
| `↑` / `↓` | Navigate report list |
| `/` | Search/filter reports |
| `v` | View selected report |
| `d` | Delete selected |
| `p` | Prune old reports |

### Backups Screen

**Keybindings:**

| Key | Action |
|-----|--------|
| `↑` / `↓` | Navigate backup list |
| `v` | View selected backup contents |
| `r` | Restore selected backup |
| `p` | Pin/unpin selected backup |
| `d` | Delete selected backup |
| `P` | Prune old backups |
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
