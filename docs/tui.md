# mcru TUI — Interactive Terminal User Interface

Complete reference and user guide for the `mcru-tui` interactive mode.

Baseline cross-screen standards (keybinding fallback policy, phase model, and testing expectations) are maintained in [docs/tui-screen-standards.md](docs/tui-screen-standards.md).

---

## Overview

`mcru-tui` is a terminal user interface powered by [Textual](https://textualize.io/textual/) that provides an interactive, menu-driven alternative to the CLI. It offers the same functionality as `mcru` but with:
- Static home screen splash with ASCII art
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

The home screen will display a static ASCII art title, a command list, and command-entry help.

### Navigation

- Type a command and press **Enter**, or use the command list when the input is empty.
- **Alt+P/S/R/H/B/C** — Open Profiles, Suites, Run, Reports, Backups, or Config while the input has focus.
- **Alt+Q** or **Ctrl+C** — Quit from the focused command input.
- **Arrow Up/Down** — Move selection in the command list; they do not navigate command history.
- **Tab** — Complete a unique or first matching command.
- Type `q`, `quit`, or `exit` and press **Enter** to quit from command entry.

Command history and cycling the splash animation are deferred; the splash remains on its first frame.

---

## Home Screen

**Purpose:** Entry point for all TUI operations.

**Features:**
- Static ASCII art splash at top
- List of available commands with descriptions
- Arrow key navigation between commands
- Command entry and Alt-key quick access

**Commands:**
| Command | Shortcut | Purpose |
|---------|----------|---------|
| Profile | `Alt+P` | Manage sync profiles |
| Suite | `Alt+S` | Manage profile suites |
| Run | `Alt+R` | Execute sync operations |
| Reports | `Alt+H` | View run reports |
| Backups | `Alt+B` | Manage backups |
| Config | `Alt+C` | Settings and presets |
| Quit | `Alt+Q` / `Ctrl+C` | Exit TUI |

**Navigation:**
- Arrow keys move selection in the command list when the input is empty
- Enter submits typed input, or runs the selected command when the input is empty
- Alt-key shortcuts open their corresponding screens while the input has focus

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
- **Duplicate names** — The form remains open and focuses the name field for correction
- **Tab / Shift+Tab** — Move focus forward / backward through focusable controls

**Key bindings:**
- `a` → Add profile
- `e` → Edit selected
- `d` → Delete selected
- `v` → Verify paths
- `s` → Cycle sort mode
- `Shift+S` → Save sort order
- `q` / `Esc` → Back to home
- `Ctrl+C` → Quit TUI immediately, including from the add/edit and delete-confirmation modals
- `Ctrl+1/2/3`, `Alt+1/2/3`, or `F1/F2/F3` → Focus sections 1–3; focus only

Tab and Shift+Tab use normal focus traversal. Section keys never invoke profile actions and are not shown in the action bar.

### Phase 3: Suite Management (Complete)

- **List suites** — Panel view with selectable suite names and full details
- **Add suite** — Create new suite (name, optional description)
- **Edit suite** — Modify suite description
- **Delete suite** — Remove suite with confirmation
- **Manage profiles** — Add/remove/reorder profiles in suite

**Key bindings:**
- `a` → Add suite
- `e` → Edit selected
- `d` → Delete selected
- `m` → Manage profiles in suite
- `q` / `Esc` → Back to home
- `Ctrl+C` → Quit TUI immediately

**Navigation note:**
- The main Suites screen does not expose section-to-section navigation keys.
- Tab and Shift+Tab use normal focus traversal on the main screen; it has no screen-specific Tab action.
- Section headers on this screen are unlabeled by number because only the suite list is directly interactive.

**Manage Profiles sub-screen** (opened with `m` from the suite list):
- `a` → Add selected available profile to suite
- `d` → Remove selected in-suite profile
- `[` / `]` → Reorder selected profile up / down
- `Tab` → Switch between In Suite and Available panels
- `q` / `Esc` → Back to suite list
- `Ctrl+C` → Quit TUI immediately
- `Ctrl+1` / `Alt+1` / `F1` → Focus In Suite panel (Section 1)
- `Ctrl+2` / `Alt+2` / `F2` → Focus Available panel (Section 2)
- `Ctrl+3` / `Alt+3` / `F3` → Actions bar (not interactively focusable; a status message is shown)

**Deviations from TUI Screen Standards:**
The Suites screen is a synchronous CRUD management screen. The following standard items are inapplicable:
- **Phase model** (`selection` / `running` / `done`): Not applicable — all operations are immediate synchronous config writes with no async execution phase.
- **Threading and callback safety** (run tokens, stale callback rejection): Not applicable — no background threads are used.

The status bar provides immediate success/error feedback. The main Suites screen has no section-focus bindings; Manage Profiles supports Ctrl/Alt/F1–F3 focus fallbacks. This screen-specific scope does not change the baseline for asynchronous workflows.

### Phase 4: Sync Execution (Complete)

**Pre-execution:**
- Profile/Suite selector (dropdown or searchable list)
- Options panel:
  - [ ] Dry-run (preview only, no file changes)
  - [ ] Create backup before a live sync
  - [ ] Force target changelog
  - Override source path (optional)
  - Override target path (optional)
  - Override mapping preset (optional)
- Start button

**During execution:**
- Animated progress spinner
- Current operation label (e.g., "Scanning source...")
- File count: current/total
- Percentage complete (if calculable)
- **Cancellation:** Escape requests cooperative cancellation and leaves the screen running until the worker completes. Ctrl+C requests cancellation and closes the TUI promptly without joining the worker on the UI thread. The non-daemon profile worker may remain alive until its current filesystem operation returns and it observes cancellation.

**On completion:**
- Result summary:
  - ✅ Added files count
  - 🔄 Updated files count
  - ❌ Removed files count
  - ✓ Unchanged files count
  - ⚠ Errors count (if any)
- Option to view full error details (if errors occurred)
- Report path is shown when the current run path generates a report
- Back button to select another profile/suite
- Outcome is `success`, `partial`, `failed`, or `cancelled`; report, changelog, and backup-finalization failures are shown as post-run warnings and can make a completed run `partial`.
- A cancelled run retains completed-operation results and explicitly warns that completed changes were not rolled back.

**Key bindings:**
- Click **Start** or press `Space` to start; Space on a focused checkbox toggles that option instead.
- `Ctrl+1/2/3`, `Alt+1/2/3`, or `F1/F2/F3` → Focus sections 1–3; focus only
- `Tab` → Toggle Profile/Suite mode during selection
- `Escape` / `q` → Request cancellation while running; return to selection when done; return home from selection
- `Ctrl+C` → Request cooperative cancellation if running, then close the TUI promptly

Both the source and target must already exist as directories before a run starts.

- **Delete report** — Remove individual reports or bulk prune old reports
- New reports persist an explicit outcome. Older reports without outcome metadata remain visible and are classified as `unknown`; no outcome is inferred from their contents.
- Report reads and summaries run in a worker, and stale reads are ignored when the selected report changes.

**Key bindings:**
- `/` → Search/filter
- `v` → View selected report
- `d` → Delete selected report
- `p` → Prune old reports
- `q` / `Escape` → Back to home; Escape closes and clears an open search first. With search focused, `q` is entered as search text.
- `Ctrl+C` → Quit TUI immediately
- `Ctrl+1` / `Alt+1` / `F1` → Focus Reports list (Section 1)
- `Ctrl+2` / `Alt+2` / `F2` → Focus Details panel (Section 2)
- `Ctrl+3` / `Alt+3` / `F3` → Focus Actions bar (Section 3)

### Phase 5+: Backup Management (Complete)

Full backup management is available in the TUI:
- **List backups** — View backup entries with profile, date, and pinned state
- **View contents** — Inspect files inside a backup zip
- **Restore backup** — Restore selected backup with confirmation
- **Pin/unpin backup** — Protect important backups from normal pruning
- **Delete backup** — Remove selected backup with confirmation
- **Prune backups** — Keep the newest N backups, with preview and confirmation
- Backup IDs identify rows unambiguously. If prune candidates change after preview, deletion is aborted; filesystem and ZIP errors are reported in the status bar.

See [docs/backups.md](backups.md) for complete CLI reference.

**Key bindings:**
- `v` → View selected backup contents
- `r` → Restore selected backup
- `p` → Pin/unpin selected backup
- `d` → Delete selected backup
- `P` → Prune backups
- `q` / `Esc` → Back to home
- `Ctrl+C` → Quit TUI immediately
- `Ctrl+1` / `Alt+1` / `F1` → Focus Backups list (Section 1)
- `Ctrl+2` / `Alt+2` / `F2` → Focus Details panel (Section 2)
- `Ctrl+3` / `Alt+3` / `F3` → Focus Actions bar (Section 3)
- Tab and Shift+Tab use normal focus traversal; section focus keys only move focus.

### Phase 6: Configuration (Complete)

- **Show paths:**
  - `~/.mcru/` — Config directory
  - `~/.mcru/profiles.json` — Profiles file
  - `~/.mcru/suites.json` — Suites file
  - `~/.mcru/mapping-presets.json` — Mapping presets
  - `~/.mcru/reports/` — Reports directory

- **Quick actions:**
  - Open config directory (in file explorer)
  - Reset mapping presets to defaults
  - Reset all (`~/.mcru/` wiped and re-initialized)
- Config shows the effective mapping file path. When `MCRU_MAPPING_FILE` selects an external file, resetting bundled presets is disabled and explained in the screen.
- Malformed profiles, suites, or global settings are preserved and reported as a recovery-needed status so the TUI remains reachable. Writes to a malformed profiles/suites file are blocked until recovery; reset-all stages valid defaults before replacing user data and preserves existing data if staging fails.

**Key bindings:**
- `o` → Open directory
- `v` → View presets
- `r` → Reset presets
- `R` → Reset all (with confirmation)
- `q` / `Esc` → Back to home
- `Ctrl+C` → Quit TUI immediately
- `Ctrl+1` / `Alt+1` / `F1` → Focus Paths panel (Section 1)
- `Ctrl+2` / `Alt+2` / `F2` → Focus Settings/actions panel (Section 2)
- `Ctrl+3` / `Alt+3` / `F3` → Focus Keys bar (Section 3)
- Tab and Shift+Tab use normal focus traversal; section focus keys only move focus.

**Deviation from TUI Screen Standards:**
Config is a static settings and maintenance screen rather than a CRUD or execution workflow. It follows the global quit/back and section keybinding policy, but keeps a static Paths / Actions / Keys layout instead of introducing a phase model or interactive list. Section focus keys are focus-only and never trigger open, reset, or destructive actions.

---

## Threading Model

The TUI uses Python threading to keep the interface responsive during long sync operations.

**Design:**
```
Main thread (Textual event loop)
  ├─ Handles user input
  ├─ Renders UI
  └─ Receives messages from background threads

Background worker (Run sync / report reads)
  ├─ Runs syncer.run() or reads and summarizes report contents
  ├─ Posts progress callbacks
  └─ Posts completion or report data
```

Run syncs and report reads/summaries use background workers. Report selection generations reject stale worker results. Profile/suite CRUD, backup actions, and Config maintenance actions are synchronous; their success and failure feedback is shown in the status bar. The baseline's worker-only phase, cancellation, and callback rules are not applicable to those operations because they do not start workers.

Ctrl+C on Run signals cooperative cancellation and exits without waiting for worker cleanup. Cancellation does not roll back completed filesystem mutations, and a non-daemon profile worker can continue until its current filesystem operation returns.

**Example (from `tui/utils.py`):**
```python
syncer = ThreadedSyncer(config, dry_run=False)
syncer.on_complete = lambda results, error: self.handle_sync_complete(results, error)
syncer.start()  # Runs in background
```

---

## Performance Considerations


**Responsiveness:**
**Memory:**
- TUI display buffers are minimal (single screen at a time)
- No significant overhead vs CLI

---
- Mouse input supported (optional; keyboard-only navigation always works)
- Unicode support required for ASCII art and borders
**Known issues:**
- High-latency SSH connections may see delayed input rendering

---

| Key | Action |
|-----|--------|
| `Ctrl+C` | Quit from every screen and modal; on Run, signal cancellation before closing |
| `q` | Back on screens where applicable; type `q` and press Enter to quit from Home |
| `Escape` | Back, close a modal, or request Run cancellation according to the current screen/phase |

Screen action bars show task actions only; section-focus fallbacks and generic arrow-key navigation remain implicit.

### Home Screen

| Key | Action |
|-----|--------|
| `↑` / `↓` | Navigate command list |
| `Enter` | Submit typed command, or execute the selected command when input is empty |
| `Alt+P` | Profile screen |
| `Alt+S` | Suite screen |
| `Alt+R` | Run screen |
| `Alt+H` | Reports screen |
| `Alt+B` | Backups screen |
| `Alt+C` | Config screen |
| `Alt+Q` / `Ctrl+C` | Quit |
| `Tab` | Complete a command from the input |
| `q`, `quit`, `exit` + `Enter` | Quit from command entry |

Home has no numbered sections or section-focus fallbacks; its Alt shortcuts route to feature screens.

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
| `Tab` / `Shift+Tab` | Normal focus traversal |
| `Ctrl+1/2/3` | Focus-only section 1 (list) / 2 (details) / 3 (actions) |
| `Alt+1/2/3`, `F1/F2/F3` | Focus-only section fallbacks |
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
| `Tab` / `Shift+Tab` | Normal focus traversal on the main screen |
| `q` / `Escape` | Back to home |
| `Ctrl+C` | Quit TUI immediately |

The main Suites screen does not expose section-focus keys. In Manage Profiles, `Tab` switches between the In Suite and Available lists; Ctrl/Alt/F1–F3 focus sections 1–3, with section 3 reporting that it is not focusable.

### Run Screen (Phase 4)

| Key | Action |
|-----|--------|
| `↑` / `↓` | Navigate profile/suite list (section 1) or navigate options (section 2, if focused there) |
| `Space` | Start sync (unless focused on a checkbox option, then toggles the checkbox) |
| `Tab` | Toggle Profile/Suite mode during selection |
| `r` | Re-run after completion |
| `Ctrl+1/2/3` | Focus-only section 1/2/3 |
| `Alt+1/2/3`, `F1/F2/F3` | Focus-only section fallbacks |
| `Escape` / `q` | Request cancellation while running; return to selection when done; return home from selection |
| `Ctrl+C` | Request cooperative cancellation, then close the TUI promptly |

Section focus keys are focus-only. Cancellation preserves completed results and does not roll back changes. A non-daemon profile worker may continue until its current filesystem operation returns.

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
| `q` / `Escape` | Back to home; Escape closes and clears an open search first; focused search treats `q` as text |
| `Ctrl+C` | Quit TUI immediately, including from viewer and confirmation modals |
| `Ctrl+1/2/3`, `Alt+1/2/3`, `F1/F2/F3` | Focus-only section navigation |

The report list includes counts and an outcome. New reports store `success`, `partial`, `failed`, or `cancelled`; legacy reports without metadata are shown as `unknown`. Filters include name, inclusive date range, and outcome. Tab uses normal focus traversal.

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
| `q` | Back to home screen |
| `Escape` | Back to home screen |
| `Ctrl+C` | Quit TUI immediately |
| `Ctrl+1/2/3`, `Alt+1/2/3`, `F1/F2/F3` | Focus-only section navigation |
| `Tab` / `Shift+Tab` | Normal focus traversal |

### Config Screen (Phase 6)

| Key | Action |
|-----|--------|
| `o` | Open config directory |
| `v` | View mapping presets |
| `r` | Reset presets |
| `R` | Reset all (with confirmation) |
| `q` / `Escape` | Back to home |
| `Ctrl+C` | Quit TUI immediately, including from viewer and confirmation modals |
| `Ctrl+1/2/3`, `Alt+1/2/3`, `F1/F2/F3` | Focus-only section navigation |
| `Tab` / `Shift+Tab` | Normal focus traversal |

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
