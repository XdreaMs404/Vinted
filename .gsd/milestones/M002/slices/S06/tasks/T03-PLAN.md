---
estimated_steps: 4
estimated_files: 4
skills_used:
  - agent-browser
  - test
  - review
---

# T03: Document and re-prove degraded-mode behavior with seeded browser UAT

**Slice:** S06 — Acquisition Hardening + Degraded-Mode Visibility
**Milestone:** M002

## Description

Load `agent-browser`, `test`, and `review` before coding. S06 closes only when a future agent can recreate the degraded-mode proof path and confirm that the served product says the same thing as the persisted diagnostics.

## Steps

1. Update README for proxy-aware state refresh and degraded-mode inspection surfaces.
2. Define the seeded S06 demo/UAT flow that exercises degraded acquisition on overview, explorer, detail, runtime, `/api/runtime`, and `/health`.
3. Run the local dashboard against `data/vinted-radar-s06.db`, verify the routes in a browser, and capture explicit pass/fail evidence.
4. Write task and slice summaries with the real verification evidence, limitations, and follow-up intelligence.

## Must-Haves

- [ ] README documents how to inspect degraded acquisition truth from CLI and web surfaces.
- [ ] `S06-UAT.md` gives a repeatable seeded-browser flow for the slice.
- [ ] Task and slice summaries include the real commands/routes used for verification.

## Verification

- `python -m pytest tests/test_dashboard.py tests/test_dashboard_cli.py tests/test_runtime_cli.py`
- `python -m vinted_radar.cli dashboard --db data/vinted-radar-s06.db --host 127.0.0.1 --port 8786`

## Inputs

- `README.md` — operator and product usage documentation.
- `vinted_radar/dashboard.py` — final served degraded-mode behavior.
- `tests/test_dashboard.py` — route regression checks for the seeded browser proof.
- `tests/test_runtime_cli.py` — CLI/runtime output checks relevant to the documented workflow.

## Expected Output

- `README.md` — updated degraded-mode and proxy-aware operator guidance.
- `.gsd/milestones/M002/slices/S06/S06-UAT.md` — repeatable S06 browser UAT.
- `.gsd/milestones/M002/slices/S06/tasks/T03-SUMMARY.md` — final task summary with verification evidence.
- `.gsd/milestones/M002/slices/S06/S06-SUMMARY.md` — slice summary with integrated story and forward intelligence.
