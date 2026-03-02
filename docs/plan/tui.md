# Plan: Add Optional TUI with Textual

**Status:** Basic setup phase

---

## Overview

Add a parallel TUI entry point (`mcru-tui`) powered by [Textual](https://github.com/Textualize/textual) that provides full feature parity with the CLI. The TUI will feature an interactive home screen with ASCII art and command navigation, with arrow-key driven menus that launch into detailed management screens. Core business logic (ConfigManager, MCRU, Reporter) will be reused; sync operations will run in background threads for UI responsiveness. All existing CLI functionality remains unchanged.

---

## Key Decisions

- **Full feature parity** — all CLI commands will eventually have TUI equivalents
- **Threading model** — background threads for sync operations keep UI responsive; thread-safe message passing via Textual's callback system
- **Home screen design** — ASCII art with animated title + command menu for quick navigation
- **Code organization** — new `tui/` module keeps TUI code isolated from CLI
- **Business logic reuse** — ConfigManager, MCRU, Reporter remain unchanged; TUI is purely a presentation layer
- **Documentation** — separate `docs/tui.md` for TUI-specific details

---

## Implementation Phases

### Phase 1: Basic Setup (Current)

**Goal:** Establish TUI module structure and entry point; verify CLI remains functional.

#### 1.1 Update Dependencies and Entry Point

**File:** `setup.py`

- Add `textual >= 0.30.0` to `install_requires`
- Add `mcru-tui` entry point: `"mcru-tui=tui.main:run"`
- Update `py_modules` list to include new `tui` package (or add `packages=find_packages()`)

**Verification:**
```bash
pip install -e .
mcru --help          # CLI should work
mcru-tui --help      # TUI should work (or launch)
```

#### 1.2 Create TUI Module Structure

**New directory structure:**
```
tui/
├── __init__.py
├── main.py                    # Entry point
├── app.py                     # Main TextualApp
├── utils.py                   # Threading wrapper, helpers
├── screens/
│   ├── __init__.py
│   ├── home.py                # Home screen (ASCII art + command menu)
│   ├── profiles.py            # Profile management
│   ├── suites.py              # Suite management
│   ├── run_profile.py         # Sync execution (threaded)
│   ├── reports.py             # View reports
│   └── config.py              # Settings/presets
└── widgets/
    ├── __init__.py
    ├── result_table.py        # Sync results display
    ├── progress_spinner.py    # Async progress indicator
    └── profile_selector.py    # Profile dropdown

tests/test_tui/
├── __init__.py
└── test_screens.py            # Placeholder for future tests
```

#### 1.3 Implement Entry Point and App Shell

**File:** `tui/main.py`

```python
def run():
    """Entry point for mcru-tui."""
    from tui.app import MCRecipeApp
    app = MCRecipeApp()
    app.run()
```

**File:** `tui/app.py`

- Create `MCRecipeApp` class extending `textual.app.App`
- Initialize `ConfigManager` on startup (loads profiles, suites, presets)
- Set up color scheme and event bindings
- Route initial screen push (home screen)
- Provide methods for screen navigation: `push_profile_screen()`, `push_run_screen()`, etc.

#### 1.4 Implement Home Screen

**File:** `tui/screens/home.py`

- Display ASCII art animation at top (cycle through ~3-4 frames)
- Command input line below art
- List of available commands:
  - Profile — manage profiles
  - Suite — manage suites
  - Run — execute sync
  - Reports — view historical runs
  - Config — settings/presets
  - Quit — exit TUI
- Arrow key navigation and Enter to select/launch
- Show recent profile name or "No profile selected" in header
- Key bindings: `q` to quit, Arrow Up/Down to navigate, Enter to select

#### 1.5 Implement Placeholder Screens

Create minimal placeholder screens for each feature (to be filled in Phase 2):

- **`tui/screens/profiles.py`** — Lists profiles, shows title, "Profiles Screen (TBD)"
- **`tui/screens/suites.py`** — Shows suites list placeholder
- **`tui/screens/run_profile.py`** — Shows run/execution placeholder
- **`tui/screens/reports.py`** — Shows reports list placeholder
- **`tui/screens/config.py`** — Shows config paths placeholder

Each screen should have a "Back" button or `Escape` key to return to home.

#### 1.6 Implement Threading Utilities

**File:** `tui/utils.py`

- `ThreadedSyncer` class that wraps `MCRU.run()`
- Emits progress callbacks that post to Textual's message queue
- Example callback signature: `on_progress(current_file: int, total_files: int, current_operation: str)`
- Exception handling and result delivery back to main thread

#### 1.7 Update Documentation

**File:** `README.md`

- Add "TUI Mode" section with quick start: `mcru-tui`
- Note feature parity with CLI
- Update entry points table:
  | Command | Purpose |
  | --- | --- |
  | `mcru` | Terminal CLI |
  | `mcru-tui` | Interactive TUI |
- Link to `docs/tui.md` for detailed TUI documentation

**File:** `docs/architecture.md`

- Add section "TUI Layer (`tui/` module)"
- Document screen hierarchy, threading model, reuse of business logic
- Update data flow diagram to show TUI path alongside CLI path
- Link to `docs/tui.md` for TUI-specific details

**File:** `docs/tui.md` (new)

- Overview of TUI features and screen layout
- Home screen commands and navigation reference
- Placeholder sections for each screen (to be filled in Phase 2)
- Threading model explanation
- Performance considerations
- Troubleshooting (terminal size, Unicode support)
- Future enhancement ideas (hot-reload previews, drag-drop, etc.)

#### 1.8 Verification Checklist

- [ ] `pip install -e .` completes without errors
- [ ] `mcru --help` displays CLI help (CLI unchanged)
- [ ] `mcru-tui` launches home screen with ASCII art
- [ ] Arrow keys navigate command list
- [ ] Enter key is captured (displays "Selected: <command>" or similar)
- [ ] `Escape` or `q` exits cleanly
- [ ] Clicking "Profile" navigates to profiles screen
- [ ] Back button returns to home screen
- [ ] Textual doesn't conflict with Click imports
- [ ] ConfigManager loads successfully in TUI context

---

### Phase 2: Profile Management Screen

> To be implemented in next iteration

- List all profiles in a table
- Add/Edit/Delete/Verify sub-commands
- Form screens for profile creation/editing
- Reuse `ConfigManager` profile methods

---

### Phase 3: Suite Management Screen

> To be implemented in next iteration

- List all suites
- Add/Edit/Delete/Show sub-commands
- Reorder profiles in suite (arrow navigation)
- Reuse `ConfigManager` suite methods

---

### Phase 4: Sync Execution Screen

> To be implemented in next iteration

- Profile/Suite selector (dropdown)
- Options panel: Dry-run, overrides
- Progress display (spinner, file count, % complete)
- Result summary on completion
- Error inline display
- Reuse `Reporter` formatting

---

### Phase 5: Reports Screen

> To be implemented in next iteration

- List recent reports with timestamp, profile, summary
- Search by name, date range
- View full report text (scrollable)
- Reuse `ConfigManager` report methods

---

### Phase 6: Config Screen

> To be implemented in next iteration

- Show paths: config dir, profiles, suites, presets
- Quick actions: Open dir, View presets, Reset presets, Reset all
- Reuse `ConfigManager` config methods

---

### Phase 7: Polish & Testing

> To be implemented after core screens complete

- Add unit tests for screens (Textual test framework)
- Add integration tests with mock ConfigManager
- Polish animations, key bindings, color scheme
- Performance profiling under large profile/suite counts
- Documentation expansion: advanced usage, tips & tricks

---

## File Manifest

### Core TUI Files (Phase 1)
- `tui/__init__.py` — package marker
- `tui/main.py` — entry point
- `tui/app.py` — main app class
- `tui/utils.py` — threading, helpers
- `tui/screens/__init__.py` — screen exports
- `tui/screens/home.py` — home screen
- `tui/screens/profiles.py` — profile placeholder
- `tui/screens/suites.py` — suite placeholder
- `tui/screens/run_profile.py` — run placeholder
- `tui/screens/reports.py` — reports placeholder
- `tui/screens/config.py` — config placeholder
- `tui/widgets/__init__.py` — widget exports
- `tests/test_tui/__init__.py` — test package marker
- `tests/test_tui/test_screens.py` — placeholder test

### Updated Files (Phase 1)
- `setup.py` — add textual, mcru-tui entry point
- `README.md` — add TUI section
- `docs/architecture.md` — add TUI layer section
- `docs/tui.md` (new) — TUI documentation

---

## Dependencies

- **textual >= 0.30.0** — TUI framework
- Existing: click >= 8.0, Python >= 3.10

---

## Notes

- Textual is cross-platform (Linux, macOS, Windows); supports modern terminal features (16-bit color, mouse input)
- Threading adds minimal complexity; Textual's message system handles thread safety automatically
- ASCII art can be stored as a string constant or loaded from a file (e.g., `tui/assets/splash.txt`)
- Future phases can add features like profile favorites, sync history dashboard, drag-drop suite reordering, etc.
