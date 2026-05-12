# TUI Screen Standards

This document is the source of truth for baseline behavior across all TUI screens.

## Purpose

Use this standard to keep screen behavior consistent as features evolve. Any page-level plan must reference this document and list explicit deviations.

## Required Baseline Features

1. Three-section layout model when applicable:
1. Section 1: primary list/progress/results content.
1. Section 2: details/options/context content.
1. Section 3: actions/help bar with visible hints for task actions only.
1. Status bar for transient feedback and non-blocking error messages.

2. Phase-aware behavior model:
1. `selection` phase for user input and target picking.
1. `running` phase for active work and cooperative cancellation.
1. `done` phase for summary/details and rerun/back behavior.

3. Error and outcome consistency:
1. Distinguish `success`, `partial`, `failed`, `cancelled` outcomes.
1. Do not lose post-step failures (report/changelog/finalization); surface them in details and status.
1. Avoid silent exception swallowing in completion callbacks.

## Keybinding Policy

Use this policy on all screens that support section navigation.

Global baseline (all screens):

1. `Ctrl+C` must quit the TUI immediately from any screen.
1. `q` should remain available as a standard quit/back key where applicable.

1. Primary section keys:
1. `Ctrl+1` -> focus section 1.
1. `Ctrl+2` -> focus section 2.
1. `Ctrl+3` -> focus section 3.

2. Required fallback keys (terminal compatibility):
1. `Alt+1`, `Alt+2`, `Alt+3`.
1. `F1`, `F2`, `F3`.

3. Safety rules:
1. Section focus keys are focus-only.
1. Section focus keys must not auto-trigger destructive actions like cancel or delete.
1. If a section is not focusable in current phase, show a status message and keep state unchanged.

4. Tab behavior:
1. Tab semantics must be explicit per phase.
1. If Tab is repurposed for domain actions, consume it consistently and document it in the action bar.

5. Action-bar display policy:
1. Do not display structural navigation controls in the Actions section.
1. Structural navigation controls include section-focus keys (`Ctrl+1/2/3`, `Alt+1/2/3`, `F1/F2/F3`) and directional traversal keys (`Up/Down`) when used for generic navigation.
1. Structural controls remain supported as bindings, but are considered implicit and should not appear in visible key-hint text.
1. Reserve visible key hints for task actions (for example: start, cancel, rerun, submit, delete, confirm).

## Threading and Callback Safety

1. Use a monotonic run token (or equivalent generation id) for async callbacks.
1. Reject stale progress/completion callbacks from older runs.
1. Avoid UI-thread blocking joins when worker completion still depends on UI callback delivery.
1. Cleanup actions must be idempotent so repeated cancel/back input does not corrupt state.

## Test Requirements (Minimum)

Every improved screen should include tests for:

1. Keybinding presence for primary and fallback section keys.
1. Global `Ctrl+C` quit binding works from the current screen.
1. Focus-only semantics for section keys.
1. Stale callback rejection after rerun/back transitions.
1. Partial-failure completion path still reaches stable `done` state.
1. Cancel/back/rerun loops do not leave stale worker references.

## Verification Matrix Template

Use this matrix in page plans and completion notes.

| Scenario | Expected | Automated | Manual |
|---|---|---|---|
| Success run path | Ends in `done`, status and details populated | Yes | Yes |
| Cancel path | Cooperative cancel, stable next run | Yes | Yes |
| Post-step failure | Partial outcome, warnings visible, UI responsive | Yes | Yes |
| Stale callback | Ignored, no UI mutation | Yes | Optional |
| Key fallback path | Alt/F fallback works if Ctrl is unavailable | Optional | Yes |

## Template For Future Page Improvement Plans

Use this structure for consistency:

1. Scope and goal.
1. Contracts/decisions (bindings, phase model, async safety).
1. Implementation phases with explicit gates.
1. Test plan (deterministic first, integration second).
1. Verification matrix (automated and manual).
1. Documentation updates and declared deviations from this standard.

## Deviation Policy

If a screen cannot follow a standard item, document:

1. The exact rule being deviated from.
1. Why deviation is required.
1. What alternative behavior replaces it.
1. How users discover the alternative in-screen and in docs.


**Note:** Screen-local keyboard extensions (beyond baseline policy) are documented in that screen's own reference doc (e.g., [docs/tui.md](tui.md) for Run screen), not in this global standards document. All new screens must follow baseline keybinding policy unless exceptional circumstances require an approved deviation documented in that screen's reference only.
