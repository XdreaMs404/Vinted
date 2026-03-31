# Project

## What This Is

A local-first Vinted market intelligence radar focused strictly on the Homme and Femme categories and their sub-categories. It tracks public listings over time, separates what was observed from what was inferred, and turns imperfect public signals into a cautious market read about what appears to be moving now.

## Core Value

Turn imperfect public Vinted listing signals into an evidence-backed market read that stays explicit about coverage, freshness, confidence, and uncertainty.

## Current State

M001 implementation is complete and integrated across S01 through S06, and its closeout summary now exists at `.gsd/milestones/M001/M001-SUMMARY.md`. That milestone still carries a **needs-attention** closeout result because the historical proof databases are not yet trustworthy enough for final multi-day acceptance.

M002 product slices S01 through S09 are complete, and the original product closeout has been archived at `.gsd/milestones/M002/M002-CLOSEOUT-S01-S09.md` because the milestone was reopened for platform work. Those slices delivered the SQL-backed French overview home, controller-backed runtime truth, shared mounted/public product shell, SQL-first explorer workspace, narrative/progressive-proof listing detail, explicit degraded acquisition truth, realistic large-corpus VPS proof, native API-side price bounds, and the high-throughput Webshare proxy-pool operator path.

The post-S09 VPS storage incident materially changed the project state: the cleaned live SQLite database remained healthy yet still grew by roughly 1.5 GB during a single successful cycle, and the schema still duplicates heavyweight card payload JSON across mutable and historical tables. M002 has therefore been reopened with S10 through S15 planned to replace the monolithic SQLite boundary with PostgreSQL for mutable control-plane/current-state truth, ClickHouse for analytical serving and rollups, and S3-compatible Parquet object storage for immutable raw evidence. SQLite now remains the legacy live path only until that cutover lands, plus a migration/backfill source for historical continuity.

M002/S10, M002/S11, M002/S12, and M002/S13 are now complete. The repo has the staged polyglot platform foundation from S10, the immutable-evidence path from S11, the first real PostgreSQL mutable-truth path from S12, and now the first ClickHouse serving-warehouse path from S13: a V002 ClickHouse warehouse schema with append-only fact tables, long-lived rollups, latest-per-listing serving tables, replay-safe outbox-to-ClickHouse ingestion with checkpoint/lag visibility, and a repository-shaped ClickHouse query adapter that can serve overview, explorer, and detail payloads without rewriting the dashboard route contracts. The foundation is still staged safely: SQLite remains the legacy live application boundary until S14 historical backfill and application cutover land, but the ClickHouse analytical read seam and parity-proof route verifier are now in place for that cutover.

What is verified today:
- `python -m pytest tests/test_platform_config.py -q`, `python -m pytest tests/test_data_platform_bootstrap.py -q`, `python -m pytest tests/test_event_envelope.py tests/test_outbox.py -q`, and `python -m pytest tests/test_data_platform_smoke.py -q` all pass, proving the S10 platform foundation: shared config/env validation, idempotent bootstrap + doctor flows, deterministic event/manifest contracts, leased PostgreSQL outbox semantics, and a real Docker-backed PostgreSQL + ClickHouse + MinIO smoke path
- `python -m pytest tests/test_api_catalog_page.py tests/test_card_payload.py -q` passes with **50 passed**, proving the minimal versioned listing-card evidence contract and backward-compatible normalization over both new envelopes and legacy flat payloads
- `python -m pytest tests/test_lake_writer.py -q` passes with **2 passed, 1 skipped** in this workstation session, proving deterministic manifest/parquet writing and immutable-key checksum protection while the MinIO integration case remains gated on Docker daemon availability
- `python -m pytest tests/test_evidence_batches.py tests/test_discovery_service.py tests/test_runtime_service.py -q` passes with **20 passed**, proving collector evidence publishing idempotence plus discovery/state-refresh emission of deterministic manifested Parquet batches
- `python -m pytest tests/test_evidence_export.py -q` passes with **3 passed**, proving SQLite evidence backfill plus event/manifest lookup back down to concrete decoded evidence fragments
- `python3 -m pytest tests/test_postgres_schema.py tests/test_platform_config.py tests/test_data_platform_bootstrap.py tests/test_runtime_cli.py tests/test_runtime_service.py tests/test_postgres_backfill.py -q` passes with **36 passed**, proving the S12 PostgreSQL mutable-truth schema/cutover path: schema v3 expectations, runtime CLI polyglot control-plane reads/writes, external-control-plane runtime smoke without SQLite runtime mutation, and explicit SQLite-to-PostgreSQL mutable-truth backfill coverage
- `python3 -m pytest tests/test_clickhouse_schema.py tests/test_clickhouse_ingest.py tests/test_clickhouse_queries.py tests/test_dashboard.py tests/test_clickhouse_parity.py -q` passes with **30 passed**, proving the S13 ClickHouse serving warehouse: schema v2 migration coverage, replay-safe fact ingestion with checkpoint state, repository-shaped overview/explorer/detail reads, dashboard contract preservation, and ClickHouse-vs-repository parity across representative routes
- a direct Python route-proof run against `scripts/verify_clickhouse_routes.py` on a seeded dashboard fixture confirmed `dashboard_api`, `explorer_api`, `detail_api`, `health`, plus ClickHouse HTML dashboard/explorer/detail routes all return 200 and match parity after contract normalization; the same slice-level check recorded `repository_total_ms=65.59` and `clickhouse_total_ms=25.22`
- a direct CLI smoke for `python3 -m vinted_radar.cli clickhouse-ingest-status --format json` (with the task-test checkpoint fixture injected) confirmed the operator-facing lag/checkpoint JSON contract exposes consumer name, last event/manifest, lag seconds, and target-table metadata for serving-ingest monitoring
- a direct Node smoke against the project auto-prompt renderer confirmed future `execute-task` prompts inline the Task Summary and Decisions templates; alongside that prompt-level rule, stale direct slice-closeout file-write instructions are now non-normative and future `complete-slice` units must write closeout artifacts only through `gsd_complete_slice`
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
- M002 still needs S14 and S15 to complete historical backfill/application cutover off the legacy SQLite boundary, then add retention plus AI-ready marts on top of the new Parquet/object-store evidence boundary

