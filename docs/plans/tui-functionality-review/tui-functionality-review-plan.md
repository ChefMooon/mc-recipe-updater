---
title: "TUI Screen Functionality Review - Implementation Plan"
status: COMPLETE
current_phase: 4 / 4
created: 2026-09-28
last_updated: 2026-09-28
---

# Overall Plan Completion Status

* **Final State:** COMPLETE
* **Total Phases Completed:** 4 / 4
* **Summary of Outcome:** All four phases are complete. Focused and full automated test gates pass, documentation is aligned, and the user confirmed the Windows Terminal manual smoke passed.

# Specification & Overview

### 1. Scope & Objective
- **Goal:** Make the seven TUI screens reliable, safe, consistent with the cross-screen contract, and adequately covered by behavior tests.
- **In-Scope:** Home, Profiles, Suites and Manage Profiles, Run, Reports, Backups, and Config; their directly-owned callbacks and tests; necessary validation of adjacent `config.py`, `syncer.py`, `backup.py`, and `registry.py` behavior; and TUI documentation updates.
- **Out-of-Scope:** New screens, broad layout/theme redesign, unrelated CLI features, and general sync/backup refactoring not required to correct a TUI finding. Do not weaken or rewrite the baseline standard to fit current behavior.

### 2. Technical Constraints & Architecture
- **Authoritative behavior:** Follow `docs/tui-screen-standards.md` for immediate global Ctrl+C quit, applicable `q` back/quit behavior, focus-only section bindings and fallbacks, explicit phase/outcome behavior, stale-callback rejection, non-blocking UI-thread behavior, and minimum tests. Follow `docs/tui.md` for user-visible bindings and `docs/plan/tui-screens.md` for page-specific design decisions and existing deviations.
- **Repository evidence:** `setup.py` declares Python >=3.10 and Textual; the repository uses pytest and Textual Pilot in `tests/test_tui/`. The app declares `q` and Ctrl+C bindings in `tui/app.py`, but page/modal probes found those actions are not consistently effective from child UI contexts.
- **Page-review findings (2026-09-28):**
  - Home: initial Input focus intercepts documented letter shortcuts; unknown commands disappear without feedback; the history hint, placeholder, and splash-cycle claims do not match demonstrated behavior; interaction coverage is thin.
  - Profiles: Ctrl+C is ineffective in modals; duplicate-name feedback arrives after the form closes; persistence errors can escape callbacks; Tab semantics and operation-level tests are missing.
  - Suites: Ctrl+C is ineffective in modals; reordering can lose the selected profile; persistence errors can escape; active-panel state can disagree with actual focus when a panel is empty; operation-level tests are missing.
  - Run: mounted phase replacement raises `DuplicateIds`, preventing sync and later transitions; non-directory source validation can permit target deletion; post-run backup failures can leave the screen running; Ctrl+C does not signal worker cancellation; cancellation can hide already-applied changes; partial outcomes and documented controls conflict with implementation.
  - Reports: invalid UTF-8 and prune I/O failures can escape; report reads/summaries are synchronous; the guide advertises columns and filters not implemented; workflow tests are thin.
  - Backups: prune confirmation can become stale before deletion; I/O failures are not consistently reported; rows omit the backup ID; screen workflow coverage is missing.
  - Config: malformed profile/suite JSON can prevent TUI startup and block recovery; wrong-shaped global settings can crash the screen; reset can delete before confirming defaults are available; the mapping override is ignored by the screen; invalid UTF-8 escapes the viewer; action coverage is thin.
