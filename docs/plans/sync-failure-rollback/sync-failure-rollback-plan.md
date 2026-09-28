---
title: "Sync Failure Rollback - Implementation Plan"
status: COMPLETED
current_phase: 4 / 4
created: 2026-09-28
last_updated: 2026-09-28
---

# Overall Plan Completion Status

* **Final State:** COMPLETE
* **Total Phases Completed:** 4 / 4
* **Summary of Outcome:** All phases are complete. Caught live sync mutation failures now trigger rollback, accurate outcomes flow through CLI/TUI/reports and backup finalization, and documentation and full regression verification pass.

# Specification & Overview

### 1. Scope & Objective

- **Goal:** Make a live sync all-or-nothing when a filesystem mutation fails. Restore the target to its exact pre-run state rather than leave a mixture of completed and failed changes.
- **User decision:** Roll back the entire run when a copy or other sync mutation fails. Cancellation remains a separate behavior for now.
- **In-Scope:**
  - Cover both default and mapped syncs in `syncer.py`.
  - Cover failed file additions, updates, removals, and default-mode directory creation/removal.
  - Stop applying further mutations after the first mutation failure, then reverse mutations already applied by that run.
  - Make an individual copy safe against partial writes, and report whether whole-run rollback completed.
  - Surface accurate failure/rollback status through CLI profile, suite, and quick runs; TUI profile and suite runs; and generated reports.
  - Mark an associated pre-run user backup as failed when a sync mutation fails; do not rotate it as a successful run.
- **Out-of-Scope:**
  - Changing cancellation behavior. The current behavior intentionally leaves completed changes in place and reports that they were not rolled back.
  - Rolling back after report, changelog, backup-finalization, or other post-sync work fails.
  - Process termination, power loss, or automatic recovery after the application exits during a transaction.
  - Redesigning manual backup restore, backup formats, or unrelated sync behavior.
  - Generated `build/` and `mc_recipe_updater.egg-info/` artifacts.

### 2. Technical Constraints & Architecture

