# Sync Input Safety Implementation Report

**Date:** 2026-09-28
**Status:** COMPLETE

## Goal and Scope

Implement the [sync input safety plan](../plans/sync-input-safety/sync-input-safety-plan.md) so syncs reject non-directory roots and resolved source/target paths that are identical or overlap. The core engine, CLI, and TUI now validate inputs before scanning, backup creation, worker startup, or mutation. Existing missing-target behavior is preserved for each entry point.

The work does not change mapping rules, normal add/update/remove behavior, transaction rollback semantics, or suite exit-status policy.

## Plan and Execution Order

The plan had three sequential phases; no parallel phase work was used.

1. **Core path contract — Complete.** Added shared validation in `MCRU` initialization and regression coverage for invalid roots, no-mutation failures, missing targets, and mapping mode.
2. **Entry-point feedback — Complete.** Added CLI preflight before backup creation and TUI preflight before worker startup. Invalid suite profiles are skipped with visible reasons.
3. **Regression gate and documentation — Complete.** Documented path constraints and entry-point missing-target policies, audited sync routes, and passed focused and full test gates.

## Coordination

- **Orchestrator:** GitHub Copilot.
- **Phase workers:** Separate general-purpose implementation agents handled Phases 1, 2, and 3 sequentially.
- **Model selection:** Default agent model selection was used without overrides. The orchestration interface did not expose model identifiers for independent confirmation.
- **Parallelism:** None.
- **Stop criteria:** No material blockers or unresolved decisions remained.

## Changes by Phase

### Phase 1: Core Path Contract

- Added `_validate_sync_roots` in `syncer.py`; it resolves both paths, requires an existing directory source, requires an existing target to be a directory, and rejects equal or ancestor/descendant roots.
- Called validation during `MCRU` initialization, before scanning or creating transaction state.
- Added tests for source files, target files, identical roots, both nesting directions, missing targets, and mapped-mode early rejection. Failure tests verify existing files remain intact and no transaction workspace is created.

### Phase 2: Entry-Point Feedback

- Updated profile, suite, and quick CLI paths to report invalid roots; profile and quick failures return nonzero exit statuses.
- Moved profile validation before backup creation. Suite profiles with invalid paths are skipped with visible reasons.
- Updated TUI profile and suite preflight to reject invalid or overlapping roots before backup creation or worker startup, while retaining its existing requirement that source and target paths exist.
- Added CLI and TUI regression coverage, including preservation of valid suite startup behavior.

### Phase 3: Regression Gate and Documentation

- Updated `docs/commands.md` and `docs/architecture.md` to describe directory requirements, resolved-root overlap rejection, and differing missing-target policies.
- Audited CLI, TUI, and core sync paths; no route bypassing the shared core guard was found.
- Updated the implementation plan handoffs and completion status.

## Validation Evidence

- Phase 1: `python -m pytest tests/test_syncer_progress.py tests/test_syncer_mapping.py -q` — **26 passed**, including invalid-root cases in both default and mapped modes.
- Phase 2: `python -m pytest tests/test_backup.py tests/test_profiles.py tests/test_tui/test_run_profile.py -q` — **96 passed**; rerun after a focused error-handling refinement also passed (**96 passed**).
- Phase 3 focused gate: `python -m pytest tests/test_syncer_progress.py tests/test_syncer_mapping.py tests/test_backup.py tests/test_profiles.py tests/test_tui/test_run_profile.py -q` — **122 passed**.
- Full suite: `python -m pytest -q` — **261 passed** in 17.92s.
- `git diff --check` — passed. Git emitted a CRLF/LF normalization advisory for `tests/test_syncer_mapping.py`.
- No generated `build/` or `mc_recipe_updater.egg-info/` artifacts were modified.

## Remaining Issues

None identified. The behavior change is intentional: overlapping source and target roots are rejected because mirroring between them is unsafe. Existing missing-target behavior remains caller-specific: the core engine and quick command allow a missing target, while profile/suite CLI paths and the TUI require it to exist.

## Final Status

All three phases are complete. Shared validation, user-facing preflight, regression coverage, and contract documentation are in place; focused and full automated test gates pass.
