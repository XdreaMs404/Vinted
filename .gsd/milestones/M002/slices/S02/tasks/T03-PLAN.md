---
estimated_steps: 4
estimated_files: 5
skills_used:
  - frontend-design
  - make-interfaces-feel-better
  - accessibility
  - agent-browser
  - best-practices
  - test
  - review
---

# T03: Expose runtime truth through `/runtime`, `/api/runtime`, and the overview shell

**Slice:** S02 — Runtime Truth + Pause/Resume Surface
**Milestone:** M002

## Description

Load `frontend-design`, `make-interfaces-feel-better`, `accessibility`, `agent-browser`, `test`, and `review` before coding. This task turns the controller contract into the user-facing runtime product surface. Today the dashboard only has `/api/runtime` plus a small freshness mention on `/`; S02 needs a dedicated French-first `/runtime` page, richer runtime JSON, and overview copy that reads controller truth instead of the last cycle row.

## Steps

1. Add a repository-backed runtime payload builder and `render_runtime_html()` flow in `vinted_radar/dashboard.py`, then wire a `/runtime` route that exposes status, phase, elapsed pause, next resume, last error, latest cycle outcome, and recent failure history in French-first copy.
2. Extend `/api/runtime` and overview freshness/runtime wording so both surfaces read controller truth while preserving compatibility keys like `latest_cycle`, `recent_cycles`, `latest_failure`, and `totals`.
3. Update `vinted_radar/cli.py` dashboard URL output and `README.md` operator docs so local serving advertises `/runtime` and explains paused/scheduled/next-resume semantics.
4. Expand `tests/test_dashboard.py` and `tests/test_dashboard_cli.py` to assert `/runtime`, controller-backed `/api/runtime`, and overview home wording, then use the local served dashboard for a final smoke check.

## Must-Haves

- [ ] `/runtime` exists as a real HTML page and stays aligned with the repository-owned runtime contract.
- [ ] `/api/runtime` keeps its existing compatibility keys while adding controller-backed status/timing/error truth.
- [ ] The overview home and dashboard CLI output stop calling a healthy waiting runtime “completed” and instead surface controller-backed scheduled/paused truth.

## Verification

- `python -m pytest tests/test_dashboard.py tests/test_dashboard_cli.py`
- `python -m vinted_radar.cli dashboard --db data/vinted-radar-s01.db --host 127.0.0.1 --port 8781`

## Observability Impact

- Signals added/changed: runtime HTML/API payloads now expose controller status, timing fields, recent errors, and overview-home runtime wording tied to the same DB contract.
- How a future agent inspects this: open `/runtime`, fetch `/api/runtime`, compare `/` and `/health`, and rerun dashboard route/CLI tests.
- Failure state exposed: controller/UI drift, missing timing fields, or a home page that still reports the last completed cycle instead of the current runtime state becomes immediately visible in both HTML and JSON diagnostics.

## Inputs

- `vinted_radar/dashboard.py` — current route map, payload builders, and HTML rendering seam where `/runtime` must be added.
- `vinted_radar/cli.py` — current local dashboard URL output that should advertise the new runtime page.
- `vinted_radar/repository.py` — T01/T02 runtime contract consumed by the runtime page and overview freshness copy.
- `tests/test_dashboard.py` — existing WSGI regression harness for `/`, `/api/runtime`, `/health`, and related routes.
- `tests/test_dashboard_cli.py` — current local dashboard command coverage that should expand to `/runtime`.
- `README.md` — operator-facing route and usage documentation.

## Expected Output

- `vinted_radar/dashboard.py` — `/runtime` route, controller-backed runtime payload builder, and overview/home runtime wording updates.
- `vinted_radar/cli.py` — local dashboard command output that advertises `/runtime` alongside the existing diagnostics URLs.
- `README.md` — refreshed runtime/operator documentation for `/runtime`, `/api/runtime`, and pause/resume semantics.
- `tests/test_dashboard.py` — route and payload assertions for `/runtime`, controller-backed `/api/runtime`, and overview-home runtime wording.
- `tests/test_dashboard_cli.py` — updated CLI smoke coverage for the new `/runtime` URL output.