- **Current behavior and evidence:**
  - `MCRU._copy` in `syncer.py` creates the destination parent and calls `shutil.copy2` directly on the final target. The default and mapped apply loops catch operation exceptions, append them to `errors`, and continue applying later operations. A failed copy is not added to the successful `added` or `updated` lists.
  - The default sync also unlinks removed files and creates/removes directories directly. Whole-run rollback therefore needs to reverse more than file copies.
  - `BackupManager.create_backup` in `backup.py` stores a ZIP snapshot of files. `restore_backup` extracts those files over the target; it does not remove files added after the snapshot, so it is not an exact rollback primitive. User backups are configurable and cannot be the only rollback mechanism.
  - `cli.py` invokes the shared `MCRU` engine for profile, suite, and quick runs. Profile/suite CLI paths can finalize a backup as successful after `MCRU.run()` returns errors; quick reports use the default `success` outcome. `tui/screens/run_profile.py` also finalizes based on a raised exception, even though per-operation failures are returned in `results["errors"]`.
  - `reporter.py` already supports `success`, `partial`, `failed`, and `cancelled` outcomes. `tests/test_tui/test_run_profile.py::test_cancelled_profile_summary_includes_partial_counts_and_no_rollback` explicitly protects the current cancellation behavior. Existing focused sync tests are in `tests/test_syncer_progress.py` and `tests/test_syncer_mapping.py`; no direct copy-failure rollback coverage was found.
  - **Decision triage:** 6 auto-resolved decisions; 2 owner-selected decisions resolved (D0 and D1); 0 unresolved owner decisions; 0 discovery-needed decisions.
  - **Resolved decisions:**
    - **D0 - Rollback scope (owner-selected; resolved):** A caught mutation error rolls back the entire run in both modes. The user selected whole-run rollback, rather than protecting only the failed file. Confidence: high; this was explicitly selected.
    - **A1 - Stop after the first mutation error (auto-resolved):** Stop applying new mutations before rollback. Continuing to mutate after a failure adds risk and work without helping the selected all-or-nothing guarantee. Confidence: high; supported by D0 and the current per-operation loops in `syncer.py`.
    - **A2 - Stage each file copy before replacement (auto-resolved):** Write to a unique temporary path in the destination's parent, then replace the destination only after the copy completes; clean up the temporary path on failure. This avoids writing a partial copy over the live destination. The alternative, copying directly to the final path, is the current failure mode. Confidence: high; `tui/screens/config.py` already stages a same-directory temporary file and calls `Path.replace`.
    - **A3 - Reuse existing outcome categories (auto-resolved):** Report `failed` when rollback restores the original target and `partial` when rollback leaves residual changes. Keep the `success`/`partial`/`failed`/`cancelled` vocabulary; make result mutation lists represent net retained changes and keep both the original and rollback errors visible. This avoids adding a new `rolled_back` category and updating report filters without adding user-visible value. Confidence: medium-high; supported by `reporter.py` and `_classify_outcome` in `tui/screens/run_profile.py`.
    - **A4 - Preserve dry-run and cancellation semantics (auto-resolved):** Do not roll back on cancellation in this change; dry-run remains mutation-free. This follows the user's stated boundary and the existing cancellation assertion in `tests/test_tui/test_run_profile.py`. Confidence: high.
    - **A5 - Keep transaction recovery separate from user backups (auto-resolved):** Automatic rollback must work when persistent backups are disabled and must not call `BackupManager.restore_backup` as-is. Finalize an associated user backup as failed on a mutation error and do not rotate it as a successful run. The current restore overlays files rather than replacing the target, and the backup manager accepts only `success` or `failed`. Confidence: high; supported by `backup.py`.
    - **A6 - Extend existing focused test locations (auto-resolved):** Add core cases to `tests/test_syncer_progress.py` and `tests/test_syncer_mapping.py`, adapter/backup cases to `tests/test_tui/test_run_profile.py` and the existing `TestBackupCLIIntegration` section of `tests/test_backup.py`. Prefer these over a new test module because each touched behavior already has a focused test home. Confidence: high; supported by the existing test modules and CLI integration section.
  - **Owner decision D1 - Transaction architecture (resolved):** The user selected **A, a per-run reverse-operation journal with staged writes**, over a full snapshot, shadow target, or deferral. The decision changes the core transaction boundary and recovery implementation, so it was surfaced to and selected by the owner.
    - **Selected design:** Record pre-run state for touched files and directories, stage individual writes, and reverse mutations in order on failure. Create a short-lived transaction workspace on the target filesystem before the first target mutation; if it cannot be created, fail without changing the target. Remove it after success or complete rollback. Preserve it and report its recovery location if rollback is incomplete. Keep it separate from persistent user backups.
    - **Rationale:** This limits temporary storage to touched data, works independently of optional backups, and fits the shared `MCRU` apply boundary. The owner selected it after reviewing the alternatives. Confidence: high that it fits the requested behavior; filesystem-specific workspace and rollback behavior still require focused tests.
    - **Alternatives reviewed:** **B, full pre-run snapshot with exact restore**, would provide a whole-tree recovery source but requires full-target I/O/storage and safe exact replacement; the current ZIP restore is overlay-only. **C, shadow target and promote on success**, would leave the live target unchanged during application but duplicates the whole target and relies on platform-sensitive directory promotion. **D, defer**, would keep implementation blocked pending target constraints. These were not selected because their whole-target cost or promotion complexity is unnecessary for the chosen touched-data journal; no additional target constraint was supplied.
  - **Assumptions:** The guarantee is for caught runtime errors, not crashes, power loss, or concurrent external edits to the target. A successful rollback is `failed`; an incomplete rollback is `partial` with recovery details. The selected architecture must retain needed recovery material if rollback fails.
  - **Risks:** Rollback can itself fail because of permissions, disk exhaustion, locks, or a failing filesystem. Such a result must not claim that the target is restored; preserve recovery material and show the original error plus rollback failures. Both journal and snapshot approaches require temporary storage; a shadow tree additionally copies the entire target.

---

# Execution Plan & Handoffs

## Phase 1: Transaction Contract and Mechanism Decision

- **Status:** COMPLETED
- **Objective:** Validate the selected journal's operational contract and baseline before modifying the sync engine.
- **Dependencies:** D0, D1, and decisions A1-A6 are resolved. No owner decisions remain open.

### Tasks
- [x] Specify that the transaction workspace must be created on the target filesystem before any target mutation, and that workspace-creation failure must leave the target unchanged; Phase 2 will implement and test this guard.
- [x] Map add, update, remove, directory-create, and directory-remove operations to journal records and inverse operations, including parent directories created for copied files.
- [x] Specify cleanup behavior: remove the journal after success or complete rollback; preserve it and report its location after incomplete rollback.
- [x] Confirm the selected journal honors D0 and A1-A5 without relying on optional persistent backups or changing cancellation and dry-run behavior.
- [x] Keep the Phase 2 failure-injection matrix covering failed add/update copies, later failures after earlier add/update/remove/directory changes, mapped syncs, and rollback failures.

