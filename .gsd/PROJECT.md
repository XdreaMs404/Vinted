# Project

## What This Is

A local-first Vinted market intelligence radar focused strictly on the Homme and Femme categories and their sub-categories. It tracks public listings over time, separates what was observed from what was inferred, and turns imperfect public signals into a cautious market read about what appears to be moving now.

## Core Value

Turn imperfect public Vinted listing signals into an evidence-backed market read that stays explicit about coverage, freshness, confidence, and uncertainty.

## Current State

M001 implementation is complete and integrated across S01 through S06, and its closeout summary now exists at `.gsd/milestones/M001/M001-SUMMARY.md`. That milestone still carries a **needs-attention** closeout result because the historical proof databases are not yet trustworthy enough for final multi-day acceptance.

M002 product slices S01 through S09 are complete, and the original product closeout has been archived at `.gsd/milestones/M002/M002-CLOSEOUT-S01-S09.md` because the milestone was reopened for platform work. Those slices delivered the SQL-backed French overview home, controller-backed runtime truth, shared mounted/public product shell, SQL-first explorer workspace, narrative/progressive-proof listing detail, explicit degraded acquisition truth, realistic large-corpus VPS proof, native API-side price bounds, and the high-throughput Webshare proxy-pool operator path.

The post-S09 VPS storage incident materially changed the project state: the cleaned live SQLite database remained healthy yet still grew by roughly 1.5 GB during a single successful cycle, and the schema still duplicates heavyweight card payload JSON across mutable and historical tables. M002 has therefore been reopened with S10 through S15 planned to replace the monolithic SQLite boundary with PostgreSQL for mutable control-plane/current-state truth, ClickHouse for analytical serving and rollups, and S3-compatible Parquet object storage for immutable raw evidence. SQLite now remains the legacy live path only until that cutover lands, plus a migration/backfill source for historical continuity.

M002/S10 is now complete. The repo has a shared polyglot platform configuration contract, versioned PostgreSQL and ClickHouse migrations, `platform-bootstrap` / `platform-doctor` operator commands, deterministic versioned event envelopes and evidence manifests, a leased PostgreSQL outbox contract, and a Docker-backed smoke proof that boots PostgreSQL + ClickHouse + MinIO end to end. The foundation is staged safely: all polyglot cutover flags still default to `false`, so the current product continues reading from SQLite while later slices move ingestion, current-state projection, warehouse serving, and lake retention onto the new platform.

What is verified today:
- `python -m pytest tests/test_platform_config.py -q`, `python -m pytest tests/test_data_platform_bootstrap.py -q`, `python -m pytest tests/test_event_envelope.py tests/test_outbox.py -q`, and `python -m pytest tests/test_data_platform_smoke.py -q` all pass, proving the S10 platform foundation: shared config/env validation, idempotent bootstrap + doctor flows, deterministic event/manifest contracts, leased PostgreSQL outbox semantics, and a real Docker-backed PostgreSQL + ClickHouse + MinIO smoke path
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
- M002/S11 through S15 now need implementation to cut the live platform over from the legacy SQLite boundary to PostgreSQL + ClickHouse + S3-compatible Parquet storage

## Architecture / Key Patterns

Local-first execution with both batch and continuous operator modes.

Evidence-first product logic: preserve observed facts, derive inferences explicitly, and surface uncertainty instead of hiding it.

Historical observation storage rather than last-write-wins snapshots, so listing evolution, freshness, and revisit cadence can be traced over time.

Mixed market surface: market summaries and rankings must always be backed by listing-level drill-down.

Discovery currently uses the Vinted web catalog API for throughput, while public item pages remain a separate direct-evidence path for cautious state resolution.

SQLite is the legacy runtime boundary that powered the current S01-S09 product and still serves as the pre-cutover live path today.

The target platform decision recorded after the VPS growth incident is to move mutable control-plane/current-state truth to PostgreSQL, analytical serving and rollups to ClickHouse, and immutable raw evidence to Parquet on S3-compatible object storage; SQLite is retained only as a migration/backfill input and offline artifact during the cutover.

M002/S10 now provides the shared config, migration, bootstrap/doctor, event/manifest, and leased outbox seams for that platform, but all cutover flags still default to false so user-facing reads remain on SQLite until the later slices land.

The dashboard is server-rendered and shares one repository-backed payload with its JSON diagnostics so the browser surface and debug surface stay truthful.

M002/S01 begins retiring request-time Python recomputation on primary user paths by moving the overview home and explorer browse path onto repository-owned SQL aggregates/pages, while `/api/dashboard` remains the brownfield compatibility seam for diagnostics and existing callers.

M002/S02 adds a separate `runtime_controller_state` snapshot for current scheduler truth while keeping `runtime_cycles` as immutable history, so `/runtime`, `/api/runtime`, `/health`, and the overview home can distinguish running, scheduled, paused, failed, and recent-cycle outcomes honestly.

Legacy SQLite snapshots can still lag the current schema, but bootstrap now migrates late-added listing metadata columns before creating dependent indexes; `tests/test_repository.py::test_repository_migrates_legacy_listing_columns_before_creating_dependent_indexes` is the guardrail for that path.

## Capability Contract

See `.gsd/REQUIREMENTS.md` for the explicit capability contract, requirement status, and coverage mapping.

## Milestone Sequence

- [x] M001: Listing-Level Market Radar — implementation complete; closeout summary written, verification result `needs-attention` pending healthy multi-day runtime proof.
- [ ] M002: Enriched Market Intelligence Experience — product slices S01 through S10 are complete. The milestone remains open for S11 through S15 to move live ingestion, current-state truth, analytics serving, backfill, retention, and AI-ready marts onto the new PostgreSQL + ClickHouse + S3-compatible Parquet platform.
- [ ] M003: Product-Level Intelligence + Grounded AI Layer — group listings into product-level signals and add grounded AI insights, summaries, and analytical exploration.
- [ ] M004: SaaS Hardening and Commercialization — industrialize the radar into a durable SaaS product without sacrificing evidence and credibility.
