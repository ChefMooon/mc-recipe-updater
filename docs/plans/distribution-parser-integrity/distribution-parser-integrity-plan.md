---
title: "Distribution and Parser Integrity - Implementation Plan"
status: COMPLETED
current_phase: 3 / 3
created: 2026-09-28
last_updated: 2026-09-28
---

# Overall Plan Completion Status

* **Final State:** COMPLETED
* **Total Phases Completed:** 3 / 3
* **Summary of Outcome:** All phases passed focused and full-suite checks. Wheel/sdist packaging, installed-resource loading, registry-driven parser choices, and unknown-parser validation are complete. The installed wheel was smoke-tested outside the checkout. Committed as `f45c15c`.

# Specification & Overview

### 1. Scope & Objective
- **Goal:** Make installed distributions include the default mapping presets and ensure CLI parser options match parsers the sync engine actually supports.
- **In-Scope:** Setuptools wheel/sdist resource inclusion; a stable resource-loading path shared by configuration, CLI reset, and TUI config; parser choices derived from the registry; clear handling of unknown parsers in saved profiles; packaging and CLI regression tests.
- **Out-of-Scope:** Changing preset contents, overwriting an existing user preset file during upgrades, renaming all top-level modules, changing parser transformations, or migrating build tooling wholesale.

### 2. Technical Constraints & Architecture
- `setup.py` declares flat `py_modules` and `find_packages()` but no package data. `mc_recipe_updater.egg-info/SOURCES.txt` does not list the root `mapping-presets.json`.
- `config.py` expects `mapping-presets.json` adjacent to `config.py`; the CLI copies it on preset reset, and `tui/screens/config.py` reads it. Editable/source runs can therefore work while built distributions omit the resource.
- `registry.py` implements `strip_bom`, `normalize_line_endings`, and `strip_trailing_whitespace`. CLI choices repeat a hard-coded list containing unsupported `lowercase_names` and omitting the implemented trailing-whitespace parser. `syncer.py` silently ignores parser names for which `get_parser()` returns `None`.
- **Required behavior:** A wheel and source distribution contain a usable default preset resource; all user-facing parser choices reflect `registry.list_parsers()`; an unknown parser in persisted profile data fails clearly before sync rather than silently doing nothing.
- **Resolved decision (owner-selected):** Add a dedicated `mcru_resources` package and make `mcru_resources/mapping-presets.json` the single bundled source of truth. Include it as setuptools package data and load/copy it through `importlib.resources`. Keep the existing flat application modules and console entry points; do not convert the application layout or add a custom build hook. This avoids coupling core configuration to `tui` and avoids a broader import migration.
- **Assumptions:** Preserve existing console-script names and editable-install behavior. User-edited `~/.mcru/mapping-presets.json` remains authoritative after first creation and is not overwritten by upgrades.
- **Risk:** Resource access currently assumes a filesystem `Path`; the shared resource API must update config reset and TUI viewing as well as initial seeding, not just the wheel manifest. Tests that patch `BUNDLED_MAPPING_FILE` must move to the resource API boundary.

---

# Execution Plan & Handoffs

## Phase 1: Packaging Strategy and Regression Baseline
- **Status:** COMPLETED
- **Objective:** Establish the owner-selected resource package as the single source of bundled preset data and add a reproducible distribution regression test.
- **Dependencies:** The resource-layout decision is resolved: retain flat application modules and use a dedicated `mcru_resources` package.

### Tasks
- [x] Add `mcru_resources/__init__.py` and move the canonical bundled defaults from the repository-root `mapping-presets.json` to `mcru_resources/mapping-presets.json`; do not change preset contents.
- [x] Add a focused `tests/test_packaging.py` regression test that builds into a temporary directory and verifies the preset resource is present in the distribution.
- [x] Confirm `find_packages()` discovers `mcru_resources` while existing top-level application imports and console entry points remain unchanged.
- [x] Ensure test builds use temporary directories and do not rewrite committed/generated `build/` or `mc_recipe_updater.egg-info/` files.

### Verification & Acceptance Criteria
*All criteria must pass before advancing to the handoff report.*
- [x] **Automated Checks:** `python -m pytest tests/test_packaging.py -q` builds and inspects a distribution using temporary output directories.
- [x] **Functional Assertions:** The resource package is discovered by setuptools and the archive contains exactly one canonical bundled preset file at `mcru_resources/mapping-presets.json`.
- [x] **Functional Assertions:** Existing top-level imports and console entry points remain unchanged; no root-level duplicate default file is needed at runtime.
- [x] **Functional Assertions:** The design preserves the current user-data precedence and does not overwrite local presets on upgrade.