### Transaction Operation Contract

Create a unique transaction workspace on the target filesystem before the first target mutation. If preflight creation fails, return a sync error without changing the target. Keep transaction material separate from persistent user backups.

| Mutation | Journal before mutation | Inverse during rollback |
| --- | --- | --- |
| Add file | Record the destination path and any missing parent directories | Remove the added file, then remove transaction-created parents when empty |
| Update file | Preserve the existing file and its metadata in the transaction workspace | Restore the preserved file and metadata to the destination |
| Remove file | Preserve the removed file and its metadata in the transaction workspace | Restore it to the original path |
| Create directory (default mode) | Record each directory that did not exist before creation | Remove recorded directories in reverse order when empty |
| Remove empty directory (default mode) | Record its path and metadata before removal | Recreate the directory and restore its metadata |

Stage each copied file before replacing its destination. Stop at the first mutation failure and apply inverses in reverse order. Successful operations rolled back are not retained changes. Report the original mutation error and every rollback error; report `failed` if rollback is complete and `partial` if not. Remove the workspace after success or complete rollback. Preserve it and expose its recovery path after incomplete rollback. Cancellation remains outside this failure transaction, and dry-run creates no transaction workspace or target mutations.

Phase 2 failure-injection coverage must include a partial staged add/update copy, failure after prior add/update/remove/directory changes, mapped sync failure, transaction workspace creation failure, and rollback failure.

### Verification & Acceptance Criteria
*All criteria must pass before advancing to the handoff report.*
- [x] **Automated Checks:** Run `python -m pytest tests/test_syncer_progress.py tests/test_syncer_mapping.py tests/test_tui/test_run_profile.py tests/test_backup.py` as the focused baseline.
- [x] **Functional Assertions:** The selected journal design covers every in-scope mutation and specifies the user-visible result after successful and incomplete rollback.
- [x] **Functional Assertions:** The design fails before mutating the target if transaction workspace creation fails.
- [x] **Functional Assertions:** Cancellation remains a separate, non-rollback path, consistent with the existing TUI test.
- [x] **Functional Assertions:** The selected mechanism works when optional persistent backups are disabled and does not depend on the merge-only behavior of `BackupManager.restore_backup`.

### Plan Compliance Checklist
*Verify each item against the actual diff before claiming this phase complete. Do not mark the phase COMPLETED if any item fails.*
- [x] **Required Files:** This plan file only, updated with the resolved design and any justified deviations.
- [x] **Boundaries:** No implementation, tests, manual backup restore behavior, or generated build artifacts were modified during this decision phase.
- [x] **Legacy Code Removed:** None; this phase was design closure only.
- [x] **Acceptance Checks:** Focused baseline command ran and all contract decisions above are recorded.

### Phase 1 Handoff & Verification Report
*Filled out by the executing agent upon phase completion.*
- **Compliance Check:** PASS
- **Verification Result:** PASS — transaction contract recorded; focused baseline passed (57 tests).
- **Execution Proof / Logs:** `python -m pytest tests/test_syncer_progress.py tests/test_syncer_mapping.py tests/test_tui/test_run_profile.py tests/test_backup.py` — 57 passed in 3.14s.
- **Artifacts Created/Modified:** This plan file only.
- **Decisions & Deviations:** No new decisions. Recorded the journal operation/inverse matrix and the preflight, cleanup, and recovery-location contract.
- **Next Phase Context:** Implement the journal inside `syncer.py`; cover all listed file and default-mode directory mutations, preflight failure, partial staged writes, rollback failures, and unchanged cancellation/dry-run behavior.

---

## Phase 2: Transactional Core Sync

- **Status:** COMPLETED
- **Objective:** Implement exact rollback for filesystem mutation failures in both `MCRU` execution modes.
- **Dependencies:** Phase 1 must complete the journal operation matrix and preflight contract. D1 and the result contract are already resolved.