## Architecture / Key Patterns

Local-first execution with both batch and continuous operator modes.

Evidence-first product logic: preserve observed facts, derive inferences explicitly, and surface uncertainty instead of hiding it.

Historical observation storage rather than last-write-wins snapshots, so listing evolution, freshness, and revisit cadence can be traced over time.

Mixed market surface: market summaries and rankings must always be backed by listing-level drill-down.

Discovery currently uses the Vinted web catalog API for throughput, while public item pages remain a separate direct-evidence path for cautious state resolution.

SQLite is the legacy runtime boundary that powered the current S01-S09 product and still serves as the pre-cutover live path today.

The target platform decision recorded after the VPS growth incident is to move mutable control-plane/current-state truth to PostgreSQL, analytical serving and rollups to ClickHouse, and immutable raw evidence to Parquet on S3-compatible object storage; SQLite is retained only as a migration/backfill input and offline artifact during the cutover.

M002/S10 now provides the shared config, migration, bootstrap/doctor, event/manifest, and leased outbox seams for that platform, and M002/S13 adds the first repository-shaped ClickHouse serving adapter plus parity-proof route verifier. Cutover flags still default to false so the live application does not switch analytical reads implicitly; S14 will backfill history and perform the intentional application cutover.

Project automation is prompt-self-contained: future auto-mode `execute-task` units use the inlined Task Summary and Decisions templates from the prompt itself, any instruction that points to a user-home template path is treated as stale guidance rather than part of the execution contract, and future `complete-slice` units must draft slice closeout content in memory and call `gsd_complete_slice` instead of writing `Sxx-SUMMARY.md` or `Sxx-UAT.md` directly.

The dashboard is server-rendered and shares one repository-backed payload with its JSON diagnostics so the browser surface and debug surface stay truthful.

M002/S01 begins retiring request-time Python recomputation on primary user paths by moving the overview home and explorer browse path onto repository-owned SQL aggregates/pages, while `/api/dashboard` remains the brownfield compatibility seam for diagnostics and existing callers.

M002/S02 adds a separate `runtime_controller_state` snapshot for current scheduler truth while keeping `runtime_cycles` as immutable history, so `/runtime`, `/api/runtime`, `/health`, and the overview home can distinguish running, scheduled, paused, failed, and recent-cycle outcomes honestly.

Legacy SQLite snapshots can still lag the current schema, but bootstrap now migrates late-added listing metadata columns before creating dependent indexes; `tests/test_repository.py::test_repository_migrates_legacy_listing_columns_before_creating_dependent_indexes` is the guardrail for that path.

## Capability Contract

See `.gsd/REQUIREMENTS.md` for the explicit capability contract, requirement status, and coverage mapping.

## Milestone Sequence

- [x] M001: Listing-Level Market Radar — implementation complete; closeout summary written, verification result `needs-attention` pending healthy multi-day runtime proof.
- [ ] M002: Enriched Market Intelligence Experience — product slices S01 through S13 are complete. The milestone remains open for S14 and S15 to backfill history, cut the live application over off the legacy SQLite boundary, and add retention plus AI-ready marts on top of the new Parquet/object-store evidence layer.
- [ ] M003: Product-Level Intelligence + Grounded AI Layer — group listings into product-level signals and add grounded AI insights, summaries, and analytical exploration.
- [ ] M004: SaaS Hardening and Commercialization — industrialize the radar into a durable SaaS product without sacrificing evidence and credibility.
