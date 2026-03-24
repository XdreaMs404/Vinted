# Project

## What This Is

A local-first Vinted market intelligence radar focused strictly on the Homme and Femme categories and their sub-categories. It tracks public listings over time, separates what was observed from what was inferred, and turns imperfect public signals into a cautious market read about what appears to be moving now.

## Core Value

Turn imperfect public Vinted listing signals into an evidence-backed market read that stays explicit about coverage, freshness, confidence, and uncertainty.

## Current State

M001 implementation is complete and integrated across S01 through S06, and its closeout summary now exists at `.gsd/milestones/M001/M001-SUMMARY.md`. That milestone still carries a **needs-attention** closeout result because the historical proof databases are not yet trustworthy enough for final multi-day acceptance.

M002 is complete, and its closeout summary now exists at `.gsd/milestones/M002/M002-SUMMARY.md`. S01 through S08 are complete: the home path is SQL-backed and French-first, runtime truth lives in a separate controller snapshot with pause/resume/scheduling surfaced through the CLI, `/runtime`, `/api/runtime`, and `/health`, the product ships with a shared responsive shell plus a mounted VPS-serving contract across overview, explorer, runtime, and HTML listing detail, `/explorer` is the main browse-and-compare workspace with SQL-backed filters and context-preserving detail drill-down, `/listings/<id>` is narrative-first with progressive proof, degraded acquisition truth is explicit across overview, explorer, detail, runtime, `/api/runtime`, and `/health`, large-corpus mounted acceptance has been re-proven on `data/m001-closeout.db`, the real public VPS entrypoint is now back online at `http://46.225.113.129:8765/` after recovering from a corrupted live DB, and discovery/runtime now pass native Vinted `price_from` / `price_to` bounds while keeping the local price guard in place.

M002/S09 extends that baseline with a real high-throughput proxy-pool operator contract: the CLI now accepts raw Webshare `host:port:user:pass` entries, auto-loads a gitignored local `data/proxies.txt` pool when present, discovery/state refresh can use route-local proxy sessions instead of one-hot failure rotation, `proxy-preflight` can verify exit-route diversity plus Vinted API reachability before a run starts, runtime persistence exposes only safe `transport_mode` / `proxy_pool_size` metadata rather than credentials, and the post-slice live concurrency assessment now sets the proxy-pooled auto-cap at 24.

What is verified today:
- `python -m pytest -q` passes
- `python -m pytest tests/test_proxy_config.py tests/test_http.py tests/test_discovery_service.py tests/test_runtime_service.py tests/test_runtime_cli.py tests/test_cli_discover_smoke.py -q` passes with **37 passed** after the concurrency-cap tuning
- `MSYS_NO_PATHCONV=1 python -m vinted_radar.cli dashboard --db data/m001-closeout.db --host 127.0.0.1 --port 8790 --base-path /radar --public-base-url http://127.0.0.1:8790/radar` plus `MSYS_NO_PATHCONV=1 python scripts/verify_vps_serving.py --base-url http://127.0.0.1:8790/radar --listing-id 64882428` re-proved overview, explorer, runtime, detail HTML, detail JSON, and health on the realistic 49,759-listing corpus
- desktop and mobile browser verification on the mounted realistic-corpus shell confirmed overview, explorer, detail, and runtime readability plus context-preserving navigation without console/network failures
- `python scripts/verify_vps_serving.py --base-url http://46.225.113.129:8765 --listing-id 8468335111` passes against the real public VPS entrypoint, and direct public checks against `/`, `/explorer`, `/runtime`, `/api/runtime`, `/api/listings/8468335111`, and `/health` confirm the live operator URL is reachable again
- `python -m pytest tests/test_discovery_service.py tests/test_runtime_service.py tests/test_runtime_cli.py -q` plus a direct Python contract check confirm discovery/runtime now thread native `price_from` / `price_to` bounds and still reject unexpected out-of-range cards locally
- `python -m pytest tests/test_proxy_config.py tests/test_http.py tests/test_discovery_service.py tests/test_runtime_service.py tests/test_runtime_cli.py tests/test_cli_discover_smoke.py -q` plus `python -m vinted_radar.cli proxy-preflight --proxy-file data/proxies.txt --sample-size 12 --timeout-seconds 10 --format json` prove the Webshare proxy contract, multi-route async transport, safe CLI/runtime metadata, and 12 distinct live exit routes with healthy Vinted API reachability.
- `python -m vinted_radar.cli batch --db data/vinted-radar-s09-live.db --page-limit 1 --max-leaf-categories 1 --state-refresh-limit 1 --request-delay 0.2 --timeout-seconds 10 --concurrency 8 --proxy-file data/proxies.txt` plus `python -m vinted_radar.cli runtime-status --db data/vinted-radar-s09-live.db --format json` prove a real proxy-backed batch cycle completed with `transport_mode=proxy-pool`, `proxy_pool_size=100`, one healthy state probe, and 96 listings persisted in the smoke DB
- the VPS had to retire a corrupted 61 GB `data/vinted-radar.db`; services now run against a fresh healthy `data/vinted-radar.clean.db`, while the corrupted file remains archived out of the live serving path
- the runtime still persists `state_refresh_summary_json` on each cycle so degraded item-page probes, anti-bot hits, transport failures, and inconclusive probe counts remain inspectable after the cycle finishes
- legacy SQLite snapshots missing late-added listing metadata columns still reopen successfully because migrations run before dependent indexes are created, with regression coverage in `tests/test_repository.py`

