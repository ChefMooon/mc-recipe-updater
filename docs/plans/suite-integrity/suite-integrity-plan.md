---
title: "Suite Integrity - Implementation Plan"
status: COMPLETED
current_phase: 3 / 3
created: 2026-09-28
last_updated: 2026-09-28
---

# Overall Plan Completion Status

* **Final State:** COMPLETED
* **Total Phases Completed:** 3 / 3
* **Summary of Outcome:** All phases passed their focused checks and the full suite (271 passed). Suite membership, incomplete-run reporting, exit status, and user documentation are complete. Committed as `74305a0`.

# Specification & Overview

### 1. Scope & Objective
- **Goal:** Ensure deleted or skipped suite members cannot make an incomplete suite look successful to users or automation.
- **In-Scope:** Remove deleted profile references from suites; record missing or skipped members during CLI suite runs; calculate an incomplete outcome and nonzero exit status; show skipped names and reasons in terminal and saved suite reports.
- **Out-of-Scope:** Changing profile execution order, retrying skipped profiles, changing single-profile outcomes, or redesigning suite persistence formats.

### 2. Technical Constraints & Architecture
- `ConfigManager.remove_profile()` currently removes a profile from `profiles.json` but does not update suite references. `rename_profile()` already updates suite references, providing a local pattern for deletion cleanup.
- In `cli.py::run`, missing profiles, invalid paths, mapping errors, and some backup-abort paths are skipped. The current `runs` list contains only profiles that actually ran; `_suite_outcome()` sees only that list. A temporary `CliRunner` reproduction with one valid and one missing profile printed a warning but exited with code 0.
- `SuiteReporter` in `reporter.py` is also used by the TUI. Any skipped-member parameter or representation must remain backward compatible or update and test every caller, including `tui/screens/run_profile.py`.
- **Proposed outcome contract:** If all members run and succeed, outcome is `success`; if some members run but any configured member is skipped or fails, outcome is `partial`; if no member runs, outcome is `failed`. Incomplete outcomes return a nonzero CLI exit status and list skipped members with reasons.
- **Assumption:** Deleting a profile should remove it from every suite, matching the existing rename behavior. Explicitly test persistence of the updated profile and suite registries.
- **Risk:** Skipped members can arise at multiple branches. They must be recorded consistently without falsely counting an attempted-but-failed sync as merely skipped or changing backup-finalization semantics.

---

# Execution Plan & Handoffs

## Phase 1: Suite Membership Consistency
- **Status:** COMPLETED
- **Objective:** Keep suite definitions valid when a profile is deleted.
- **Dependencies:** None.

### Tasks
- [x] Update `ConfigManager.remove_profile()` in `config.py` to remove the deleted profile name from all suite profile lists and persist both registries.
- [x] Follow the reference-update style in `rename_profile()` and preserve suite order for remaining members.
- [x] Add tests in `tests/test_profiles.py` for deletion from one or more suites, deletion of an unreferenced profile, and persistence after reloading the manager.
- [x] Confirm save failures are reported through the existing CLI/TUI mutation boundaries; do not claim deletion succeeded if registry persistence fails.

### Verification & Acceptance Criteria
*All criteria must pass before advancing to the handoff report.*
- [x] **Automated Checks:** `python -m pytest tests/test_profiles.py -q`.
- [x] **Functional Assertions:** Removing a profile removes all of its suite references while preserving the order and contents of other profiles.
- [x] **Functional Assertions:** Removing a nonexistent profile continues to fail without altering either registry.
- [x] **Functional Assertions:** Reloading `ConfigManager` after a successful removal yields consistent profile and suite data.

### Plan Compliance Checklist
*Verify each item against the actual diff before claiming this phase complete. Do not mark the phase COMPLETED if any item fails.*
- [x] **Required Files:** `config.py` and `tests/test_profiles.py`.
- [x] **Boundaries:** Do not change suite schema, profile rename semantics, or profile CRUD behavior beyond keeping suite references consistent.
- [x] **Legacy Code Removed:** Replace profile deletion that leaves stale suite references.
- [x] **Acceptance Checks:** Run the focused profile tests and verify saved JSON state, not only in-memory state.

### Phase 1 Handoff & Verification Report
- **Compliance Check:** PASSED
- **Verification Result:** PASSED
- **Execution Proof / Logs:** `python -m pytest tests/test_profiles.py -q` — 37 passed; `git diff --check` — clean.
- **Artifacts Created/Modified:** `config.py`; `tests/test_profiles.py` — suite-reference cleanup, registry persistence/reload, nonexistent-profile, and save-failure coverage.
- **Decisions & Deviations:** No deviation. Remaining member order is preserved, and both registries are persisted.
- **Next Phase Context:** New profile deletions cannot create stale suite references. Legacy or manually edited missing members remain in scope for Phase 2.

---

## Phase 2: Incomplete Suite Outcomes
- **Status:** COMPLETED
- **Objective:** Surface every skipped suite member and classify incomplete suite runs as unsuccessful for automation.
- **Dependencies:** Phase 1 keeps future suite membership clean; legacy or manually edited suite files can still contain missing members.

