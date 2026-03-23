# S03: Responsive French Product Shell + VPS Serving Path

**Goal:** Make the live radar feel like one coherent French-first product on phone and desktop by shipping a shared SSR shell, stable HTML routes for overview/explorer/runtime/detail, and a proxy-friendly VPS serving contract instead of a localhost-only dev posture.
**Demo:** Run `python -m vinted_radar.cli dashboard --db data/vinted-radar-s03.db --host 127.0.0.1 --port 8782`, apply the proxy/base-url serving flow added in this slice, then open `http://127.0.0.1:8782/`, `/explorer`, `/runtime`, and `/listings/9101` from desktop and a mobile viewport to confirm shared French navigation, responsive layouts, proxy-safe links, and healthy `/health` behavior suitable for VPS access.

## Must-Haves

- Add a shared French-first shell and navigation across overview, explorer, runtime, and an HTML listing-detail route instead of leaving the product split between one polished home and mostly raw secondary routes.
- Make route generation and operator docs compatible with reverse proxy / VPS serving, including stable health/readiness checks and no baked-in localhost assumptions in product links.
- Keep evidence-backed diagnostics accessible but secondary, so the remote product remains understandable to a broad audience without hiding runtime or proof surfaces.

## Proof Level

- This slice proves: operational
- Real runtime required: yes
- Human/UAT required: yes

## Verification

- `python -m pytest tests/test_dashboard.py tests/test_dashboard_cli.py tests/test_cli_smoke.py`
- `python scripts/verify_vps_serving.py --base-url http://127.0.0.1:8782 --listing-id 9101`
- Browser verification at `http://127.0.0.1:8782/` using desktop and mobile viewport confirms shared French navigation, working `/runtime` and `/listings/<id>` HTML routes, and responsive consultation without broken proxy/base-path links.

## Observability / Diagnostics

- Runtime signals: advertised base URL / route generation rules, health/readiness status, current runtime status summary in the shared shell, and explicit degraded-link/error states when a route cannot build detail context.
- Inspection surfaces: `/health`, `/api/runtime`, shared HTML routes (`/`, `/explorer`, `/runtime`, `/listings/<id>`), CLI dashboard output, and `scripts/verify_vps_serving.py`.
- Failure visibility: broken route generation, localhost-only URLs, or responsive regressions remain visible through route tests, smoke verifier failures, and the shared shell's fallback states.
- Redaction constraints: never expose proxy credentials, host secrets, or private network topology in rendered URLs, logs, or docs.

## Integration Closure

- Upstream surfaces consumed: `vinted_radar/dashboard.py`, `vinted_radar/cli.py`, `vinted_radar/repository.py`, `README.md`, `install_services.sh`, and S01/S02 overview/runtime routes.
- New wiring introduced in this slice: shared SSR product shell, HTML listing-detail route, proxy-aware URL/base-path contract, and repo-owned VPS serving smoke verification.
- What remains before the milestone is truly usable end-to-end: S04 still needs deep explorer/comparison utility, S05 still needs narrative-first detail reading, and S06 still needs degraded acquisition truth across the same shell.

## Tasks

- [x] **T01: Introduce the proxy-aware serving contract and stable product routes** `est:1h15m`
  - Why: Remote access is still fragile because the app and docs assume localhost semantics; S03 needs stable route generation and first-class HTML endpoints before shell work can sit on them.
  - Files: `vinted_radar/dashboard.py`, `vinted_radar/cli.py`, `README.md`, `install_services.sh`, `scripts/verify_vps_serving.py`, `tests/test_dashboard.py`, `tests/test_dashboard_cli.py`
  - Do: add proxy/base-url aware URL generation, preserve health/readiness behavior behind a reverse proxy, introduce an HTML `/listings/<id>` route alongside the existing JSON detail payload, and document the serving contract so the product can be consulted remotely without broken links.
  - Verify: `python -m pytest tests/test_dashboard.py tests/test_dashboard_cli.py`
  - Done when: the app can sit behind a VPS/reverse-proxy path without localhost-only URLs or missing HTML routes for runtime/detail navigation.
- [x] **T02: Build the shared French responsive shell across overview, explorer, runtime, and detail** `est:1h30m`
  - Why: The milestone needs a coherent product surface, not one improved page beside several brownfield routes that still read like internal tools.
  - Files: `vinted_radar/dashboard.py`, `tests/test_dashboard.py`, `tests/test_dashboard_cli.py`
  - Do: extract common SSR layout and navigation, switch primary labels/copy to French-first wording, add shared landmarks/breadcrumbs/page chrome, and replace desktop-only route composition with responsive layouts that remain usable on phone and desktop.
  - Verify: `python -m pytest tests/test_dashboard.py`
  - Done when: `/`, `/explorer`, `/runtime`, and `/listings/<id>` visibly share one product shell and stay navigable at mobile and desktop widths.
- [x] **T03: Validate phone/desktop consultation and ship the VPS operator path** `est:1h`
  - Why: S03 is not real until there is one repeatable serving path and one repeatable smoke verification flow that future agents can rerun before touching UI work.
  - Files: `README.md`, `install_services.sh`, `scripts/verify_vps_serving.py`, `tests/test_cli_smoke.py`, `tests/test_dashboard_cli.py`
  - Do: finish the operator-facing serving docs, tighten service install defaults around the new product routes, and add a smoke verifier that checks `/`, `/explorer`, `/runtime`, `/listings/<id>`, and `/health` through the same base URL a VPS operator will use.
  - Verify: `python scripts/verify_vps_serving.py --base-url http://127.0.0.1:8782 --listing-id 9101`
  - Done when: the repo contains one documented VPS/local serving path and one explicit command that passes against the shared shell routes.

## Files Likely Touched

- `vinted_radar/dashboard.py`
- `vinted_radar/cli.py`
- `README.md`
- `install_services.sh`
- `scripts/verify_vps_serving.py`
- `tests/test_dashboard.py`
- `tests/test_dashboard_cli.py`
- `tests/test_cli_smoke.py`
