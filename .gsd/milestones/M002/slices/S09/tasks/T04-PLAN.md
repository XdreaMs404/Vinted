---
estimated_steps: 5
estimated_files: 10
skills_used:
  - code-optimizer
  - test
---

# T04: Run live Webshare-backed verification and close out S09 artifacts

**Slice:** S09 — High-Throughput Proxy Pool + Webshare Acquisition Operator Flow
**Milestone:** M002

## Description

Close the slice with real live evidence from the provided pool and leave a complete GSD record behind: roadmap, slice summary, task summaries, UAT, project knowledge, and the architectural decision that explains the new transport shape.

## Steps

1. Store the provided Webshare pool in the agreed local ignored path and run the new preflight command against it.
2. Run a real proxy-backed batch smoke against Vinted and inspect the persisted runtime/config truth.
3. Update milestone/project/knowledge/decision artifacts to capture the new operator and transport contract.
4. Write T01–T04 summaries plus S09 summary and UAT with real verification evidence.
5. Reassess any remaining limits or follow-ups discovered during live proof.

## Must-Haves

- [ ] The provided pool is exercised live through both preflight and a real Vinted batch cycle.
- [ ] S09 leaves complete milestone/slice/task/UAT documentation, not just code changes.
- [ ] The decision/knowledge/project registers capture the new proxy-pool contract and any real live caveats.

## Verification

- `python -m vinted_radar.cli batch --db data/vinted-radar-s09-live.db --page-limit 1 --max-leaf-categories 1 --state-refresh-limit 1 --request-delay 0.2 --timeout-seconds 10 --concurrency 8 --proxy-file data/proxies.txt`
- `python -m vinted_radar.cli runtime-status --db data/vinted-radar-s09-live.db --format json`

## Observability Impact

- Signals added/changed: live proxy-backed runtime config metadata and the new S09 artifact trail.
- How a future agent inspects this: S09 task/slice summaries, `runtime-status --format json`, and the persisted live smoke DB.
- Failure state exposed: live proxy-pool issues now leave preflight output, runtime config metadata, and slice-level notes instead of existing only in ephemeral terminal output.

## Inputs

- `.gsd/milestones/M002/M002-ROADMAP.md` — milestone slice list.
- `.gsd/PROJECT.md` — current project state.
- `.gsd/KNOWLEDGE.md` — append-only rules/patterns/lessons register.
- `.gsd/DECISIONS.md` — append-only decision register.
- `.gsd/milestones/M002/slices/S09/S09-PLAN.md` — slice contract.

## Expected Output

- `.gsd/milestones/M002/M002-ROADMAP.md` — S09 added and closed.
- `.gsd/milestones/M002/slices/S09/S09-UAT.md` — live/runtime UAT path.
- `.gsd/milestones/M002/slices/S09/S09-SUMMARY.md` — slice closeout summary.
- `.gsd/milestones/M002/slices/S09/tasks/T01-SUMMARY.md` — task summary.
- `.gsd/milestones/M002/slices/S09/tasks/T02-SUMMARY.md` — task summary.
- `.gsd/milestones/M002/slices/S09/tasks/T03-SUMMARY.md` — task summary.
- `.gsd/milestones/M002/slices/S09/tasks/T04-SUMMARY.md` — task summary.
- `.gsd/PROJECT.md` — updated current-state note.
- `.gsd/KNOWLEDGE.md` — appended proxy-pool pattern/lesson.
- `.gsd/DECISIONS.md` — appended S09 proxy-transport decision.
