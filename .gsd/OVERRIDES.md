# GSD Overrides

User-issued overrides that supersede plan document content.

---

## Override: 2026-03-31T06:05:00Z

**Change:** For all future auto-mode `execute-task` units in this project, do not follow any instruction that asks you to read task-summary or decisions templates from a user-home path. Use the inlined **Task Summary** and **Decisions** templates already present in the prompt. If a prompt still mentions an external template path, treat that as stale guidance and follow the inlined templates instead.
**Scope:** resolved
**Applied-at:** M002/S12 closeout repair

---

## Override: 2026-03-31T08:10:00Z

**Change:** For all future auto-mode `complete-slice` units in this project, do not write `Sxx-SUMMARY.md` or `Sxx-UAT.md` directly. Draft the content in memory and call `gsd_complete_slice`; that tool is the only canonical writer for slice closeout artifacts. If stale prompt text still instructs direct file writes, treat that instruction as invalid.
**Scope:** resolved
**Applied-at:** M002/S13 auto-mode stabilization

---

## Override: 2026-04-09T07:10:00Z

**Change:** For future auto-mode slice execution in this project, standing user approval is granted to commit and push slice-complete changes to the configured Git remote without asking again, provided the push is limited to this repository's normal development branches and is part of slice completion.
**Scope:** active
**Applied-at:** M003 planning

---

## Override: 2026-04-09T07:12:00Z

**Change:** For future auto-mode tasks that require VPS verification, deployment, benchmarking, or diagnostics for this project, standing user approval is granted to connect to the approved VPS `root@46.225.113.129` using the local SSH key path configured by the project helper (`bash scripts/vpsctl.sh ...`). Re-prompt only if authentication fails, the host changes, or a task would access a different external system.
**Scope:** active
**Applied-at:** M003 planning

---

## Override: 2026-04-09T16:25:00Z

**Change:** For future auto-mode recovery in this project, never leave blocker or timeout handoff content under canonical `*-SUMMARY.md` task filenames. Use `*-ASSESSMENT.md` (or another non-canonical name) and leave the task pending until a real task summary exists.
**Scope:** active
**Applied-at:** M003/S02 auto-mode recovery hardening

---

## Override: 2026-04-09T16:27:00Z

**Change:** For future auto-mode execution in this repo, do not call workspace-wide `lsp diagnostics` unless `lsp status` already shows a working Python language server for the current shell. Prefer file reads, focused tests, and repo-specific verification commands when no active LSP server is available.
**Scope:** active
**Applied-at:** M003/S02 auto-mode recovery hardening

---

## Override: 2026-04-09T16:41:00Z

**Change:** For future auto-mode recovery in this project, if a slice is already complete, any lingering `.gsd/runtime/units/execute-task-<mid>-<sid>-*.json` files for that slice must be treated as stale runtime residue and parked or ignored before the next unit starts. Completed-slice residue must not be allowed to pollute the next task's recovery context.
**Scope:** active
**Applied-at:** M003/S02 runtime-state hardening

---