### Tasks
- [x] Add regression coverage in `tests/test_syncer_progress.py` and `tests/test_syncer_mapping.py` that injects copy failures, including a failure after partial data has been written to a staging destination.
- [x] Implement the selected transaction mechanism in `syncer.py` for default and mapped syncs; include additions, updates, removals, and default-mode directory mutations in the rollback journal.
- [x] Stage copied content before replacing the final destination so a failed copy cannot leave a truncated or partial target file.
- [x] Stop applying new mutations after the first mutation error; reverse prior mutations in reverse order and preserve the original failure plus any rollback errors.
- [x] Return results that distinguish a complete rollback from an incomplete rollback without counting reverted operations as committed changes.
- [x] Keep dry-run and `SyncCancelled` behavior unchanged.

### Verification & Acceptance Criteria
*All criteria must pass before advancing to the handoff report.*
- [x] **Automated Checks:** Run `python -m pytest tests/test_syncer_progress.py tests/test_syncer_mapping.py` — 17 passed.
- [x] **Functional Assertions:** After injected failures, tests verify rollback restores files/directories and removes retained additions when rollback succeeds.
- [x] **Functional Assertions:** Default and mapped sync failure cases pass; staged add/update failures do not corrupt the destination.
- [x] **Functional Assertions:** Rollback failure exposes retained changes and the recovery workspace.
- [x] **Functional Assertions:** Existing dry-run and cancellation tests pass with their current semantics.

### Plan Compliance Checklist
*Verify each item against the actual diff before claiming this phase complete. Do not mark the phase COMPLETED if any item fails.*
- [x] **Required Files:** `syncer.py`, `tests/test_syncer_progress.py`, and `tests/test_syncer_mapping.py`.
- [x] **Boundaries:** Transaction mechanics remain in the core sync boundary; `MCRU` is not coupled to TUI widgets or persistent backup registry state. Cancellation and manual restore semantics are unchanged.
- [x] **Legacy Code Removed:** Direct, non-transactional copy/apply behavior in default and mapped paths was replaced.
- [x] **Acceptance Checks:** Focused sync tests and the failure-injection assertions above ran.

### Phase 2 Handoff & Verification Report
*Filled out by the executing agent upon phase completion.*
- **Compliance Check:** PASS
- **Verification Result:** PASS — transactional default and mapped sync tests passed (17 tests); diagnostics found no errors; `git diff --check` found no whitespace errors.
- **Execution Proof / Logs:** `python -m pytest tests/test_syncer_progress.py tests/test_syncer_mapping.py` — 17 passed in 0.21s. `git diff --check` — passed (Git emitted a line-ending normalization notice for `tests/test_syncer_mapping.py`).
- **Artifacts Created/Modified:** `syncer.py`, `tests/test_syncer_progress.py`, and `tests/test_syncer_mapping.py`.
- **Decisions & Deviations:** Added explicit coverage for failed staged adds and reported the recovery path when workspace cleanup fails, closing two gaps found during orchestrator review.
- **Next Phase Context:** Consume `rollback_complete`, `recovery_path`, `rollback_errors`, and net retained mutation lists in CLI/TUI/report outcome handling; ensure backup finalization follows mutation failure status.

---

## Phase 3: CLI, TUI, and Report Outcomes

- **Status:** COMPLETED
- **Objective:** Make all run entry points report rollback accurately and keep backup metadata consistent with failed syncs.
- **Dependencies:** Phase 2 must expose reliable rollback status in the sync result contract.

### Tasks
- [x] Update profile, suite, and quick-run handling in `cli.py` so mutation errors produce a failed run outcome rather than a success-looking summary/report.
- [x] Update profile and suite completion handling in `tui/screens/run_profile.py` to show whether rollback completed or failed; keep cancellation messaging unchanged.
- [x] Pass accurate outcomes through `Reporter` and `SuiteReporter` in `reporter.py`. Report `failed` when rollback succeeds and `partial` when rollback cannot fully restore the target, using the existing outcome vocabulary.
- [x] Finalize pre-run backups as failed when the sync result contains a mutation error, and do not rotate them as successful runs. `restore_backup` is not used for transaction rollback.
- [x] Add CLI regression coverage in the existing `TestBackupCLIIntegration` section of `tests/test_backup.py`, and TUI regression coverage in `tests/test_tui/test_run_profile.py` for result classification, backup finalization, and visible rollback status.

### Verification & Acceptance Criteria
*All criteria must pass before advancing to the handoff report.*
- [x] **Automated Checks:** `python -m pytest tests/test_tui/test_run_profile.py tests/test_backup.py` — 54 passed.
- [x] **Functional Assertions:** CLI profile, suite, and quick runs cannot report success when `MCRU` returns mutation errors; failed backups are finalized as failed and not rotated.
- [x] **Functional Assertions:** TUI profile and suite runs distinguish successful rollback from incomplete rollback; cancellation continues to report that changes were not rolled back.
- [x] **Functional Assertions:** Reports consume net retained mutation lists and do not count reverted operations as committed target changes.

