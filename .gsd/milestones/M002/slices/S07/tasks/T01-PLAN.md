---
estimated_steps: 6
estimated_files: 6
skills_used:
  - debug-like-expert
  - test
---

# T01: Harden mounted large-corpus serving for realistic S07 acceptance

**Slice:** S07 — Live VPS End-to-End Acceptance Closure
**Milestone:** M002

## Description

The first mounted proof on `data/m001-closeout.db` exposed the real S07 problems: overview/explorer recomputed the same classified snapshot too many times, the mounted `/radar` CLI examples break under Git Bash/MSYS path conversion, and visible HTML leaked mojibake from historical category strings. This task removes those blockers before any honest closeout attempt.

## Steps

1. Materialize the classified overview snapshot once per repository connection / `now` key and reuse it across overview, explorer filters, comparisons, and page queries.
2. Pass one generated timestamp through each assembled dashboard/explorer payload so the repository cache can actually be reused within a single request.
3. Repair common UTF-8 mojibake in visible HTML only, keep JSON literal, and lift the mounted smoke verifier timeout to a realistic large-corpus default.
4. Update the README mounted-serving section with the `MSYS_NO_PATHCONV=1` workaround for Git Bash/MSYS.
5. Add regression coverage for repository snapshot reuse, generated-at reuse, and visible-text repair.
6. Re-measure realistic route timings on `data/m001-closeout.db`.

## Must-Haves

- [x] Overview/explorer stop recomputing the full classified snapshot for each subquery in the large-corpus mounted path.
- [x] The mounted shell remains truthful while the visible HTML no longer shows the obvious `VÃ...` category-path corruption found during first proof.

## Verification

- `python -m pytest -q`
- `python - <<'PY'
from vinted_radar.dashboard import build_dashboard_payload, build_explorer_payload, DashboardFilters, ExplorerFilters
from vinted_radar.repository import RadarRepository
from time import perf_counter
fixed_now = '2026-03-23T17:30:00+00:00'
with RadarRepository('data/m001-closeout.db') as repo:
    start=perf_counter(); build_dashboard_payload(repo, filters=DashboardFilters(), now=fixed_now); print('dashboard', round(perf_counter()-start,2))
with RadarRepository('data/m001-closeout.db') as repo:
    start=perf_counter(); build_explorer_payload(repo, filters=ExplorerFilters(), now=fixed_now); print('explorer', round(perf_counter()-start,2))
PY`

## Observability Impact

- Signals added/changed: request-time route latency on the realistic proof DB becomes inspectable without repeating the whole classified CTE for every page section.
- How a future agent inspects this: rerun the dashboard/explorer payload timing snippet on `data/m001-closeout.db`, then compare route timings and `verify_vps_serving.py` stability.
- Failure state exposed: the mounted smoke verifier now times out less aggressively, and visible mojibake regressions can be caught in HTML route/browser output.

## Inputs

- `vinted_radar/repository.py` — current SQL overview/explorer snapshot assembly with repeated classified CTE work.
- `vinted_radar/dashboard.py` — request-level payload assembly where one `generated_at` can be reused.
- `scripts/verify_vps_serving.py` — mounted smoke harness with a too-tight default timeout for the realistic proof DB.
- `README.md` — mounted serving examples that currently omit the Git Bash/MSYS path-conversion trap.
- `tests/test_repository.py` — repository-level regression coverage seam.
- `tests/test_dashboard.py` — payload/render regression coverage seam.

## Expected Output

- `vinted_radar/repository.py` — connection-local overview snapshot reuse for overview/explorer mounted pages.
- `vinted_radar/dashboard.py` — generated-at reuse across assembled payload calls.
- `scripts/verify_vps_serving.py` — realistic per-request timeout default for large mounted proof.
- `README.md` — Git Bash/MSYS mounted command guidance.
- `tests/test_repository.py` — snapshot-reuse regression test.
- `tests/test_dashboard.py` — generated-at reuse + mojibake repair regression tests.
