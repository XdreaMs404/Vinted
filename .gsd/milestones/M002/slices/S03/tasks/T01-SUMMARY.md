---
id: T01
parent: S03
milestone: M002
provides:
  - Proxy-aware route generation with configurable `base_path` / `public_base_url` across overview, explorer, runtime, health, and listing-detail surfaces
  - A first-class HTML listing detail route at `/listings/<id>` alongside the existing JSON detail endpoint
  - One repeatable `scripts/verify_vps_serving.py` smoke verifier for the mounted product shell
key_files:
  - vinted_radar/serving.py
  - vinted_radar/dashboard.py
  - vinted_radar/cli.py
  - scripts/verify_vps_serving.py
  - tests/test_dashboard.py
  - tests/test_dashboard_cli.py
  - tests/test_runtime_cli.py
  - README.md
  - install_services.sh
key_decisions:
  - D019: keep the existing Python + SQLite + SSR delivery stack and extend it instead of rewriting the app around a new framework
patterns_established:
  - Build product-route links through a shared route context (`base_path` + optional `public_base_url`) so HTML, JSON diagnostics, CLI output, and health checks stay aligned behind a reverse proxy
observability_surfaces:
  - `python scripts/verify_vps_serving.py --base-url ... --listing-id ...`
  - `/health`
  - `python -m vinted_radar.cli dashboard --db ... --base-path ... --public-base-url ...`
  - `tests/test_dashboard.py`
  - `tests/test_dashboard_cli.py`
duration: 1h20m
verification_result: passed
completed_at: 2026-03-23T10:29:23+01:00
blocker_discovered: false
---

# T01: Introduce the proxy-aware serving contract and stable product routes

**Added a shared proxy-aware route contract, an HTML listing-detail page, and a repeatable serving smoke verifier so the product can be mounted behind a VPS proxy without localhost-only links.**

## What Happened

I started by extracting route-generation concerns into a dedicated `vinted_radar/serving.py` helper instead of scattering host/prefix logic across the CLI and HTML renderers.

That helper now owns:
- base-path normalization
- external/public base-URL normalization
- route-path generation for mounted apps
- advertised operator URLs for CLI output

On top of that, `vinted_radar/dashboard.py` now accepts `base_path` and `public_base_url` on the WSGI application/server helpers. The app:
- strips the configured mount prefix from incoming requests when needed
- keeps `/`, `/explorer`, `/runtime`, `/health`, and `/api/...` healthy under a mounted prefix
- exposes a real HTML listing route at `/listings/<id>`
- includes serving metadata in `/health`
- generates proxy-safe links for featured cards, explorer rows, diagnostics, and runtime/detail navigation instead of hardcoding bare localhost-era paths

I also tightened the detail seam. The JSON detail endpoint still exists at `/api/listings/<id>`, but the product now has a stable HTML detail page that future shell work can wrap instead of forcing operators through JSON-only drill-down.

In `vinted_radar/cli.py`, the `dashboard`, `batch --dashboard`, and `continuous --dashboard` commands now accept:
- `--base-path`
- `--public-base-url`

Their printed URLs now include:
- overview home
- explorer
- runtime
- HTML listing detail pattern
- JSON listing detail pattern
- health

That makes the operator output match the actual mounted route contract instead of assuming `http://127.0.0.1:<port>/...` forever.

Finally, I added `scripts/verify_vps_serving.py`. It smoke-checks the real mounted product routes through one base URL and verifies that:
- overview, explorer, runtime, and listing-detail HTML routes all respond with HTML
- the listing-detail API responds with the requested listing
- `/health` stays JSON and reports the expected serving prefix
- generated HTML links include the mounted prefix rather than silently drifting back to `/...`

I updated `README.md` and `install_services.sh` just enough to advertise the new contract and smoke verifier, without waiting for the later T03 operator polish pass.

## Verification

I verified the task in two layers:

1. **Regression / contract tests**
   - `python -m pytest tests/test_dashboard.py tests/test_dashboard_cli.py`
2. **Mounted local smoke using the real server and mounted prefix**
   - seeded `data/vinted-radar-s03.db`
   - started `python -m vinted_radar.cli dashboard --db data/vinted-radar-s03.db --host 127.0.0.1 --port 8782 --base-path radar --public-base-url http://127.0.0.1:8782/radar`
   - ran `python scripts/verify_vps_serving.py --base-url http://127.0.0.1:8782/radar --listing-id 9002`

Both passed.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `python -m pytest tests/test_dashboard.py tests/test_dashboard_cli.py` | 0 | ✅ pass | 0.63s |
| 2 | `python scripts/verify_vps_serving.py --base-url http://127.0.0.1:8782/radar --listing-id 9002` | 0 | ✅ pass | ~0.2s |

## Diagnostics

For future inspection:
- `python scripts/verify_vps_serving.py --base-url ... --listing-id ...` is now the fastest end-to-end check for proxy/base-path drift.
- `/health` now exposes a `serving` block with `base_path`, `public_base_url`, and the mounted route examples.
- `python -m vinted_radar.cli dashboard --db ... --base-path ... --public-base-url ...` prints the exact overview/explorer/runtime/detail/health URLs the operator should test.
- `tests/test_dashboard.py` covers prefixed routes and prefixed HTML links, so route-regression drift should surface before manual smoke.

## Deviations

I introduced one small helper module, `vinted_radar/serving.py`, instead of keeping all route-generation logic embedded inside `dashboard.py` and `cli.py`. The task plan did not name that file, but the extraction keeps the serving contract centralized and makes later shell work safer.

## Known Issues

- The new HTML detail page is intentionally simple. T02 still needs to wrap it into the shared French product shell.
- Explorer copy and layout remain partially English / desktop-shaped in this task. T02 owns the full shell and responsive unification.
- On Git Bash for Windows, an unquoted `--base-path /radar` can be rewritten by MSYS path conversion before Python sees it. Using `--base-path radar`, quoting the value, or disabling path conversion avoids that local-only tooling quirk.

## Files Created/Modified

- `vinted_radar/serving.py` — new shared route-context helper for mounted path generation and advertised operator URLs.
- `vinted_radar/dashboard.py` — proxy-aware routing, mounted-prefix handling, HTML `/listings/<id>` route, serving metadata in `/health`, and prefixed links across HTML payloads.
- `vinted_radar/cli.py` — new `--base-path` / `--public-base-url` options plus consistent advertised URLs for dashboard-capable commands.
- `scripts/verify_vps_serving.py` — mounted-route smoke verifier for overview, explorer, runtime, detail, detail API, and health.
- `tests/test_dashboard.py` — regressions for prefixed routes, HTML detail, prefixed health metadata, and proxy-safe links.
- `tests/test_dashboard_cli.py` — CLI coverage for local and proxy-aware advertised URLs.
- `tests/test_runtime_cli.py` — dashboard-capable runtime commands now assert the new advertised detail routes too.
- `README.md` — documented the proxy/VPS serving contract, HTML detail route, and smoke verifier.
- `install_services.sh` — added dashboard base-path / public-base-url arguments and post-install smoke-check guidance.
- `.gsd/milestones/M002/slices/S03/S03-PLAN.md` — T01 marked complete.
