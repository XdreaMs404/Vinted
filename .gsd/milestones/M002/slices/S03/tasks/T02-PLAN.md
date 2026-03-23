---
estimated_steps: 4
estimated_files: 3
skills_used:
  - frontend-design
  - make-interfaces-feel-better
  - accessibility
  - agent-browser
  - test
  - review
---

# T02: Build the shared French responsive shell across overview, explorer, runtime, and detail

**Slice:** S03 — Responsive French Product Shell + VPS Serving Path
**Milestone:** M002

## Description

Load `frontend-design`, `make-interfaces-feel-better`, `accessibility`, `agent-browser`, `test`, and `review` before coding. T01 makes the routes real; this task makes them feel like one product. The goal is a shared French-first shell with clear landmarks, navigation, and responsive behavior so phone and desktop users see one coherent radar instead of a collection of route-specific layouts.

## Steps

1. Refactor `vinted_radar/dashboard.py` to introduce common page chrome, navigation, and layout helpers reused by overview, explorer, runtime, and detail routes.
2. Replace route-specific English or technical-first headings with French-first product copy while keeping deeper diagnostics available as secondary content.
3. Rework wide desktop sections into responsive card/grid/stacked patterns so key browsing and runtime information remains legible at mobile widths.
4. Expand `tests/test_dashboard.py` to assert shared landmarks, navigation, and route-level layout expectations across the four core product routes.

## Must-Haves

- [ ] The four core HTML routes share one identifiable product shell instead of separate ad-hoc layouts.
- [ ] Navigation, headings, and primary labels are French-first and understandable without hiding evidence/proof access.
- [ ] Mobile-width rendering no longer depends on oversized desktop tables as the primary way to consume the product.

## Verification

- `python -m pytest tests/test_dashboard.py`
- `python -m vinted_radar.cli dashboard --db data/vinted-radar-s03.db --host 127.0.0.1 --port 8782`

## Observability Impact

- Signals added/changed: shared route landmarks/navigation, consistent fallback states, and responsive shell behavior that can be verified route by route.
- How a future agent inspects this: open `/`, `/explorer`, `/runtime`, and `/listings/<id>` in the browser, compare their shared shell structure, and rerun `tests/test_dashboard.py`.
- Failure state exposed: a route drifting out of the shared shell or collapsing into desktop-only layout becomes visible in route tests and browser verification instead of surfacing later as scattered UX inconsistencies.

## Inputs

- `vinted_radar/dashboard.py` — T01 route/base-url work that now needs one shared shell on top.
- `tests/test_dashboard.py` — current route assertions that should expand to shared-shell coverage.
- `tests/test_dashboard_cli.py` — route-output expectations that should stay aligned with the shared shell entrypoints.

## Expected Output

- `vinted_radar/dashboard.py` — shared French product shell, navigation, and responsive layout helpers for overview/explorer/runtime/detail.
- `tests/test_dashboard.py` — route regression coverage for shared landmarks, navigation, and responsive shell expectations.
- `tests/test_dashboard_cli.py` — any small CLI expectation updates required by the unified route set.