- **Existing test evidence:** The focused Home, Profiles, Suites, Run, Backups, and Config modules were reported passing by page reviewers (25, 27, 25, 16, 7, and 7 tests respectively). Reports tests were inspected but not run. These counts are not a full-suite result and do not disprove the behavior findings; several defects were found with mounted Pilot probes or controlled failing dependencies.
- **Assumptions:** Keep existing screen ownership and Textual patterns. Add focused tests to existing page test modules where practical. For synchronous screens, document worker-only criteria as not applicable with a reason; retain their existing documented phase/threading deviations.
- **Resolved decisions:**
  1. Home command history and splash cycling are deferred; correct hints/docs to describe actual list navigation and static splash behavior.
  2. Reports will implement the advertised count columns and date-range/result-type filters.
  3. Run will support both a clickable Start button and the Space shortcut.
  4. Cancellation will preserve and display completed-operation partial results with a `cancelled` outcome and explicit no-rollback warning. `SyncCancelled` will carry accumulated results through the threaded callback. Rollback is out of scope and may be considered through a separate transaction/undo design.
  5. When `MCRU_MAPPING_FILE` points to an external override, Config will show the effective path and disable the reset action for that override.
  6. Ctrl+C on Run will signal cooperative cancellation and close the TUI immediately without joining the worker on the UI thread. This guarantees prompt UI exit, not immediate process termination: the existing non-daemon worker may remain until its current filesystem operation returns and it observes cancellation. This is preferred over daemonizing or abandoning an in-flight mutation.
  7. Run will continue requiring both source and target to exist as directories. `MCRU` can treat a missing target as empty and create parents during copy, but the current TUI explicitly rejects a missing target; retaining that behavior is the smallest compatibility-preserving choice. File paths must be rejected before mutation.
  8. Suite workers will capture their cancellation event per run, rather than consulting mutable screen state. Completed profile results will be recorded before backup/report/changelog finalization so post-step failures cannot erase them.
  9. Config recovery will include the startup construction boundary (`tui/app.py` and, if needed, `tui/main.py`), because `ConfigManager` loads JSON before any screen mounts. The recovery path must preserve malformed source files and remain reachable before normal screen navigation.
  10. Reports will read and summarize report contents in a Textual worker and reject stale results using a selection-generation check. This avoids blocking the event loop while retaining full-report support.
  11. The Phase 1 mapping-cancellation gate will include `tests/test_syncer_mapping.py`; backup tests remain in scope because backup finalization is part of Run completion.
  12. Home history and splash cycling are already deferred in decision 1; Phase 2 will align hints and docs without reopening that decision.
- **Decision-closure triage (2026-09-28):** 8 auto-resolved; 1 owner-selected; 0 unresolved owner decisions; 0 decisions requiring further discovery.

| ID | Options reviewed | Resolution and rationale | Confidence / evidence |
|---|---|---|---|
| A1 Ctrl+C | Abruptly terminate the worker/process; or signal cancellation and close the UI without joining. | Signal then close the UI; make no immediate process-termination promise. This preserves the global immediate-quit UI contract without abandoning an in-flight filesystem operation. | High. `docs/tui-screen-standards.md` requires immediate quit; `ThreadedSyncer` uses a non-daemon thread and cooperative cancellation. |
| A2 Path preflight | Allow a missing target as core `MCRU` does; or preserve the Run screen's current requirement that both paths exist. | Require source and target to exist and be directories. This is behavior-preserving and prevents file paths from being treated as sync roots. | High. `_prepare_profile_config` currently rejects missing paths; `MCRU` scans recursively and copy creates target parents. |
| A3 Suite cancellation | Read a mutable screen-level event; or capture an event for each run. | Capture per-run state so an older worker cannot observe a newer run's cancellation request. | High. `_run_suite_worker` currently consults `self._suite_cancel_event`. |
| A4 Suite results | Append results after post-steps; or record sync results before post-step finalization. | Record results first, then report backup/report/changelog failures as warnings. This prevents completed mutations disappearing from the summary. | High. Suite backup finalization currently precedes `runs.append`. |
| A5 Startup recovery | Recover only from a mounted Config screen; or include app/config construction. | Include the startup boundary and preserve malformed files; a screen-only route cannot run if construction fails first. | High. `MCRecipeApp` constructs `ConfigManager`, whose constructor parses profiles and suites before mounting a screen. |
| A6 Report responsiveness | Keep synchronous reads; impose a content-size limit; or move reads to a worker. | Use a worker with a selection-generation check, preserving full-report access without blocking or displaying stale results. | Medium-high. Current report detail reads are synchronous; Textual is already used for threaded TUI work; no size limit is specified. |
| A7 Mapping test gate | Omit mapping tests from the focused command; or run them with cancellation tests. | Include `tests/test_syncer_mapping.py` because mapping cancellation is an explicit acceptance case. | High. The plan requires mapping-path cancellation coverage and the test module exists. |
| A8 Home dependency | Reopen Home history/animation scope in Phase 2; or implement the already-resolved deferral. | Keep history and cycling deferred; make hints/docs truthful without reopening scope. | High. Resolved decision 1 already selects this behavior. |
| A9 Report outcome persistence (owner-selected) | A: persist outcomes for new reports and classify legacy as unknown; B: persist outcomes and best-effort infer legacy; C: derive outcomes at read time without writing metadata; D: persist outcomes and omit legacy from filtered results. | Selected A. Write an explicit outcome field to newly generated report files; keep legacy reports visible and classify them as `unknown`. Do not change which run paths create reports as part of this decision. | Owner-selected. Current report text has no reliable outcome field; best-effort inference can misclassify legacy failures/cancellations. |

