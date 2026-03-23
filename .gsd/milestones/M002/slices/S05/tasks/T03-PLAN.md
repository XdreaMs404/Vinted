---
estimated_steps: 4
estimated_files: 4
skills_used:
  - agent-browser
  - test
  - review
---

# T03: Document and prove the richer explorer-to-detail workflow

**Slice:** S05 — Listing Detail Narrative + Progressive Proof
**Milestone:** M002

## Description

Load `agent-browser`, `test`, and `review` before coding. S05 is only real if the richer detail route can be exercised as part of the explorer workflow, not merely asserted in unit tests. This task closes the slice with route/docs alignment, a written UAT path, and browser proof against the demo DB.

## Steps

1. Update README/detail-route guidance wherever the richer narrative/progressive-proof behavior changes the user-facing workflow.
2. Write `S05-UAT.md` with a repeatable explorer → detail → return test flow that checks narrative clarity, provenance labels, and progressive disclosure.
3. Keep automated route coverage aligned with the documented behavior and ensure no stale assertions still expect the old proof-first wording.
4. Run the local server against `data/vinted-radar-s04.db`, perform browser verification on the filtered explorer path, and capture the resulting evidence in the task and slice summaries.

## Must-Haves

- [x] The richer detail flow is documented in both README-facing usage notes and a slice-specific UAT file.
- [x] Browser proof exercises explorer context preservation, narrative-first reading, and progressive-proof access on the demo DB.
- [x] Automated tests remain green after the wording and structure changes.

## Verification

- `python -m pytest tests/test_dashboard.py tests/test_dashboard_cli.py`
- `python -m vinted_radar.cli dashboard --db data/vinted-radar-s04.db --host 127.0.0.1 --port 8784`

## Inputs

- `README.md` — current route/workflow documentation.
- `vinted_radar/dashboard.py` — final detail-route behavior to verify in the browser.
- `tests/test_dashboard.py` — route regression harness that should reflect the finished detail flow.
- `tests/test_dashboard_cli.py` — served-route messaging checks for the local dashboard command.

## Expected Output

- `README.md` — updated description of the richer listing-detail workflow.
- `.gsd/milestones/M002/slices/S05/S05-UAT.md` — repeatable UAT instructions for S05.
- `tests/test_dashboard.py` — final route assertions aligned with the narrative/progressive-proof detail behavior.
- `tests/test_dashboard_cli.py` — any CLI expectation updates required by the documented served routes.
