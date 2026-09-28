---
title: "Sync Input Safety - Implementation Plan"
status: COMPLETE
current_phase: 3 / 3
created: 2026-09-28
last_updated: 2026-09-28
---

# Overall Plan Completion Status

* **Final State:** COMPLETE
* **Total Phases Completed:** 3 / 3
* **Summary of Outcome:** Core, CLI, and TUI sync-root validation is implemented. Contract documentation is updated and the focused and full regression gates pass.

# Specification & Overview

### 1. Scope & Objective
- **Goal:** Prevent a sync from treating a non-directory source as an empty tree or mutating overlapping source and target trees.
- **In-Scope:** Core validation in `syncer.py`; consistent user-facing preflight in the CLI and TUI; regression tests for source files, invalid target roots, identical roots, and nested source/target roots.
- **Out-of-Scope:** Changing normal add/update/remove behavior, transaction rollback semantics, mapping rules, missing-target policy for existing entry points, or symlink/junction support beyond safely resolving paths for comparison.

### 2. Technical Constraints & Architecture
- `MCRU.__init__` currently rejects a missing source but accepts any existing path. `_scan` uses recursive directory traversal, so a regular file can produce an empty source file set; the apply phase may then remove target files.
- The default and mapped sync paths share `MCRU` construction, so the core guard must run before scanning, transaction workspace creation, or target mutation. CLI entry points also perform existence-only checks; the TUI has its own run preflight.
- A temporary reproduction confirmed that `source = target/src` can remove the source file and its directory during a successful sync. Another confirmed that a regular file source can clear the target.
- **Proposed contract:** The source must be an existing directory. Reject source and target paths that resolve to the same location or where either is an ancestor of the other. If a target exists, it must be a directory. Preserve each caller's current missing-target behavior.
- **Assumptions:** Resolve paths before overlap checks and use platform-aware path comparisons. Verify Windows path and junction behavior during implementation; do not broaden this work into following arbitrary symlink trees.
- **Risk:** Overlap rejection is a behavior change for configurations that currently run but cannot safely produce a well-defined mirror. Error messages must identify the invalid relationship before any mutation.

---

# Execution Plan & Handoffs

## Phase 1: Core Path Contract
- **Status:** COMPLETED
- **Objective:** Validate sync roots inside the shared engine before any filesystem scan or mutation.
- **Dependencies:** None.

### Tasks
- [x] Add focused tests in `tests/test_syncer_progress.py` for a source file, identical roots, source nested under target, target nested under source, and an existing target that is a file.
- [x] Add or adapt mapping-mode coverage in `tests/test_syncer_mapping.py` to prove the shared guard runs before mapping traversal or target mutation.
- [x] Implement a small path-validation boundary in `syncer.py` and invoke it from `MCRU` initialization or `run()` before scanning or creating transaction state.
- [x] Resolve source and target paths consistently, including a target path that does not yet exist, and verify comparisons on Windows.
- [x] Return a clear validation error for each rejected input without changing source, target, or transaction artifacts.

### Verification & Acceptance Criteria
*All criteria must pass before advancing to the handoff report.*
- [x] **Automated Checks:** `python -m pytest tests/test_syncer_progress.py tests/test_syncer_mapping.py -q`.
- [x] **Functional Assertions:** A source file, an existing non-directory target, and equal/overlapping resolved roots fail before mutation in default and mapped modes.
- [x] **Functional Assertions:** Disjoint directory roots continue to sync; core behavior for a missing target remains unchanged.
- [x] **Functional Assertions:** Failure leaves every pre-existing source and target file intact and creates no `.mcru-transaction-*` workspace.

### Plan Compliance Checklist
*Verify each item against the actual diff before claiming this phase complete. Do not mark the phase COMPLETED if any item fails.*
- [x] **Required Files:** `syncer.py`, `tests/test_syncer_progress.py`, and `tests/test_syncer_mapping.py`.
- [x] **Boundaries:** Keep validation in the shared sync boundary; do not change mapping semantics, mutation ordering, rollback design, or missing-target policy.
- [x] **Legacy Code Removed:** Replace the existence-only source assumption in `MCRU`; do not leave a path that reaches `_scan` with a regular file source.
- [x] **Acceptance Checks:** Run the focused command and verify the no-mutation assertions against both sync modes.

### Phase 1 Handoff & Verification Report
- **Compliance Check:** PASS
- **Verification Result:** PASS — focused suite passed (26 tests); `git diff --check` passed.
- **Execution Proof / Logs:** `python -m pytest tests/test_syncer_progress.py tests/test_syncer_mapping.py -q` — 26 passed.
- **Artifacts Created/Modified:** `syncer.py`, `tests/test_syncer_progress.py`, `tests/test_syncer_mapping.py`.
- **Decisions & Deviations:** Validation runs in `MCRU` initialization and resolves roots before scanning or transaction creation. Missing-target behavior is preserved.
- **Next Phase Context:** CLI and TUI must surface the shared path contract before backup creation or worker startup.

---

## Phase 2: Entry-Point Feedback
- **Status:** COMPLETED
- **Objective:** Make CLI and TUI users receive the same actionable preflight error instead of a misleading empty-source sync or an uncaught low-level exception.
- **Dependencies:** Phase 1 defines and implements the core validation contract.