- **Open decisions:**
  None. Report outcome persistence is resolved: new reports use explicit `success`, `partial`, `failed`, or `cancelled` metadata; reports without that metadata remain visible as `unknown` in the result-type filter. Existing report-generation behavior is unchanged.

---

# Execution Plan & Handoffs

## Phase 1: Run Lifecycle and File Safety
- **Status:** COMPLETED
- **Objective:** Make Run transitions work, reject unsafe path inputs, and reach a stable, truthful completion state for success, partial failure, and cancellation.
- **Dependencies:** Existing review findings and the resolved cancellation-summary contract in Specification & Overview.

### Tasks
- [x] Repair the mounted selection-to-running/results/back/rerun panel replacement in `tui/screens/run_profile.py`; preserve the current selection where a rerun or return-to-selection expects it.
- [x] Validate source and target with `is_dir()` before starting work in `_prepare_profile_config`; preserve the current TUI requirement that both directories exist, even though core `MCRU` can create a missing target. Prove that a source file, target file, or missing path cannot remove or overwrite target files.
- [x] Make post-run backup finalization/rotation failures visible as post-step warnings while still reaching `done` with the completed sync results. Do not swallow completion exceptions or report an unqualified success.
- [x] Make Ctrl+C signal cooperative cancellation and close the TUI immediately without a UI-thread join. Do not promise immediate process termination while the non-daemon worker is in a filesystem operation; make worker callbacks safe after app shutdown, cleanup idempotent, and retain run-token checks on progress and completion callbacks.
- [x] Carry accumulated completed-operation results on `SyncCancelled`, propagate them through `ThreadedSyncer` and suite completion, and display partial counts/details with a `cancelled` outcome plus an explicit warning that completed changes are not rolled back. Capture the suite cancellation event per worker run and preserve each completed profile's results before backup/report/changelog finalization.
- [x] Distinguish `success`, `partial`, `failed`, and `cancelled`, including suite skips, operation errors, and post-run warnings; do not label a cancelled run as successful or imply rollback.
- [x] Add tests for cancellation after at least one mutation in default and mapping sync paths, including partial-result propagation through `ThreadedSyncer` and suite runs; add mounted Textual Pilot tests for real phase transitions, rerun/back, actual Ctrl+C dispatch, path preflight, post-step failures, stale callback rejection, per-run suite cancellation events, and repeated cancel/back/rerun cleanup.

### Verification & Acceptance Criteria
*All criteria must pass before advancing to the handoff report.*
- [x] **Automated Checks:** `python -m pytest tests/test_tui/test_run_profile.py -q` (28 passed) and `python -m pytest tests/test_syncer_progress.py tests/test_syncer_mapping.py tests/test_backup.py -q` (24 passed).
- [x] **Functional Assertions:** A mounted run reaches running and done without `DuplicateIds`; rerun/back returns to a stable selection state; source/target files and missing paths fail before target mutation; finalization errors retain results and show a warning; cancellation carries completed operations into the summary and states that no rollback occurred; stale callbacks do not mutate a newer run; Ctrl+C closes the UI promptly, signals cleanup, and does not block the event loop while worker cleanup proceeds separately.

