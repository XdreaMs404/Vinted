---
estimated_steps: 5
estimated_files: 4
skills_used:
  - frontend-design
  - test
  - review
---

# T02: Surface acquisition health honestly across overview, explorer, detail, runtime, and health JSON

**Slice:** S06 — Acquisition Hardening + Degraded-Mode Visibility
**Milestone:** M002

## Description

Load `frontend-design`, `test`, and `review` before coding. T01 makes degraded acquisition measurable; this task makes it legible in the product. The same persisted truth needs to drive overview, explorer, detail, runtime, `/api/runtime`, and `/health` so the user sees one honesty contract, not page-local wording.

## Steps

1. Add repository/dashboard-level acquisition-health payload helpers built from recent scan failures and persisted probe degradation summaries.
2. Extend overview honesty notes and freshness/runtime summaries with healthy/partial/degraded acquisition status.
3. Add explorer-level caution copy and detail-level risk/provenance notes when the latest probe is degraded or anti-bot challenged.
4. Add runtime-page acquisition diagnostics and `/health` summary fields that match the product wording.
5. Expand repository/dashboard tests to lock in the new cross-surface honesty contract.

## Must-Haves

- [ ] Overview, explorer, detail, runtime, `/api/runtime`, and `/health` all expose the same persisted acquisition-health truth.
- [ ] Degraded or partial acquisition is described in broader-language copy, while raw diagnostics remain available in JSON.
- [ ] A latest degraded probe on listing detail becomes an explicit caution note, not a silent fallback to history.

## Verification

- `python -m pytest tests/test_overview_repository.py tests/test_dashboard.py tests/test_dashboard_cli.py`

## Observability Impact

- Signals added/changed: acquisition-health status, recent scan-failure list, degraded probe counts/reasons, health-route acquisition summary.
- How a future agent inspects this: `/api/runtime`, `/health`, overview/explorer/detail/runtime HTML, and repository/dashboard tests.
- Failure state exposed: degraded collection shows up as visible product warnings plus machine-readable diagnostics instead of only buried logs.

## Inputs

- `vinted_radar/repository.py` — overview/runtime contracts and freshness summary wiring.
- `vinted_radar/dashboard.py` — overview/explorer/detail/runtime payloads and HTML rendering.
- `tests/test_overview_repository.py` — overview truth/honesty regression harness.
- `tests/test_dashboard.py` — cross-route payload and HTML assertions.

## Expected Output

- `vinted_radar/repository.py` — acquisition-health contract available to overview/runtime consumers.
- `vinted_radar/dashboard.py` — degraded-mode copy and JSON/HTML surfacing across overview/explorer/detail/runtime/health.
- `tests/test_overview_repository.py` — acquisition-health assertions on overview data.
- `tests/test_dashboard.py` — route/API/HTML assertions for degraded-mode visibility.