### Plan Compliance Checklist
*Verify each item against the actual diff before claiming this phase complete. Do not mark the phase COMPLETED if any item fails.*
- [x] **Required Files:** `mapping-presets.json` (move), `mcru_resources/__init__.py`, `mcru_resources/mapping-presets.json`, and `tests/test_packaging.py`.
- [x] **Boundaries:** No application module migration, public entry-point rename, default preset content change, or committed build/egg-info regeneration.
- [x] **Legacy Code Removed:** Remove the root-level bundled JSON duplicate after moving it; user data at `~/.mcru/mapping-presets.json` remains unchanged.
- [x] **Acceptance Checks:** Run the packaging test and verify the archive contains the resource at the selected package path.

### Phase 1 Handoff & Verification Report
- **Compliance Check:** PASSED
- **Verification Result:** PASSED
- **Execution Proof / Logs:** `python -m pytest tests/test_packaging.py -q` — 1 passed. The temporary wheel contained exactly one preset resource at the selected package path.
- **Artifacts Created/Modified:** Moved the unchanged root `mapping-presets.json` into `mcru_resources/mapping-presets.json`; added `mcru_resources/__init__.py`, `setup.py` package data, and `tests/test_packaging.py`.
- **Decisions & Deviations:** Added the `setup.py` package-data declaration in this phase rather than Phase 2 because the Phase 1 archive-content test required it. This is within plan scope and implements the Phase 2 packaging requirement early. The preset blob hash was verified unchanged.
- **Next Phase Context:** The dedicated resource package is the canonical bundled source. Phase 2 wires all consumers to it and aligns parser validation.

---

## Phase 2: Packaged Presets and Registry-Driven Parser Choices
- **Status:** COMPLETED
- **Objective:** Make preset resources available in installed distributions and eliminate accepted no-op parser options.
- **Dependencies:** Phase 1 selects the resource representation.

### Tasks
- [x] Configure `setup.py` package data so wheel and source distributions include `mcru_resources/mapping-presets.json`.
- [x] Add a shared resource-loading/copying boundary using `importlib.resources` and replace the root `BUNDLED_MAPPING_FILE` assumptions in `config.py`, `cli.py`, and `tui/screens/config.py`.
- [x] Preserve one-time seeding of user presets and the existing reset behavior; keep external `MCRU_MAPPING_FILE` handling distinct from bundled defaults.
- [x] Update `tests/test_tui/test_config_screen.py` to inject or patch the shared resource boundary rather than patching `BUNDLED_MAPPING_FILE`.
- [x] Replace duplicated parser `click.Choice` lists in `cli.py` with choices from `registry.list_parsers()` or an equivalent single source of truth.
- [x] Reject unknown parser names loaded from existing profiles with a clear validation error before file mutation; retain the registered built-in parser behavior.
- [x] Add tests for the exact set of supported CLI parser choices, unknown persisted parser errors, preset seeding/reset, and TUI reading of the bundled preset resource.

### Verification & Acceptance Criteria
*All criteria must pass before advancing to the handoff report.*
- [x] **Automated Checks:** `python -m pytest tests/test_packaging.py tests/test_profiles.py tests/test_tui/test_config_screen.py -q`.
- [x] **Functional Assertions:** CLI parser options exactly match the registry, including `strip_trailing_whitespace`, and exclude unsupported `lowercase_names` unless it is genuinely implemented and registered.
- [x] **Functional Assertions:** Unknown stored parser values fail visibly before sync mutations; valid stored parsers still run in order.
- [x] **Functional Assertions:** Config initialization, CLI reset, and TUI preset viewing can all read the bundled resource from the selected package layout.