### Plan Compliance Checklist
- [ ] **Required Files:** `syncer.py`, `tui/screens/run_profile.py`, `tui/utils.py`, `tests/test_syncer_progress.py`, `tests/test_syncer_mapping.py`, `tests/test_tui/test_run_profile.py`; touch `backup.py` or `tests/test_backup.py` only as required by the verified backup finalization contract.
- [ ] **Boundaries:** No transactional rollback implementation, unrelated sync algorithm, CLI, or UI redesign; report outcome persistence is owned by Phase 3; no blocking worker join on the Textual event loop; no claim that Ctrl+C immediately terminates an active filesystem operation or rolls back mutations.
- [ ] **Legacy Code Removed:** Replace the unsafe duplicate-ID transition and quit-without-cancel path; remove any completion path that leaves the UI in `running` after a post-step failure or discards accumulated cancellation results. No module deletion is planned.
- [ ] **Acceptance Checks:** Run both focused commands above and verify every functional assertion against the resulting tests/output.

### Phase 1 Handoff & Verification Report
- **Compliance Check:** PASS
- **Verification Result:** PASS
- **Execution Proof / Logs:** `python -m pytest tests/test_tui/test_run_profile.py -q` (28 passed); `python -m pytest tests/test_syncer_progress.py tests/test_syncer_mapping.py tests/test_backup.py -q` (24 passed); `python -m pytest tests/test_backup.py -q` (16 passed after fixture isolation correction).
- **Artifacts Created/Modified:** `syncer.py`, `tui/screens/run_profile.py`, `tui/utils.py`, `tests/test_syncer_progress.py`, `tests/test_syncer_mapping.py`, `tests/test_tui/test_run_profile.py`, `tests/test_backup.py`.
- **Decisions & Deviations:** Ctrl+C signals cooperative cancellation and closes the UI without joining; a non-daemon worker may remain until its current filesystem operation returns. Run continues to require source and target directories. Corrected backup test fixture path resolution and second-resolution ID collisions so the required backup gate is isolated and deterministic.
- **Next Phase Context:** Run transitions, cancellation summaries, file preflight, and global quit behavior are covered by Phase 1 tests. Phase 2 should preserve the no-join Ctrl+C contract while testing modal/screen dispatch across Home, Profiles, and Suites.

## Phase 2: Home, Profiles, and Suites Workflows
- **Status:** COMPLETED
- **Objective:** Make command entry, CRUD, suite membership/reordering, modal behavior, focus state, and screen-level errors predictable and testable.
- **Dependencies:** Phase 1 establishes Run-specific quit/cancel and callback/error-handling behavior. Phase 2 must verify Ctrl+C from each non-Run screen and modal; Phase 4 repeats the cross-screen audit. Home history and splash cycling are already deferred by the resolved decision above.

### Tasks
- [x] Home: make documented shortcuts work with the default Input focus while preserving command entry; show feedback or retain unknown commands; align hints/placeholders with behavior. Do not implement command history or splash cycling in this plan; correct the visible hint and docs to match current behavior.
- [x] Profiles: make Ctrl+C work from add/edit/delete modals; keep duplicate-name validation actionable in the form; report expected persistence failures in status; specify Tab behavior and keep status/actions consistent with the standard.
- [x] Suites: make Ctrl+C work from form/confirmation modals; preserve the moved profile selection through reorder refreshes; update active-panel state only when focus succeeds; surface save/edit/reorder failures without claiming success.
- [x] Run controls: add a clickable Start button while preserving Space-to-start and Space-to-toggle behavior when a checkbox option has focus; test both input paths.
- [x] Add behavior-focused Pilot tests for Home routing/input/unknown commands, Profiles add/edit/delete/validation/failure outcomes, and Suites CRUD/membership/reorder/empty and missing profiles/focus/modals.
- [x] Verify section-key and fallback bindings remain focus-only and do not trigger task actions; use mounted Pilot dispatch to verify Ctrl+C from each screen and modal, not only binding declarations.