### Plan Compliance Checklist
*Verify each item against the actual diff before claiming this phase complete. Do not mark the phase COMPLETED if any item fails.*
- [x] **Required Files:** `cli.py`, `tui/screens/run_profile.py`, `reporter.py`, `tests/test_backup.py`, and `tests/test_tui/test_run_profile.py`.
- [x] **Boundaries:** No backup archive redesign, new outcome taxonomy, or unrelated CLI/TUI cleanup was introduced.
- [x] **Legacy Code Removed:** Success-only backup finalization and default-success report handling for mutation errors were replaced.
- [x] **Acceptance Checks:** CLI, TUI, reporter, and backup-finalization assertions ran.

### Phase 3 Handoff & Verification Report
*Filled out by the executing agent upon phase completion.*
- **Compliance Check:** PASS
- **Verification Result:** PASS — 54 focused CLI/TUI/backup tests passed; diagnostics found no errors; `git diff --check` found no whitespace errors.
- **Execution Proof / Logs:** `python -m pytest tests/test_tui/test_run_profile.py tests/test_backup.py` — 54 passed in 3.03s. `git diff --check` — passed (line-ending normalization notice for `tests/test_syncer_mapping.py`).
- **Artifacts Created/Modified:** `cli.py`, `tui/screens/run_profile.py`, `reporter.py`, `tests/test_backup.py`, and `tests/test_tui/test_run_profile.py`.
- **Decisions & Deviations:** No scope changes. Existing outcome categories are reused; cancellation behavior remains unchanged.
- **Next Phase Context:** Document automatic in-run rollback versus persistent backups and cancellation in `docs/backups.md`, then run the full test suite and final diff checks.

---

## Phase 4: Documentation and Full Regression Verification

- **Status:** COMPLETED
- **Objective:** Document the distinction between automatic sync rollback, user-managed backups, and cancellation, then validate the complete change.
- **Dependencies:** Phases 2 and 3 must be complete.

### Tasks
- [x] Update `docs/backups.md` to explain automatic rollback on caught sync mutation failures, its relationship to optional pre-run backups, rollback-failure reporting, and the unchanged cancellation behavior.
- [x] Review the final diff against the selected transaction contract; verify no `build/` or `mc_recipe_updater.egg-info/` artifacts were edited.
- [x] Run the full test suite and resolve only regressions caused by this change.

### Verification & Acceptance Criteria
*All criteria must pass before advancing to the handoff report.*
- [x] **Automated Checks:** `python -m pytest` — 243 passed; `git diff --check` — passed.
- [x] **Functional Assertions:** Documentation distinguishes exact in-run rollback from manual backup restore and cancellation.
- [x] **Functional Assertions:** Injected mutation failures verify unchanged targets after successful rollback and partial outcomes with recovery details after rollback failure.

### Plan Compliance Checklist
*Verify each item against the actual diff before claiming this phase complete. Do not mark the phase COMPLETED if any item fails.*
- [x] **Required Files:** `docs/backups.md`; final verification of files listed in Phases 2 and 3.
- [x] **Boundaries:** No unrelated documentation rewrite, backup format migration, generated artifact update, or application behavior expansion.
- [x] **Legacy Code Removed:** No unprotected sync mutation path or success-on-error reporting path remains in the covered run flows.
- [x] **Acceptance Checks:** Full test suite, diff check, and functional rollback assertions ran.

### Phase 4 Handoff & Verification Report
*Filled out by the executing agent upon phase completion.*
- **Compliance Check:** PASS
- **Verification Result:** PASS — all 243 tests passed; `git diff --check` passed; documentation diagnostics found no errors; no generated build or egg-info artifacts were modified.
- **Execution Proof / Logs:** `python -m pytest` — 243 passed in 18.26s. `git diff --check` — passed; Git emitted a line-ending normalization notice for `tests/test_syncer_mapping.py`.
- **Artifacts Created/Modified:** `docs/backups.md`; implementation report at `docs/reports/2026-09-28-sync-failure-rollback-implementation-report.md`.
- **Decisions & Deviations:** None. The selected journal architecture and existing outcome categories were retained.
- **Next Phase Context:** None; all four phases are complete.

---
