# TUI Screen Design Plan

Page-by-page design checklist for the TUI implementation. Work through each screen one at a time — design first, then implement.

**Status key:** `[ ]` not started · `[~]` in design · `[x]` designed & approved · `[x]` implemented

---

## Screen Index

| Screen | File | Status |
|--------|------|--------|
| [Home](#1-home-screen) | `tui/screens/home.py` | Implemented |
| [Profiles](#2-profiles-screen) | `tui/screens/profiles.py` | Implemented x |
| [Suites](#3-suites-screen) | `tui/screens/suites.py` | Implemented |
| [Run](#4-run-screen) | `tui/screens/run_profile.py` | Implemented |
| [Reports](#5-reports-screen) | `tui/screens/reports.py` | Implemented |
| [Backups](#6-backups-screen) | `tui/screens/backups.py` | Implemented |
| [Config](#7-config-screen) | `tui/screens/config.py` | Implemented |

---

## 1. Home Screen

**File:** `tui/screens/home.py`
**Status:** Implemented — revisit only if issues arise

### Design Checklist

- [x] ASCII art splash loaded from `.asciimtn` file with fallback
- [x] Version string displayed below art
- [x] Subtitle/hint text displayed
- [x] Command input field with placeholder
- [x] Command list with arrow-key navigation and `►` marker
- [x] Tab autocomplete on input
- [x] Enter executes command from input or selected list item
- [x] Routes to all feature screens
- [x] `q` / `Ctrl+C` exits cleanly
- [x] Input cleared after submission

### Open Questions

- [ ] Should command history (up/down in input) be wired up?
- [ ] Should the animation actually cycle frames (timer-based)?

---

## 2. Profiles Screen

**File:** `tui/screens/profiles.py`
**Status:** Implemented
**ConfigManager methods:** `list_profiles()`, `get_profile()`, `add_profile()`, `update_profile_field()`, `rename_profile()`, `remove_profile()`, `sort_profiles()`

### Layout Pattern

Lazygit-inspired three-panel layout:
- **`[1] Profiles`** — `ListView` of profile names with selection highlight (left)
- **`[2] Details`** — `Static` detail view of selected profile (right)
- **`[3] Actions`** — keybinding hint bar (bottom)
- **Status bar** — `Static` docked to bottom for transient messages

### Design Checklist

#### Layout
- [x] `[1] Profiles` panel — `ListView` of profile names with selection highlight
- [x] `[2] Details` panel — Name, Description, Source/Target with OK/MISSING indicator, Parsers, Mapping, Tags, Changelog, Created
- [x] `[3] Actions` bar — keybinding hints
- [x] Status bar for transient feedback (saves, errors, verify results)
- [x] Empty state with hint when no profiles exist
- [x] Sort mode label shown in `[1] Profiles` panel title

#### Key Bindings
- [x] `Escape` → back to home
- [x] `↑` / `↓` → navigate profile list
- [x] `a` → open Add Profile modal
- [x] `e` → open Edit Profile modal (pre-filled with selected profile)
- [x] `d` → delete selected with confirmation modal
- [x] `v` → verify paths on selected profile (result shown in status bar)
- [x] `s` → cycle sort modes: saved order → name A→Z → name Z→A → newest first → oldest first
- [x] `S` → persist current sort order to `profiles.json`

#### Add / Edit Form (Modal)
- [x] Modal overlay (`ModalScreen`) — not a sub-screen
- [x] Field: Name (text input, required)
- [x] Field: Source path (text input, required)
- [x] Field: Target path (text input, required)
- [x] Field: Description (optional text input)
- [x] Field: Parsers (checkbox per registered parser)
- [x] Field: Mapping preset (`Select` from available presets, or "(none)")
- [x] Field: Target changelog (checkbox)
- [x] Validation: name, source, target required; duplicate name blocked on add
- [x] `Enter` submits; saves via `ConfigManager`, refreshes list, re-selects edited profile
- [x] `Escape` cancels without saving
- [x] Edit mode pre-populates all fields; supports rename

#### Delete Confirmation
- [x] Confirmation modal (consistent with add/edit modal approach)
- [x] Shows profile name to confirm correct target
- [x] `y` / `Enter` confirms; `n` / `Escape` cancels
- [x] Calls `remove_profile()` and refreshes list; status bar shows result

#### Verify Paths
- [x] Runs `Path.exists()` on selected profile's source and target
- [x] Shows result in status bar (e.g., "Source OK  Target MISSING")

#### Edge Cases
- [x] No profiles → empty state with hint to press `a`
- [x] Profile with very long paths — full path shown in `[2] Details`; `[1] Profiles` shows name only
- [x] Parsers — comma-joined list in detail panel; "(none)" if empty

---

## 3. Suites Screen

**File:** `tui/screens/suites.py`
**Status:** Implemented
**ConfigManager methods:** `list_suites()`, `get_suite()`, `add_suite()`, `update_suite()`, `remove_suite()`, `add_profile_to_suite()`, `remove_profile_from_suite()`, `reorder_suite_profile()`

### Layout Pattern

Lazygit-inspired three-panel layout (same pattern as Profiles screen):
- **`[1] Suites`** — `ListView` of suite names (left)
- **`[2] Details`** — detail view: name, description, profile count, ordered profile list (right)
- **`[3] Actions`** — keybinding hint bar (bottom)
- **Status bar** — transient messages

### Design Checklist

#### Layout
- [x] `[1] Suites` panel — `ListView` of suite names with selection highlight
- [x] `[2] Details` panel — name, description, profile count, ordered profile list
- [x] `[3] Actions` bar — keybinding hints
- [x] Status bar for transient feedback
- [x] Empty state when no suites exist

#### Key Bindings
- [x] `Escape` → back to home
- [x] `↑` / `↓` → navigate suite list
- [x] `a` → open Add Suite form
- [x] `e` → open Edit Suite form (name + description)
- [x] `d` → delete selected suite (with confirmation)
- [x] `m` → open Manage Profiles sub-screen for selected suite

#### Add / Edit Suite Form
- [x] Modal overlay (consistent with Profiles screen)
- [x] Field: Name (text input)
- [x] Field: Description (optional text input)
- [x] Validation: name required and unique (on add)
- [x] Submit saves via `ConfigManager` and refreshes list

#### Manage Profiles Sub-screen (panel layout)
- [x] `[1] In Suite` panel — ordered `ListView` of profiles currently in the suite (left)
- [x] `[2] Available` panel — `ListView` of profiles not yet in the suite (right)
- [x] `[3] Actions` bar — keybinding hints
- [x] `a` → add highlighted profile from `[2]` into suite
- [x] `d` → remove highlighted profile from `[1]`
- [x] `↑` / `↓` → navigate active panel
- [x] `Tab` → switch focus between `[1]` and `[2]`
- [x] `[` / `]` (or `shift+↑` / `shift+↓`) → reorder selected profile in `[1]`
- [x] `Escape` → back to suite list (auto-saves order)

#### Edge Cases
- [x] Empty suite → shows "(no profiles)" in manage view
- [x] Profile referenced by suite that no longer exists — show as missing in manage view
- [x] Only one profile in suite → reorder controls disabled or no-op

---

## 4. Run Screen

**File:** `tui/screens/run_profile.py`
**Status:** Implemented
**Uses:** `ConfigManager.list_profiles()`, `ConfigManager.list_suites()`, `MCRU`, `Reporter`, `ThreadedSyncer` (from `tui/utils.py`)

### Design Checklist

### Layout Pattern

Three-panel layout with phase-dependent content:
- **`[1]`** — selector / progress / results (left or full-width depending on phase)
- **`[2]`** — options / details / error log (right)
- **`[3] Actions`** — keybinding hint bar (bottom)
- **Status bar** — transient messages

#### Layout — Pre-Run (Selection)
- [x] `[1] Profiles / Suites` panel — `ListView` selector; `Tab` toggles Profile / Suite mode
- [x] `[2] Options` panel — dry-run checkbox, optional source/target/preset overrides
- [x] `[3] Actions` bar — `Space` start · `Tab` toggle mode · `Esc` back
- [x] Status bar for validation feedback
- [x] `Space` → begin sync

#### Layout — During Sync
- [x] `[1] Progress` panel — current operation label and counter
- [x] `[2] Details` panel — profile/suite name and start timestamp
- [x] `[3] Actions` bar — cancel hint
- [x] `Escape` / `Ctrl+C` → cancel sync (stop thread gracefully)

#### Layout — Post-Run Summary
- [x] `[1] Results` panel — counts: Added, Updated, Removed, Unchanged, Dirs added, Dirs removed, Errors
- [x] `[2] Details` panel — profile/suite name, dry-run indicator, report path, backup/skipped details
- [x] `[3] Actions` bar — `r` re-run · `Esc` back to selection
- [x] Dry-run indicator shown prominently if applicable

#### Key Bindings
- [x] `Escape` → cancel (during run) / back to selection (pre/post run)
- [x] `Space` → start sync (pre-run state)
- [x] `tab` → toggle Profile / Suite mode
- [x] `r` → re-run (post-run state)

#### Threading
- [x] `ThreadedSyncer` wraps `MCRU.run()` in a background thread
- [x] Progress callbacks post to Textual message queue (thread-safe)
- [x] Completion callback delivers result dict or exception to main thread
- [x] Cancel support: set a stop event checked inside the thread

#### Edge Cases
- [x] No profiles/suites → empty selector with hint to create one
- [x] Profile paths missing → show error before starting sync
- [x] Suite with 0 profiles → disable start
- [x] Sync errors mid-run → collect into errors list, show in summary
- [x] Suite run: progress per-profile

---

## 5. Reports Screen

**File:** `tui/screens/reports.py`
**Status:** Implemented
**ConfigManager methods:** `list_reports()` (or equivalent path listing), `get_report_content()`, `delete_report()`

### Layout Pattern

Lazygit-inspired three-panel layout:
- **`[1] Reports`** — `ListView` of report entries (profile/suite + date) (left)
- **`[2] Details`** — summary of selected report: counts, dry-run flag, error excerpt (right)
- **`[3] Actions`** — keybinding hint bar (bottom)
- **Status bar** — transient messages

### Design Checklist

#### Layout
- [x] `[1] Reports` panel — `ListView` of entries (profile/suite name + date) with selection highlight
- [x] `[2] Details` panel — report metadata and parsed summary counts where available
- [x] `[3] Actions` bar — keybinding hints
- [x] Search/filter input (toggled via `/`; appears as inline prompt above `[1]`)
- [x] Status bar for transient feedback
- [x] Empty state when no reports exist

#### Key Bindings
- [x] `Escape` → back to home
- [x] `↑` / `↓` → navigate report list
- [x] `/` → focus search input
- [x] `Enter` / `v` → view selected report (full text)
- [x] `d` → delete selected report (with confirmation)
- [x] `p` → prune old reports (keep last N — with confirmation)

#### Report Viewer Sub-screen
- [x] Modal overlay (consistent with other screens)
- [x] Scrollable text display of full `.txt` report
- [x] Report file name / path in header
- [x] `Escape` → close and return to list

#### Search / Filter
- [x] Filter applies to profile/suite name column (case-insensitive substring)
- [ ] Optional: filter by date range (start / end inputs)
- [x] Filter resets on `Escape` from search input

#### Prune
- [x] Confirmation prompt: "Keep last N reports? [10]"
- [x] Shows how many will be deleted before confirming

#### Edge Cases
- [x] No reports → empty state with hint
- [x] Report file deleted externally → handle missing file gracefully in viewer
- [x] Very long report file → ensure scrolling works

---

## 6. Backups Screen

**File:** `tui/screens/backups.py`
**Status:** Implemented
**Decision:** Full TUI implementation

### Design Checklist

#### Option A: CLI-Redirect Screen (Simple)
- [ ] Header: "Backups"
- [ ] Info text explaining backup management is via CLI
- [ ] Display list of available CLI commands with descriptions:
  - `mcru backup list`
  - `mcru backup view <id>`
  - `mcru backup restore <id>`
  - `mcru backup pin <id>`
  - `mcru backup delete <id>`
  - `mcru backup prune`
- [ ] `Escape` → back to home

#### Option B: Full TUI Backup Screen
- [x] `[1] Backups` panel — `ListView` of backup entries (ID, profile, date) with selection highlight (left)
- [x] `[2] Details` panel — selected backup metadata: file count, size, pinned status (right)
- [x] `[3] Actions` bar — keybinding hints
- [ ] Key bindings:
  - [x] `↑` / `↓` → navigate list
  - [x] `v` → view backup file listing
  - [x] `r` → restore selected backup (with confirmation)
  - [x] `p` → pin/unpin selected backup
  - [x] `d` → delete selected backup (with confirmation)
  - [x] `P` → prune old backups (with confirmation)
  - [x] `Escape` → back to home
- [x] Restore confirmation: shows backup ID, date, profile name

**Decision:** [ ] Option A · [x] Option B

---

## 7. Config Screen

**File:** `tui/screens/config.py`
**Status:** Implemented
**ConfigManager methods:** `CONFIG_DIR`, `CONFIG_FILE`, `SUITES_FILE`, `DEFAULT_MAPPING_FILE`, paths to reports dir

### Layout Pattern

Two-panel layout (content is mostly static display, not a navigable list):
- **`[1] Paths`** — config paths with existence indicators (left)
- **`[2] Actions`** — quick action descriptions and current state (right)
- **`[3] Keys`** — keybinding hint bar (bottom)
- **Status bar** — transient feedback

### Design Checklist

#### Layout
- [x] `[1] Paths` panel — labelled list of paths with OK/MISSING indicators: config dir, profiles file, suites file, mapping presets, reports dir
- [x] `[2] Actions` panel — quick action descriptions: open dir, view presets, reset presets, reset all
- [x] `[3] Keys` bar — keybinding hints
- [x] Status bar for transient feedback (reset results, errors)

#### Key Bindings
- [x] `Escape` → back to home
- [x] `o` → open config directory
- [x] `v` → view mapping presets
- [x] `r` → reset presets (with confirmation)
- [x] `R` → reset all (with strong confirmation)

#### View Mapping Presets
- [x] Modal overlay (consistent with other screens)
- [x] Scrollable JSON display of mapping presets file
- [x] Read-only (editing is out of scope for TUI)

#### Reset Presets Confirmation
- [x] Two-step: press `r`, then confirm with `y`
- [x] Shows what will be reset

#### Reset All Confirmation
- [x] Three-step or typed confirmation (e.g., type "RESET" to confirm)
- [x] Red/danger styling to make it clear this is destructive

#### Edge Cases
- [x] Config directory doesn't exist yet → show MISSING status
- [x] Mapping presets file is corrupt JSON → show error in viewer

---

## Shared Design Decisions

Resolved decisions carried forward from the Profiles screen. All future screens follow these patterns.

- [x] **Layout pattern** — lazygit-inspired panels: numbered `[1] List`, `[2] Details`, `[3] Actions` bar; `Static` status bar docked to bottom. Applied to all screens.
- [x] **List widget** — `ListView` with name-only items in `[1]` panel; full detail rendered in `[2]` panel via `Static` (not `DataTable`)
- [x] **Form style** — modal overlay (`ModalScreen`) for all add/edit forms
- [x] **Confirmation style** — modal overlay for destructive actions; status bar for lightweight feedback (verify, sort results)
- [x] **Status / notification bar** — `Static` widget docked to bottom; updated via `_set_status()`
- [x] **Theme / color scheme** — Textual theme vars: `$primary`, `$surface`, `$text`, `$text-muted`, `$error`; panel borders use `solid $primary`
- [x] **Error display** — validation errors inline within modal form; runtime errors in status bar

---

## Implementation Order (Suggested)

1. **Profiles** — most foundational; other screens depend on profiles existing
2. **Suites** — builds on profiles; needed before Run can be useful
3. **Run** — core feature; requires profiles/suites to be in place
4. **Reports** — read-only, no dependencies; good for quick wins
5. **Config** — low complexity, mostly display
6. **Backups** — decision-dependent; do Option A first if short on time