### Verification & Acceptance Criteria
- [x] **Automated Checks:** `python -m pytest tests/test_tui/test_screens.py tests/test_tui/test_profiles_screen.py tests/test_tui/test_run_profile.py -q` (113 passed).
- [x] **Functional Assertions:** Home shortcuts route from initial focus, unknown input receives feedback, and visible hints are truthful; profile and suite mutations retain stable selection and surface failures; consecutive suite reorders affect the same selected profile; empty-panel focus indicators match the actual focused widget; Run starts through both the button and Space without confusing checkbox toggling; Ctrl+C exits from modal and screen contexts.

### Plan Compliance Checklist
- [ ] **Required Files:** `tui/screens/home.py`, `tui/screens/profiles.py`, `tui/screens/suites.py`, `tui/screens/run_profile.py`, `tests/test_tui/test_screens.py`, `tests/test_tui/test_profiles_screen.py`, `tests/test_tui/test_run_profile.py`; `tui/app.py` only if a centralized binding change is needed.
- [ ] **Boundaries:** Keep screen-local responsibilities and existing modal conventions; implement the explicitly selected Reports/Run controls only, defer Home history/animation, and do not display structural traversal/section keys as task actions.
- [ ] **Legacy Code Removed:** Replace stale hints, unsafe modal bindings, selection-resetting reorder refresh, and focus markers that can desynchronize. No module deletion is planned.
- [ ] **Acceptance Checks:** Run both focused commands and verify real Pilot dispatch, callback outcomes, and focus behavior rather than checking binding declarations alone.

### Phase 2 Handoff & Verification Report
- **Compliance Check:** PASS
- **Verification Result:** PASS
- **Execution Proof / Logs:** `python -m pytest tests/test_tui/test_screens.py tests/test_tui/test_profiles_screen.py tests/test_tui/test_run_profile.py -q` (113 passed); changed Python files report no diagnostics; `git diff --check` passed.
- **Artifacts Created/Modified:** `tui/screens/home.py`, `tui/screens/profiles.py`, `tui/screens/suites.py`, `tui/screens/run_profile.py`, `tests/test_tui/test_screens.py`, `tests/test_tui/test_profiles_screen.py`, `tests/test_tui/test_run_profile.py`, `docs/tui.md`.
- **Decisions & Deviations:** Home history and splash cycling remain deferred; visible hints and Home/Profiles guidance were aligned with implemented behavior. Ctrl+C was verified through mounted Pilot screen/modal dispatch; section and fallback bindings remain focus-only.
- **Next Phase Context:** Use the established screen status/error patterns and preserve the Phase 1 Run contract. Phase 3 includes worker-backed Reports reads, backups preview integrity, and startup Config recovery.

## Phase 3: Reports, Backups, and Config Reliability
- **Status:** COMPLETED
- **Objective:** Prevent data-management screens from crashing or acting on stale/ambiguous targets, and make filesystem/configuration failures visible and recoverable.
- **Dependencies:** Phase 1 establishes shared error and outcome reporting. The mapping-override reset behavior and report outcome/legacy classification are already resolved above.

### Tasks
- [x] Reports: handle invalid UTF-8 and prune failures with readable status/viewer feedback; read and summarize report contents in a Textual worker and reject stale selection results; implement the advertised count columns and date-range/result-type filters. Write an explicit `success`, `partial`, `failed`, or `cancelled` outcome field in newly generated report files; show legacy reports with no outcome as `unknown`. Do not expand which run paths generate report files as part of this task.
- [x] Backups: ensure prune confirmation applies to the previewed candidate set or aborts when it changes; surface ZIP/filesystem failures in status; identify backup rows unambiguously.
- [x] Config startup: make malformed profile/suite JSON and invalid or wrong-shaped global settings recoverable without making the in-screen reset the only recovery route; include `ConfigManager` construction and the `MCRecipeApp`/TUI entry path, preserve malformed source files, and show a clear recoverable error path.
- [x] Config reset: preflight bundled defaults and stage replacement before removing existing data; report failure accurately and preserve current data when replacement is unavailable.
- [x] Config mapping behavior: display/view the effective mapping path; when `MCRU_MAPPING_FILE` points to an external override, disable reset for that override and explain the disabled action in-screen.
- [x] Add focused tests for corrupt/missing/large reports, prune errors/races, backup view/restore/pin/delete/prune confirmations and failures, malformed profile/suite JSON, invalid/wrong-shaped global settings, reset failure/cancel paths, and mapping override behavior.

