# T01 Assessment — auto-mode stall handoff

This is a recovery handoff, not a completed task summary.

## What happened

- Auto-mode dispatched `M003/S02/T01` and entered the task with stale carry-over verification noise from `complete-slice M003/S01`.
- The executor then issued several broad `read` calls and a workspace-level `lsp diagnostics` call.
- The `lsp` call never returned in the activity trace, and the unit hit the stalled-tool / idle-recovery path.
- Auto-mode then wrote a blocker placeholder under the canonical summary filename, which is unsafe because GSD reconciliation treats `*-SUMMARY.md` as completed work.

## Why this file exists

Project knowledge already states that incomplete recovery handoffs must live under a non-canonical filename such as `*-ASSESSMENT.md`. This file restores that rule for T01.

## Next safe action

- Treat `T01` as pending work.
- Do not infer completion from the removed placeholder summary.
- Resume from the real task plan at `.gsd/milestones/M003/slices/S02/tasks/T01-PLAN.md` after the LSP/tooling issue is addressed.