### Tasks
- [x] Track each configured profile that is not run in `cli.py::run`, including missing profiles, invalid paths, mapping lookup errors, and user-aborted backup creation; retain a concise reason.
- [x] Update `_suite_outcome()` and the no-runs path so a partial run is `partial`, an all-skipped run is `failed`, and neither exits successfully.
- [x] Extend `SuiteReporter` in `reporter.py` to print and save skipped-member details and the final outcome. Use an optional additive input or update all CLI/TUI call sites deliberately.
- [x] Keep successfully run profiles and their existing result tuples intact; do not fabricate sync results for profiles that never ran.
- [x] Add CLI integration tests in `tests/test_backup.py` (or the existing `tests/test_profiles.py` CLI harness) for missing, invalid, mixed, and all-skipped suites, including exit codes and saved report content.
- [x] Verify existing TUI `SuiteReporter` behavior with `tests/test_tui/test_run_profile.py` and report tests in `tests/test_tui/test_reports_screen.py`.

### Verification & Acceptance Criteria
*All criteria must pass before advancing to the handoff report.*
- [x] **Automated Checks:** `python -m pytest tests/test_backup.py tests/test_profiles.py tests/test_tui/test_run_profile.py tests/test_tui/test_reports_screen.py -q`.
- [x] **Functional Assertions:** Mixed success and skip results in `partial`, emits skipped reasons, and returns exit code 1.
- [x] **Functional Assertions:** All-skipped suites report `failed` and return exit code 1; fully successful suites retain exit code 0.
- [x] **Functional Assertions:** Failed sync results remain distinct from skipped members and preserve existing backup finalization and report outcome behavior.
- [x] **Functional Assertions:** TUI callers that provide no skipped members retain their current successful and failed summary behavior.

### Plan Compliance Checklist
*Verify each item against the actual diff before claiming this phase complete. Do not mark the phase COMPLETED if any item fails.*
- [x] **Required Files:** `cli.py`, `reporter.py`, `tests/test_backup.py` or `tests/test_profiles.py`, `tests/test_tui/test_run_profile.py`, and `tests/test_tui/test_reports_screen.py`.
- [x] **Boundaries:** Do not change single-profile result classification, suite ordering, retry policy, backup storage format, or unrelated report filters.
- [x] **Legacy Code Removed:** Replace warning-only skip paths and the all-skipped success exit path with explicit incomplete outcomes.
- [x] **Acceptance Checks:** Run the focused command and verify terminal summary, persisted report, backup state, and process exit status.

### Phase 2 Handoff & Verification Report
- **Compliance Check:** PASSED
- **Verification Result:** PASSED
- **Execution Proof / Logs:** `python -m pytest tests/test_profiles.py tests/test_backup.py tests/test_tui/test_run_profile.py tests/test_tui/test_reports_screen.py -q` — 119 passed.
- **Artifacts Created/Modified:** `cli.py`, `reporter.py`, `tests/test_backup.py`, `tests/test_tui/test_run_profile.py`, and `tests/test_tui/test_reports_screen.py` — skip/failure tracking, report details, exit codes, and TUI compatibility coverage.
- **Decisions & Deviations:** Attempted sync exceptions are recorded as failures rather than skips; `SuiteReporter` receives optional additive member details. No scope deviation.
- **Next Phase Context:** CLI outcomes and reports now expose incomplete suite runs; Phase 3 documents and verifies this user contract.

---

## Phase 3: Full Regression and User Contract
- **Status:** COMPLETED
- **Objective:** Validate suite integrity across CLI and TUI and document the incomplete-suite exit contract.
- **Dependencies:** Phases 1 and 2.

### Tasks
- [x] Update `docs/suites.md` and the suite section of `docs/commands.md` to explain skipped members, outcome labels, and automation exit status.
- [x] Run focused suite/profile/report tests and the complete test suite.
- [x] Review the final diff for backward-compatible `SuiteReporter` use and absence of unrelated generated artifacts.

### Verification & Acceptance Criteria
*All criteria must pass before advancing to the handoff report.*
- [x] **Automated Checks:** `python -m pytest tests/test_profiles.py tests/test_backup.py tests/test_tui/test_run_profile.py tests/test_tui/test_reports_screen.py -q` and `python -m pytest -q`.
- [x] **Functional Assertions:** All configured members are either represented as run results or explicit skips; incomplete suites cannot be reported as success.
- [x] **Functional Assertions:** CLI docs match actual exit codes, report contents, and profile deletion behavior.

### Plan Compliance Checklist
*Verify each item against the actual diff before claiming this phase complete. Do not mark the phase COMPLETED if any item fails.*
- [x] **Required Files:** `docs/suites.md`, `docs/commands.md`, and the test modules listed in Phases 1 and 2.
- [x] **Boundaries:** No new suite schema or unrelated CLI/TUI restructuring; do not edit generated `build/` or egg-info output.
- [x] **Legacy Code Removed:** No user-facing suite path may silently skip a member and retain a success outcome.
- [x] **Acceptance Checks:** Run both commands above and verify the docs against observed command output.

### Phase 3 Handoff & Verification Report
- **Compliance Check:** PASSED
- **Verification Result:** PASSED
- **Execution Proof / Logs:** Focused suite/profile/report tests — 119 passed; `python -m pytest -q` — 271 passed; `git diff --check` — clean.
- **Artifacts Created/Modified:** `docs/suites.md` and `docs/commands.md` — documented deletion cleanup, skip/failure details, outcomes, and exit statuses.
- **Decisions & Deviations:** No suite schema or unrelated CLI/TUI restructuring; generated build and egg-info outputs were not committed.
- **Next Phase Context:** No remaining phase. Suite behavior and documentation are complete; commit `74305a0`.

---