### Verification & Acceptance Criteria
- [x] **Automated Checks:** `python -m pytest tests/test_tui/test_reports_screen.py tests/test_tui/test_backups_screen.py tests/test_tui/test_config_screen.py -q` (44 passed) and `python -m pytest tests/test_backup.py -q` (18 passed).
- [x] **Functional Assertions:** Corrupt data yields visible errors rather than escaped callback exceptions; date-range boundaries, all persisted result-type filters, `unknown` legacy classification, and count columns work as documented; stale report-worker results do not replace the currently selected report; prune never deletes a set different from the confirmed preview; reset failure preserves existing data and is not reported as success; the effective mapping path shown by Config matches the path used by configuration and external overrides cannot be reset through this action; report reads do not block the UI; malformed startup data remains recoverable without overwriting the malformed source.

### Plan Compliance Checklist
- [ ] **Required Files:** `tui/screens/reports.py`, `tui/screens/backups.py`, `tui/screens/config.py`, `tui/app.py`, `tui/main.py` if needed for recovery, `config.py`, `reporter.py`, `backup.py`, `tests/test_tui/test_reports_screen.py`, `tests/test_tui/test_backups_screen.py`, `tests/test_tui/test_config_screen.py`; add/modify `registry.py` or `tests/test_backup.py` only when the confirmed backup contract requires it.
- [ ] **Boundaries:** Avoid broad configuration/backup migrations; preserve user data on failed reset; add only the report outcome metadata required by the selected result-type filter; do not implement Home history/animation or transactional rollback in this plan.
- [ ] **Legacy Code Removed:** Replace delete-before-preflight reset ordering, silent broad exception suppression, and stale prune-preview execution where present. No module deletion is planned.
- [ ] **Acceptance Checks:** Run both focused commands and confirm injected filesystem/parse failures are asserted at the screen or startup boundary, not only at helper level.

### Phase 3 Handoff & Verification Report
- **Compliance Check:** PASS
- **Verification Result:** PASS
- **Execution Proof / Logs:** `python -m pytest tests/test_tui/test_reports_screen.py tests/test_tui/test_backups_screen.py tests/test_tui/test_config_screen.py -q` (44 passed); `python -m pytest tests/test_backup.py -q` (18 passed); diagnostics report no errors; `git diff --check` passed.
- **Artifacts Created/Modified:** `tui/screens/reports.py`, `tui/screens/backups.py`, `tui/screens/config.py`, `config.py`, `reporter.py`, `backup.py`, `tests/test_tui/test_reports_screen.py`, `tests/test_tui/test_backups_screen.py`, `tests/test_tui/test_config_screen.py`, plus related existing tests and Phase 1 Run integration.
- **Decisions & Deviations:** New reports carry explicit outcomes; legacy reports show `unknown`. External mapping overrides cannot be reset through Config. Report reads use background workers with stale-selection rejection. Backup tests now isolate module paths and make IDs unique per test run.
- **Next Phase Context:** Data screens have focused passing tests. Phase 4 must align docs to actual behavior, run the cross-screen and standards audits, execute all TUI and full repository tests, and attempt/record the Windows Terminal smoke pass.

## Phase 4: Cross-Screen Verification and Documentation
- **Status:** COMPLETED
- **Objective:** Verify the seven screens against the shared standards, resolve user-facing documentation drift, and leave a repeatable completion record.
- **Dependencies:** Phases 1-3 complete and material feature/documentation decisions recorded.

