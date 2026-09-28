# Three-Plan Implementation Report

**Date:** 2026-09-28
**Status:** COMPLETE

## Goal and Scope

Implemented the three requested plans in order: [suite integrity](../plans/suite-integrity/suite-integrity-plan.md),
[distribution and parser integrity](../plans/distribution-parser-integrity/distribution-parser-integrity-plan.md),
and [documentation cleanup](../plans/documentation-cleanup/documentation-cleanup-plan.md).
Each workstream was validated and committed before the next began.

## Execution Order and Outcomes

Workstreams ran sequentially; no implementation phases overlapped.

1. **Suite integrity — complete.** Profile deletion removes references from every suite
   while retaining member order and persisting both registries. CLI suite runs report skipped
   members and reasons, distinguish failures from skips, classify incomplete outcomes, and
   return nonzero status when not successful. `SuiteReporter` remains compatible with TUI
   callers. Suite and command documentation describe the behavior.
2. **Distribution and parser integrity — complete.** Moved the unchanged bundled presets into
   `mcru_resources`, declared the package data, and switched config, CLI, and TUI consumers to
   `importlib.resources`. CLI parser choices now come from the registry, and unknown persisted
   parser names fail before sync mutations. Updated the architecture guide.
3. **Documentation cleanup — complete.** Repaired the README onboarding and reset guidance,
   removed malformed and duplicate material, corrected the shipped TUI description, and fixed
   the pinned/unpinned backup rotation examples.

## Coordination

- **Orchestrator:** Primary session.
- **Implementation workers:** `suite-integrity`, `distribution-parser-integrity`, and
  `documentation-cleanup`, each assigned one plan and its ordered phases.
- **Model selection:** All worker calls used the default selection with no explicit model
  override. The task interface did not expose model identifiers for independent comparison.
- **Parallelism:** No implementation parallelism. The next plan started only after the
  preceding plan passed validation and was committed.

## Validation Evidence

### Suite Integrity

- `python -m pytest tests/test_profiles.py -q` — **37 passed**.
- `python -m pytest tests/test_profiles.py tests/test_backup.py tests/test_tui/test_run_profile.py tests/test_tui/test_reports_screen.py -q`
  — **119 passed**.
- `python -m pytest -q` — **271 passed** (independently rerun by the orchestrator).
- `git diff --check` — passed.

### Distribution and Parser Integrity

- `python -m pytest tests/test_packaging.py -q` — **1 passed**.
- `python -m pytest tests/test_packaging.py tests/test_profiles.py tests/test_tui/test_config_screen.py -q` — **64 passed**.
- `python -m pytest -q` — **279 passed** (independently rerun by the orchestrator).
- `git diff --check` — passed.
- Built wheel and source distribution in temporary directories. Both contained exactly one
  `mcru_resources/mapping-presets.json` resource and the required application modules. Installed
  the wheel to a temporary target and smoke-tested config initialization and parser help outside
  the repository checkout.
- Compared the moved preset's Git blob hash with the original `HEAD:mapping-presets.json`; the
  hashes matched.

### Documentation Cleanup

- `python cli.py --help`, `python cli.py run --help`, and `python cli.py quick --help` — all
  completed successfully; the parser options match the registered parsers.
- Independently checked relative Markdown links and the architecture parser anchor — all resolved.
- README and backup-guide code fence delimiters were balanced (16 and 58 delimiters, respectively).
- `git diff --check` — passed.

## Commits

| Plan | Commit |
|---|---|
| Suite integrity | `74305a0` — `fix(suites): report incomplete suite outcomes` |
| Distribution and parser integrity | `f45c15c` — `fix(packaging): bundle presets and validate parser choices` |
| Documentation cleanup | `6cdca99` — `docs: clean up onboarding and backup guidance` |

## Deviations and Remaining Items

- No implementation blockers or unresolved behavior decisions remain.
- The distribution plan added setuptools package-data configuration during its packaging-baseline
  phase so that the required regression test could pass; the change was already required by the
  plan's next phase.
- The three plan directories were untracked in the initial worktree. Their contents were left
  unchanged and excluded from implementation commits.
- No build or egg-info outputs were committed. A generated package bytecode file was removed after validation.
- The commits are local and have not been pushed.

## Final Status

All three plans are complete, validated, and committed in the requested order. The orchestration
report is recorded separately from the three plan commits.