### Tasks
- [x] Audit the profile, suite, and quick command checks in `cli.py`; validate directory types and resolved overlap before creating backups where practical.
- [x] Keep the core guard authoritative so direct `MCRU` callers cannot bypass it; translate expected validation failures into a clear CLI error and nonzero exit status.
- [x] Review `_prepare_profile_config` and run startup in `tui/screens/run_profile.py`; preserve the established TUI requirement that configured source and target paths exist while rejecting files and overlap before starting a worker.
- [x] Add CLI regression coverage using the existing `CliRunner` integration tests in `tests/test_backup.py` or `tests/test_profiles.py`, and TUI coverage in `tests/test_tui/test_run_profile.py`.
- [x] Ensure suite processing marks an invalid profile as skipped with a visible reason; suite exit-status semantics remain owned by the suite-integrity plan.

### Verification & Acceptance Criteria
*All criteria must pass before advancing to the handoff report.*
- [x] **Automated Checks:** `python -m pytest tests/test_backup.py tests/test_profiles.py tests/test_tui/test_run_profile.py -q`.
- [x] **Functional Assertions:** CLI run and quick paths do not create a backup or begin sync mutations for rejected roots, and return a nonzero status with the invalid path identified.
- [x] **Functional Assertions:** TUI rejects unsafe roots before launching its worker and displays an actionable validation message.
- [x] **Functional Assertions:** Valid, disjoint directory paths preserve the existing profile, quick-run, suite, and TUI workflows.

### Plan Compliance Checklist
*Verify each item against the actual diff before claiming this phase complete. Do not mark the phase COMPLETED if any item fails.*
- [x] **Required Files:** `cli.py`, `tui/screens/run_profile.py`, `tests/test_backup.py` or `tests/test_profiles.py`, and `tests/test_tui/test_run_profile.py`.
- [x] **Boundaries:** Do not duplicate or weaken the core guard; do not redesign suite results, backups, or the TUI workflow beyond path preflight and user feedback.
- [x] **Legacy Code Removed:** Replace existence-only CLI checks where they permit regular files to proceed as sync roots.
- [x] **Acceptance Checks:** Run the focused command and verify both command output and process exit status for rejected paths.

### Phase 2 Handoff & Verification Report
- **Compliance Check:** PASS
- **Verification Result:** PASS — focused suite passed (96 tests), including rerun after error-handling refinement; `git diff --check` passed.
- **Execution Proof / Logs:** `python -m pytest tests/test_backup.py tests/test_profiles.py tests/test_tui/test_run_profile.py -q` — 96 passed.
- **Artifacts Created/Modified:** `cli.py`, `tui/screens/run_profile.py`, `tests/test_backup.py`, `tests/test_tui/test_run_profile.py`.
- **Decisions & Deviations:** CLI validates through the shared `MCRU` guard before backup creation. TUI also preserves its established requirement that both configured paths exist. Invalid suite profiles are skipped with a visible reason; suite exit-status semantics remain unchanged.
- **Next Phase Context:** Update path-contract documentation, audit all entry points, then run the focused and full test gates.

---

## Phase 3: Regression Gate and Contract Documentation
- **Status:** COMPLETED
- **Objective:** Verify path safety across the application and document the input constraints where users configure or run syncs.
- **Dependencies:** Phases 1 and 2.

### Tasks
- [x] Update the relevant path-validation descriptions in `docs/commands.md` and `docs/architecture.md` without changing unrelated documentation.
- [x] Run the focused sync, CLI, and TUI tests, then the full suite.
- [x] Review all entry points for an unsafe route that bypasses core validation; inspect the final diff for unrelated changes.

### Verification & Acceptance Criteria
*All criteria must pass before advancing to the handoff report.*
- [x] **Automated Checks:** `python -m pytest tests/test_syncer_progress.py tests/test_syncer_mapping.py tests/test_backup.py tests/test_profiles.py tests/test_tui/test_run_profile.py -q` and `python -m pytest -q`.
- [x] **Functional Assertions:** The complete suite passes; documentation accurately states directory and overlap constraints; all rejected paths fail before target mutation.
- [x] **Functional Assertions:** No source/target files or generated transaction workspaces are left altered by validation failures.

### Plan Compliance Checklist
*Verify each item against the actual diff before claiming this phase complete. Do not mark the phase COMPLETED if any item fails.*
- [x] **Required Files:** `docs/commands.md`, `docs/architecture.md`, and the focused test modules from Phases 1 and 2.
- [x] **Boundaries:** No broad sync refactor, transaction redesign, mapping rewrite, or changes to generated `build/` and `mc_recipe_updater.egg-info/` artifacts.
- [x] **Legacy Code Removed:** No entry point may proceed with a source file or overlapping resolved roots.
- [x] **Acceptance Checks:** Run both commands above and confirm the docs against CLI/TUI behavior.

### Phase 3 Handoff & Verification Report
- **Compliance Check:** PASS
- **Verification Result:** PASS — focused suite passed (122 tests), full suite passed (261 tests), and `git diff --check` passed.
- **Execution Proof / Logs:** `python -m pytest tests/test_syncer_progress.py tests/test_syncer_mapping.py tests/test_backup.py tests/test_profiles.py tests/test_tui/test_run_profile.py -q` — 122 passed; `python -m pytest -q` — 261 passed.
- **Artifacts Created/Modified:** `docs/commands.md`, `docs/architecture.md`.
- **Decisions & Deviations:** Documented the existing target-existence policies separately: profile/suite CLI and TUI require existing targets; quick runs and the core engine permit a missing target.
- **Next Phase Context:** No further phases.

---