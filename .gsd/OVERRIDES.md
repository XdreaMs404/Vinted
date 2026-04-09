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
