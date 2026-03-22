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

# T02: Rebuild `/` as a French overview home on top of the SQL contract

**Slice:** S01 — SQL-Backed Overview Home + First Comparative Modules
**Milestone:** M002

## Description

Load `frontend-design`, `make-interfaces-feel-better`, `accessibility`, and `agent-browser` before coding. This task turns the new repository contract into the real default product surface. The current home still says "dashboard", stays mostly English, and exposes dense proof tables that read like an internal debugger. Replace that with a French-first overview page that tells a broader audience what is moving now, how trustworthy the read is, and where to go next, while preserving drill-down access to explorer, runtime truth, and detail JSON.

## Steps

1. Refactor `build_dashboard_payload()` and the `/` route to consume the T01 SQL overview contract for the primary home path, and keep `/api/dashboard` as the machine-readable overview payload (adding a clearer alias only if it does not break the brownfield seam).
2. Rework `render_dashboard_html()` into a French market-overview surface with accessible sectioning, responsive cards, and first comparison modules instead of the current M001 proof-screen framing.
3. Surface low-support, partial, degraded, inferred, and estimated-signal notes directly in the page and JSON payload so the new product copy stays honest under R011-style weak evidence conditions.
4. Update the local dashboard command output, route documentation, and route tests so the browser surface, CLI messaging, and JSON endpoints all reflect the new overview semantics.

## Must-Haves

- [ ] `/` and its JSON payload are backed by the T01 SQL overview contract rather than full-corpus Python scoring on the primary path.
- [ ] The main overview copy and section labels are French-first and understandable to a broader audience.
- [ ] The home surface keeps visible honesty cues plus working links to `/explorer`, `/api/runtime`, `/health`, and listing-detail JSON.

## Verification

- `python -m pytest tests/test_dashboard.py tests/test_dashboard_cli.py`
- `python -m vinted_radar.cli dashboard --db data/vinted-radar-s01.db --host 127.0.0.1 --port 8765`
- Browser check at `http://127.0.0.1:8765/` — French overview headings, coverage/freshness/confidence honesty, comparison modules, and explorer/runtime links are visible with no console or failed-request errors.

## Observability Impact

- Signals added/changed: overview JSON now exposes support counts, low-signal reasons, latest runtime/failure summary, and any compatibility alias metadata added for the home payload.
- How a future agent inspects this: open `/`, fetch `/api/dashboard`, inspect `/api/runtime` and `/health`, and rerun the seeded WSGI tests.
- Failure state exposed: empty, thin-support, or degraded overview modules show explicit reasons in the payload/UI instead of collapsing into generic blank cards.

## Inputs

- `vinted_radar/dashboard.py` — current route, payload, and HTML rendering seam that must become the overview home.
- `vinted_radar/cli.py` — current local dashboard entrypoint and printed URLs.
- `vinted_radar/repository.py` — T01 SQL overview contract consumed by the rebuilt home route.
- `tests/test_overview_repository.py` — T01 contract assertions that define what the home route may rely on.
- `tests/test_dashboard.py` — existing WSGI regression harness for HTML and JSON route behavior.
- `tests/test_dashboard_cli.py` — existing CLI smoke coverage for the local overview server command.
- `README.md` — current user-facing route and entrypoint documentation.

## Expected Output

- `vinted_radar/dashboard.py` — French overview payload assembly, HTML rendering, and any compatibility alias handling for the home payload.
- `vinted_radar/cli.py` — updated local server command messaging if the home/JSON semantics change.
- `tests/test_dashboard.py` — updated HTML/JSON route assertions for the overview home contract.
- `tests/test_dashboard_cli.py` — updated CLI coverage for the served overview URLs and entrypoint messaging.
- `README.md` — refreshed local usage notes for the overview home and related JSON endpoints.