### Plan Compliance Checklist
*Verify each item against the actual diff before claiming this phase complete. Do not mark the phase COMPLETED if any item fails.*
- [x] **Required Files:** `setup.py`, `config.py`, `cli.py`, `registry.py` only if validation needs a registry API, `tui/screens/config.py`, and the focused tests named above.
- [x] **Required Files:** `setup.py`, `config.py`, `cli.py`, `registry.py` only if validation needs a registry API, `tui/screens/config.py`, `tests/test_packaging.py`, `tests/test_profiles.py`, and `tests/test_tui/test_config_screen.py`.
- [x] **Boundaries:** Keep module entry points and parser transforms unchanged; do not overwrite user preset files on package upgrade or introduce an unrelated config migration.
- [x] **Legacy Code Removed:** Remove duplicated hard-coded parser choices, the no-op `lowercase_names` choice, and root-file-only resource assumptions.
- [x] **Acceptance Checks:** Run the focused tests and verify every preset consumer and parser entry point.

### Phase 2 Handoff & Verification Report
- **Compliance Check:** PASSED
- **Verification Result:** PASSED
- **Execution Proof / Logs:** `python -m pytest tests/test_packaging.py tests/test_profiles.py tests/test_tui/test_config_screen.py -q` — 64 passed.
- **Artifacts Created/Modified:** `config.py`, `cli.py`, `registry.py`, `syncer.py`, `tui/screens/config.py`, `tests/test_profiles.py`, `tests/test_tui/test_config_screen.py`, and `docs/architecture.md`.
- **Decisions & Deviations:** Kept flat application modules and entry points. Config initialization, CLI resets, and TUI preset access share `read_bundled_mapping_presets()`; persisted unknown parsers fail before sync mutations. No user preset is overwritten during initialization.
- **Next Phase Context:** Resource consumers and parser validation are aligned. Phase 3 verifies built artifacts and an install independent of the checkout.

---

## Phase 3: Installed-Artifact Verification
- **Status:** COMPLETED
- **Objective:** Prove that packaged installs work independently of the repository checkout and pass the full regression suite.
- **Dependencies:** Phases 1 and 2.

### Tasks
- [x] Build a wheel and source distribution into temporary directories; inspect the artifacts for `mcru_resources/mapping-presets.json` and required Python modules.
- [x] Install the wheel into a temporary target and run a smoke test that initializes isolated config, loads the default preset, and displays CLI parser choices without importing files from the repository checkout.
- [x] Run focused packaging/config/parser tests and the full test suite.
- [x] Review generated metadata only as build output; do not commit generated `build/` or egg-info changes unless a separately required release policy says otherwise.

### Verification & Acceptance Criteria
*All criteria must pass before advancing to the handoff report.*
- [x] **Automated Checks:** `python -m pytest tests/test_packaging.py tests/test_profiles.py tests/test_tui/test_config_screen.py -q` and `python -m pytest -q`.
- [x] **Functional Assertions:** A clean wheel install can seed and read the default presets without the source checkout present.
- [x] **Functional Assertions:** Existing editable-install, CLI, TUI config, mapping, and parser tests pass.

### Plan Compliance Checklist
*Verify each item against the actual diff before claiming this phase complete. Do not mark the phase COMPLETED if any item fails.*
- [x] **Required Files:** Distribution metadata/resource files and `tests/test_packaging.py`; no source modules beyond the approved Phase 2 list.
- [x] **Required Files:** `docs/architecture.md`, distribution metadata/resource files, and `tests/test_packaging.py`; no source modules beyond the approved Phase 2 list.
- [x] **Boundaries:** Build artifacts stay temporary; no changes to user configuration or installed files outside the test environment.
- [x] **Legacy Code Removed:** No package consumer relies on a root JSON file that is absent from the built artifact; architecture documentation names the packaged resource location accurately.
- [x] **Acceptance Checks:** Run the package smoke test and full suite from the specified commands.

### Phase 3 Handoff & Verification Report
- **Compliance Check:** PASSED
- **Verification Result:** PASSED
- **Execution Proof / Logs:** Focused packaging/config/parser tests — 64 passed; `python -m pytest -q` — 279 passed. Wheel and sdist were built in temporary directories and inspected; a temporary wheel install seeded isolated config and displayed parser help outside the source checkout.
- **Artifacts Created/Modified:** `mcru_resources/mapping-presets.json`, distribution metadata generated only in temporary build directories, and `tests/test_packaging.py`. `docs/architecture.md` records the packaged resource location.
- **Decisions & Deviations:** No build or egg-info output was committed. `setuptools` and `wheel` were installed in the project virtual environment for packaging validation; dependency manifests were unchanged.
- **Next Phase Context:** No remaining phase. Artifact, installed-resource, parser, and full regression checks passed; commit `f45c15c`.

---