### Tasks
- [x] Update `docs/tui.md` and `docs/plan/tui-screens.md` to match implemented bindings, actions, outcomes, recovery behavior, report outcome/legacy semantics, and explicit feature-scope decisions, including deferred Home history/animation and the no-rollback cancellation contract. Clarify that Ctrl+C closes the TUI promptly while cooperative worker cleanup may continue until the current filesystem operation returns. Keep `docs/tui-screen-standards.md` as the baseline source of truth; document any approved screen-specific deviation in its screen reference.
- [x] Run a cross-screen keybinding audit: Ctrl+C from every screen/modal; `q` where applicable; Ctrl/Alt/F section-focus fallbacks on supported screens; focus-only semantics; explicit Tab behavior; visible action hints limited to task actions.
- [x] Run the standards verification matrix: success; cooperative cancellation and next-run stability; post-step failure/partial outcome; stale callback rejection; fallback keys. For synchronous screens, record a reasoned N/A for worker-only scenarios and retain their documented deviations.
- [x] Run all TUI tests and the complete repository test suite; fix only regressions within this plan's scope and record unrelated existing failures without broadening the work.
- [x] Perform a Windows Terminal manual smoke pass for key fallbacks, modal quit, screen navigation, and the Run cancel/quit path; record terminal/runtime constraints and final evidence in this plan's handoff. User confirmed all manual verification passed; per-key transcript was not provided.

### Verification & Acceptance Criteria
- [x] **Automated Checks:** `python -m pytest tests/test_tui -q` (170 passed) and `python -m pytest -q` (229 passed).
- [x] **Functional Assertions:** All seven screens have behavior-level coverage for their supported workflows; the verification matrix is complete; docs match actual controls and outcomes; no screen/modal blocks immediate Ctrl+C quit in mounted Pilot dispatch; Run cancellation reports accumulated partial results without promising rollback; applicable callbacks reject stale runs and reach a stable terminal phase after all outcomes.

### Plan Compliance Checklist
- [x] **Required Files:** `docs/tui.md`, `docs/plan/tui-screens.md`, and the existing TUI test modules touched in earlier phases; update `docs/tui-screen-standards.md` only if an explicit, approved baseline change is required.
- [x] **Boundaries:** No unapproved feature expansion or baseline-standard weakening; rollback remains deferred to a separate design; no unrelated documentation sweep; every deviation states the rule, reason, replacement behavior, and how users discover it.
- [x] **Legacy Code Removed:** Remove obsolete or contradictory key/help claims and superseded behavior paths; retain no duplicate advertised-but-unimplemented contract.
- [x] **Acceptance Checks:** Run both commands, complete the applicable verification matrix, and record manual checks and any unrelated failures before marking the phase complete.

### Phase 4 Handoff & Verification Report
- **Compliance Check:** PASS
- **Verification Result:** PASS
- **Execution Proof / Logs:** `python -m pytest tests/test_tui -q` (170 passed); `python -m pytest -q` (229 passed); targeted Phase 4 checks (87 passed); diagnostics report no errors; `git diff --check` passed. Live launch via `python -m tui.main` rendered Home and Run and opened a Profiles modal without starting a sync. The user confirmed the full Windows Terminal smoke passed for key fallbacks, modal quit, navigation, and Run cancel/quit; no per-key transcript was supplied.
- **Artifacts Created/Modified:** `docs/tui.md`, `docs/plan/tui-screens.md`, TUI screen implementations and tests from Phases 1-3, this implementation plan, and `docs/reports/2026-09-28-tui-functionality-review-implementation-report.md`.
- **Decisions & Deviations:** Home history and splash cycling remain deferred; no rollback is implemented; Ctrl+C closes Run promptly while cooperative worker cleanup may continue. Synchronous screens are N/A for worker-only lifecycle cases. The baseline `docs/tui-screen-standards.md` was not weakened. Subagents were invoked sequentially using the default model selection; the orchestration tool did not expose an explicit model identifier.
- **Next Phase Context:** None; all phases and acceptance checks are complete.