What is still pending on the roadmap:
- M001 still needs trustworthy multi-day closeout evidence from healthy historical databases

## Architecture / Key Patterns

Local-first execution with both batch and continuous operator modes.

Evidence-first product logic: preserve observed facts, derive inferences explicitly, and surface uncertainty instead of hiding it.

Historical observation storage rather than last-write-wins snapshots, so listing evolution, freshness, and revisit cadence can be traced over time.

Mixed market surface: market summaries and rankings must always be backed by listing-level drill-down.

Discovery currently uses the Vinted web catalog API for throughput, while public item pages remain a separate direct-evidence path for cautious state resolution.

SQLite is the durable runtime boundary. Discovery runs, catalog scans, listings, discoveries, observations, item-page probes, and runtime cycles are all persisted so coverage, failures, and operator state remain inspectable after each run.

The dashboard is server-rendered and shares one repository-backed payload with its JSON diagnostics so the browser surface and debug surface stay truthful.

M002/S01 begins retiring request-time Python recomputation on primary user paths by moving the overview home and explorer browse path onto repository-owned SQL aggregates/pages, while `/api/dashboard` remains the brownfield compatibility seam for diagnostics and existing callers.

M002/S02 adds a separate `runtime_controller_state` snapshot for current scheduler truth while keeping `runtime_cycles` as immutable history, so `/runtime`, `/api/runtime`, `/health`, and the overview home can distinguish running, scheduled, paused, failed, and recent-cycle outcomes honestly.

Legacy SQLite snapshots can still lag the current schema, but bootstrap now migrates late-added listing metadata columns before creating dependent indexes; `tests/test_repository.py::test_repository_migrates_legacy_listing_columns_before_creating_dependent_indexes` is the guardrail for that path.

## Capability Contract

See `.gsd/REQUIREMENTS.md` for the explicit capability contract, requirement status, and coverage mapping.

## Milestone Sequence

- [x] M001: Listing-Level Market Radar — implementation complete; closeout summary written, verification result `needs-attention` pending healthy multi-day runtime proof.
- [x] M002: Enriched Market Intelligence Experience — complete; S01 through S09 now ship the SQL-backed overview home, controller-backed runtime truth, shared French product shell, mounted/public serving contract, SQL-first explorer workspace, narrative/progressive-proof listing detail, explicit degraded acquisition truth, realistic large-corpus acceptance, recovered public VPS proof at `http://46.225.113.129:8765/`, native API-side price bounds for discovery/runtime, and a high-throughput Webshare proxy-pool operator path with preflight-backed transport verification.
- [ ] M003: Product-Level Intelligence + Grounded AI Layer — group listings into product-level signals and add grounded AI insights, summaries, and analytical exploration.
- [ ] M004: SaaS Hardening and Commercialization — industrialize the radar into a durable SaaS product without sacrificing evidence and credibility.
