# S06: Acquisition Hardening + Degraded-Mode Visibility

**Goal:** Harden the weaker item-page/state-refresh acquisition seam and make degraded or partial acquisition conditions explicit across overview, explorer, listing detail, runtime, and machine-readable diagnostics.
**Demo:** Run `python -m pytest tests/test_item_page_parser.py tests/test_runtime_service.py tests/test_runtime_repository.py tests/test_runtime_cli.py tests/test_overview_repository.py tests/test_dashboard.py tests/test_dashboard_cli.py`, then `python -m vinted_radar.cli dashboard --db data/vinted-radar-s06.db --host 127.0.0.1 --port 8786`, open `/`, `/explorer`, `/runtime`, `/listings/9002`, `/api/runtime`, and `/health`, and verify that proxy-aware state refresh telemetry, degraded acquisition status, recent scan failures, and probe-level caution copy are visible and consistent.

## Must-Haves

- State refresh must become proxy-aware and classify anti-bot / transport degradation distinctly instead of collapsing every bad probe into generic `unknown`.
- Persisted runtime truth must expose acquisition-health telemetry from both discovery scans and item-page probes so the product can distinguish healthy, partial, and degraded collection.
- Overview, explorer, detail, runtime, `/api/runtime`, and `/health` must surface degraded-mode honesty in broader-language product copy without hiding the underlying diagnostics.

## Proof Level

- This slice proves: integration
- Real runtime required: yes
- Human/UAT required: yes

## Verification

- `python -m pytest tests/test_item_page_parser.py tests/test_runtime_service.py tests/test_runtime_repository.py tests/test_runtime_cli.py tests/test_overview_repository.py tests/test_dashboard.py tests/test_dashboard_cli.py`
- `python -m vinted_radar.cli dashboard --db data/vinted-radar-s06.db --host 127.0.0.1 --port 8786`
- Browser verification at `http://127.0.0.1:8786/` confirms degraded acquisition messaging on overview, explorer, detail, runtime, `/api/runtime`, and `/health` against a seeded S06 demo DB.

## Observability / Diagnostics

- Runtime signals: latest cycle acquisition-health summary, probe degradation counts/reasons, recent scan failures, controller heartbeat, and explicit healthy/partial/degraded status.
- Inspection surfaces: `python -m vinted_radar.cli runtime-status --db <db>`, `python -m vinted_radar.cli state-refresh --db <db> --format json`, `/api/runtime`, `/api/dashboard`, `/api/explorer`, `/api/listings/<id>`, `/health`, and seeded dashboard/browser proof.
- Failure visibility: anti-bot challenges, HTTP probe degradation, probe exceptions, and recent catalog scan failures remain visible in persisted runtime data instead of being flattened into silent uncertainty.
- Redaction constraints: runtime config and proxy URLs stay sanitized; do not expose proxy credentials or secrets in HTML, JSON, or logs.

## Integration Closure

- Upstream surfaces consumed: `vinted_radar/http.py`, `vinted_radar/parsers/item_page.py`, `vinted_radar/services/state_refresh.py`, `vinted_radar/services/runtime.py`, `vinted_radar/repository.py`, `vinted_radar/dashboard.py`, and the S02-S05 runtime/explorer/detail shell.
- New wiring introduced in this slice: proxy-aware state refresh, persisted acquisition-health telemetry, degraded-mode payload contracts, and product-surface caution copy across overview/explorer/detail/runtime/health.
- What remains before the milestone is truly usable end-to-end: S07 still needs live VPS acceptance on the fully assembled product with remote phone/desktop proof.

## Tasks

- [x] **T01: Harden state refresh transport and persist probe degradation telemetry** `est:2h`
  - Why: S06 starts at the weakest acquisition seam. If item-page probing stays proxy-blind and challenge-blind, the product will continue to hide degraded collection behind generic `unknown` states.
  - Files: `vinted_radar/parsers/item_page.py`, `vinted_radar/services/state_refresh.py`, `vinted_radar/services/runtime.py`, `vinted_radar/repository.py`, `vinted_radar/db.py`, `vinted_radar/cli.py`, `tests/test_item_page_parser.py`, `tests/test_runtime_service.py`, `tests/test_runtime_repository.py`, `tests/test_runtime_cli.py`
  - Do: detect anti-bot / challenge-shaped item-page responses explicitly, pass proxy pools into state refresh from batch/continuous and the standalone CLI, extend state-refresh/runtime persistence with structured probe degradation summaries, and keep sanitized config/runtime output trustworthy.
  - Verify: `python -m pytest tests/test_item_page_parser.py tests/test_runtime_service.py tests/test_runtime_repository.py tests/test_runtime_cli.py`
  - Done when: the latest runtime cycle and runtime-status payload expose persisted state-refresh degradation summaries, and proxy pools reach item-page probes through both runtime and direct CLI entrypoints.
- [x] **T02: Surface acquisition health honestly across overview, explorer, detail, runtime, and health JSON** `est:2h`
  - Why: Hardening the backend is not enough; the slice only closes if every product surface can say when acquisition is healthy, partial, or degraded without making the user infer it from raw failures.
  - Files: `vinted_radar/repository.py`, `vinted_radar/dashboard.py`, `tests/test_overview_repository.py`, `tests/test_dashboard.py`
  - Do: derive an acquisition-health contract from persisted scan failures and probe degradation summaries; add explicit healthy/partial/degraded cues to overview honesty notes, explorer summary copy, runtime status/detail, listing-detail risk notes/provenance, `/api/runtime`, and `/health`; keep raw diagnostics and visible copy aligned.
  - Verify: `python -m pytest tests/test_overview_repository.py tests/test_dashboard.py tests/test_dashboard_cli.py`
  - Done when: the product and JSON surfaces agree on recent acquisition degradation, and degraded probes/scan failures remain visible in broader-language copy instead of disappearing into technical detail.
- [x] **T03: Document and re-prove degraded-mode behavior with seeded browser UAT** `est:1h30m`
  - Why: S06 is an integration slice. It is not done until a future agent can recreate the degraded-mode proof path and trust that the product wording matches the persisted diagnostics.
  - Files: `README.md`, `.gsd/milestones/M002/slices/S06/S06-UAT.md`, `.gsd/milestones/M002/slices/S06/S06-SUMMARY.md`, `.gsd/milestones/M002/slices/S06/tasks/T03-SUMMARY.md`
  - Do: update operator docs for proxy-aware state refresh and degraded-mode surfaces, create a repeatable S06 demo DB + UAT path, run the local dashboard with browser verification against the seeded degraded dataset, and capture the final slice evidence in task/slice summaries.
  - Verify: `python -m pytest tests/test_dashboard.py tests/test_dashboard_cli.py tests/test_runtime_cli.py`
  - Done when: README + UAT describe the degraded-mode workflow accurately and the browser proof confirms the same honesty contract on the actual served routes.

## Files Likely Touched

- `vinted_radar/parsers/item_page.py`
- `vinted_radar/services/state_refresh.py`
- `vinted_radar/services/runtime.py`
- `vinted_radar/repository.py`
- `vinted_radar/dashboard.py`
- `vinted_radar/db.py`
- `vinted_radar/cli.py`
- `README.md`
- `tests/test_item_page_parser.py`
- `tests/test_runtime_service.py`
- `tests/test_runtime_repository.py`
- `tests/test_runtime_cli.py`
- `tests/test_overview_repository.py`
- `tests/test_dashboard.py`
- `tests/test_dashboard_cli.py`
