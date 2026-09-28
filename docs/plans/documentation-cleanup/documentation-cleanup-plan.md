---
title: "User Documentation Cleanup - Implementation Plan"
status: COMPLETED
current_phase: 2 / 2
created: 2026-09-28
last_updated: 2026-09-28
---

# Overall Plan Completion Status

* **Final State:** COMPLETED
* **Total Phases Completed:** 2 / 2
* **Summary of Outcome:** Both phases passed. README onboarding, reset guidance, and TUI wording are accurate; backup rotation examples match the unpinned limit. CLI help, Markdown links and anchors, code fences, and whitespace checks passed. Committed as `6cdca99`.

# Specification & Overview

### 1. Scope & Objective
- **Goal:** Repair broken onboarding documentation and remove editorial residue from the backup guide so users can follow the published workflows confidently.
- **In-Scope:** Restructure the affected README sections; correct its stale TUI status and stray text; fix the backup rotation example in `docs/backups.md`; verify links, code fences, and representative commands.
- **Out-of-Scope:** A general documentation rewrite, changes to application behavior, reworking the architecture guide, or documenting behavior that has not yet been implemented by the sync-safety, suite-integrity, and distribution/parser plans.

### 2. Technical Constraints & Architecture
- `README.md` contains a truncated reset instruction followed by pasted module notes and unbalanced code fences around the architecture summary. It also duplicates the command table, calls the TUI "in development", and includes the stray text "ReLI Commands".
- `docs/backups.md` explains the intended pinned-backup limit correctly but its Scenario 2 contains an editorial "Correction: Actually" note instead of a clean example.
- The README currently serves as the primary install and first-run guide. Keep existing command names, links, and user-data guarantees accurate; do not claim the TUI or parser capabilities beyond the shipped implementation.
- **Dependencies:** Final verification of any new parser-choice, suite-exit, or path-validation claims depends on the corresponding implementation plans. This plan may repair formatting and stale descriptions independently, but must not pre-document unresolved behavior.

---

# Execution Plan & Handoffs

## Phase 1: Repair Onboarding and Backup Guidance
- **Status:** COMPLETED
- **Objective:** Restore a coherent README flow and a concise, correct backup rotation example.
- **Dependencies:** None for structural repairs. TUI status should be checked against current entry points and screens before editing.

### Tasks
- [x] Repair the README from the "Where Data is Stored" section onward: restore the truncated reset instructions, remove pasted architecture fragments, balance fenced blocks, and retain one command overview.
- [x] Remove the stray "ReLI Commands" line and update the TUI status wording to reflect the current shipped feature state without overstating completeness.
- [x] Rewrite Scenario 2 in `docs/backups.md` as a direct example: pinned backups are excluded from the unpinned limit; show correct retained totals for both 10 and 12 unpinned backups.
- [x] Preserve useful installation, mapping, parser, backup, and architecture links; remove only duplicated or malformed content.

### Verification & Acceptance Criteria
*All criteria must pass before advancing to the handoff report.*
- [x] **Automated Checks:** `git diff --check`.
- [x] **Functional Assertions:** README code fences are balanced, headings form a coherent first-run path, no duplicate pasted architecture block remains, and all relative links resolve to existing files/headings.
- [x] **Functional Assertions:** Backup rotation examples agree with `backup.max_backups` semantics and contain no editorial correction text.
- [x] **Functional Assertions:** TUI wording matches the current installed entry points and available screens.

### Plan Compliance Checklist
*Verify each item against the actual diff before claiming this phase complete. Do not mark the phase COMPLETED if any item fails.*
- [x] **Required Files:** `README.md` and `docs/backups.md` only.
- [x] **Boundaries:** Do not rewrite unrelated guides, change commands, or describe features not yet implemented.
- [x] **Legacy Code Removed:** Remove the truncated reset text, pasted source/module dump, duplicate command table, stale development label, stray phrase, and editorial correction note.
- [x] **Acceptance Checks:** Run `git diff --check` and manually verify links, fences, and examples against current code.

### Phase 1 Handoff & Verification Report
- **Compliance Check:** PASSED
- **Verification Result:** PASSED
- **Execution Proof / Logs:** `git diff --check` — clean. README and backup-guide fences were balanced; all relative links and the architecture parser anchor resolved. Backup examples were checked against the non-pinned `backup.max_backups` rotation behavior.
- **Artifacts Created/Modified:** `README.md` — repaired onboarding/reset flow, removed malformed pasted content and duplicate command table, and corrected TUI status. `docs/backups.md` — replaced the editorial correction with retained totals for both scenarios.
- **Decisions & Deviations:** Kept the change limited to the two required documentation files and linked to detailed guides rather than duplicating them. No deviation.
- **Next Phase Context:** Structural repairs are complete. Phase 2 verifies command examples and feature claims against the implemented CLI and related plans.

---

## Phase 2: Cross-Check Published Usage
- **Status:** COMPLETED
- **Objective:** Verify the repaired onboarding text against actual CLI help and keep it aligned with the related behavior plans.
- **Dependencies:** Phase 1. Any newly documented path, suite, or parser guarantees depend on completion of the relevant behavior plans.

### Tasks
- [x] Compare README command examples with `python cli.py --help`, `python cli.py run --help`, and `python cli.py quick --help`.
- [x] Confirm each command and documentation link exists; verify parser examples against the registry-driven choices after the distribution/parser plan is implemented.
- [x] If documenting safe path constraints or incomplete-suite exit codes, verify them against the completed sync-input-safety and suite-integrity plans; otherwise leave those claims out of this change.
- [x] Review the final diff for accidental content loss and unrelated edits.

### Verification & Acceptance Criteria
*All criteria must pass before advancing to the handoff report.*
- [x] **Automated Checks:** `python cli.py --help`, `python cli.py run --help`, `python cli.py quick --help`, and `git diff --check`.
- [x] **Functional Assertions:** Every documented command and option appears in live CLI help; all links point to existing documentation; no unimplemented behavior is advertised.
- [x] **Functional Assertions:** The README remains concise enough to scan and links to detailed guides rather than duplicating their full content.

### Plan Compliance Checklist
*Verify each item against the actual diff before claiming this phase complete.*
- [x] **Required Files:** `README.md` and `docs/backups.md`; add another documentation file only if a verified cross-reference is necessary.
- [x] **Boundaries:** No application/test changes and no broad documentation rewrite.
- [x] **Legacy Code Removed:** No stale or unsupported command/feature claim remains in the edited sections.
- [x] **Acceptance Checks:** Run the command-help and whitespace checks and verify all documentation references manually.

### Phase 2 Handoff & Verification Report
- **Compliance Check:** PASSED
- **Verification Result:** PASSED
- **Execution Proof / Logs:** `python cli.py --help`, `python cli.py run --help`, and `python cli.py quick --help` — passed. Relative links and anchors resolved; README and backup-guide code fences were balanced (16 and 58 delimiters); `git diff --check` — clean.
- **Artifacts Created/Modified:** Only `README.md` and `docs/backups.md`; no application or test files changed.
- **Decisions & Deviations:** Parser examples match the registry-driven CLI options. The README does not add unverified suite-exit or path-validation guarantees. Backup rotation was checked against the implementation and backup tests. No deviation.
- **Next Phase Context:** No remaining phase. Published usage matches the CLI and implemented behavior; commit `6cdca99`.

---