---
id: M002
title: "Enriched Market Intelligence Experience"
status: complete
completed_at: 2026-03-31T16:35:14.481Z
key_decisions:
  - D019-D022: Keep M002 on the existing Python/WSGI route split and retire primary-path scale risk through repository-owned SQL overview/explorer contracts instead of a framework rewrite.
  - D025-D029: Represent current runtime truth and degraded acquisition honesty as persisted repository/controller contracts shared by CLI, HTML, JSON, and health surfaces.
  - D031-D032: Apply price bounds at the Vinted API boundary and treat proxy pools as route-local transport state with preflight-backed operator proof.
  - D033-D037: Adopt the polyglot split of PostgreSQL mutable truth, ClickHouse serving analytics, and S3-compatible Parquet evidence with one config/bootstrap/outbox contract.
  - D038-D042: Store minimal versioned evidence envelopes and immutable manifested Parquet batches rather than bloating hot mutable tables.
  - D043-D045: Model PostgreSQL control-plane/current-state truth as projector-owned mutable tables with explicit backfill and cutover seams.
  - D047-D052: Move overview/explorer/detail analytics to replay-safe ClickHouse facts behind a repository-shaped adapter while preserving public route parity.
  - D053-D059: Backfill historical SQLite truth idempotently, keep shadow-mode reads honest, and expose one shared cutover state across CLI/runtime/health.
  - D060-D064: Bound the post-cutover platform with lifecycle, audit, truthful change-fact replay, AI-ready marts/evidence packs, and one authoritative cutover verifier.
key_files:
  - README.md
  - infra/clickhouse/migrations/V002__serving_warehouse.sql
  - scripts/verify_clickhouse_routes.py
  - scripts/verify_cutover_stack.py
  - tests/test_clickhouse_ingest.py
  - tests/test_clickhouse_parity.py
  - tests/test_clickhouse_queries.py
  - tests/test_cutover_smoke.py
  - tests/test_feature_marts.py
  - tests/test_full_backfill.py
  - tests/test_lifecycle_jobs.py
  - tests/test_platform_audit.py
  - tests/test_reconciliation.py
  - vinted_radar/cli.py
  - vinted_radar/dashboard.py
  - vinted_radar/platform/clickhouse_ingest.py
  - vinted_radar/platform/config.py
  - vinted_radar/query/detail_clickhouse.py
  - vinted_radar/query/feature_marts.py
  - vinted_radar/query/overview_clickhouse.py
  - vinted_radar/services/full_backfill.py
  - vinted_radar/services/lifecycle.py
  - vinted_radar/services/platform_audit.py
  - vinted_radar/services/reconciliation.py
lessons_learned:
  - After a storage-platform migration, route parity, platform audit, evidence drill-down, and change-fact freshness must be proved together; no single surface is enough to establish honest cutover.
  - When milestone closeout runs on a branch that is itself `main`, code-diff verification must compare against `origin/main` or the integration base rather than `merge-base HEAD main`, or real implementation work will appear as an empty diff.
  - Environment-gated Docker smoke should be recorded as an operational attention note and rerun in CI/VPS, not confused with a missing feature when slice evidence and non-Docker integration suites already prove delivery.
---

# M002: Enriched Market Intelligence Experience

**M002 turned the radar from an SQLite-bound local proof into a French-first market-intelligence product running on a bounded PostgreSQL + ClickHouse + Parquet data platform with truthful runtime, degraded-mode, cutover, audit, and AI-ready evidence surfaces.**

## What Happened

M002 shipped in two coherent halves that now close as one system.

The first half (S01-S09) reshaped the product surface without throwing away the evidence-first backbone. `/` became a SQL-backed French market overview instead of a request-time Python proof screen; runtime truth moved onto a controller-backed contract with pause/resume visibility; overview, explorer, detail, and runtime were unified under a mounted/public shell; explorer became a real browse-and-compare workspace; detail became narrative-first with progressive proof; degraded acquisition truth stayed explicit; realistic-corpus and public-VPS acceptance proved the assembled product; and operator flow hardened through API-side price bounds plus high-throughput Webshare proxy-pool transport.

The second half (S10-S15) replaced the storage boundary that the VPS incident proved could not scale. The repo now boots a real polyglot platform with shared configuration, versioned migrations, deterministic event/manifests, PostgreSQL mutable truth, ClickHouse serving facts/rollups, immutable Parquet evidence storage, resumable historical backfill, shared cutover state, lifecycle retention, reconciliation/audit, truthful change-fact replay, and AI-ready marts/evidence packs. SQLite is no longer the intended long-term live history boundary; it now serves only as migration input plus staged fallback/shadow safety.

Closeout verification re-checked actual assembled behavior instead of trusting slice artifacts blindly. Because this branch is itself `main`, the milestone code-diff audit had to use the integration equivalent (`git diff --stat $(git merge-base HEAD origin/main) HEAD -- ':!.gsd/'`), which showed 36 non-`.gsd/` files changed and 11,969 insertions across application code, migrations, scripts, and tests. Targeted integrated verification then ran:

- `python3 -m pytest tests/test_dashboard.py tests/test_runtime_cli.py tests/test_clickhouse_queries.py tests/test_full_backfill.py tests/test_platform_audit.py tests/test_cutover_smoke.py tests/test_feature_marts.py tests/test_reconciliation.py -q` → **47 passed, 1 skipped**
- `python3 -m pytest tests/test_cutover_smoke.py -q -rs` → **1 skipped** with reason `docker binary is required for the cutover smoke stack test`
- `command -v docker` → exit code **1** in this shell

That Docker note is operational attention, not a delivery failure: step-3/4/5 verification still passed because the milestone produced substantial non-`.gsd/` code, the success contract was met, all slices are complete with summaries/UATs present, and the cross-slice integration audit found no unresolved mismatch.

## Decision Re-evaluation

| Decision set | Re-evaluation | Result |
|---|---|---|
| D019-D022 — keep the Python/WSGI route split and retire home-path scale risk with repository SQL instead of a framework rewrite | Actual delivery validated the incremental brownfield strategy: S01-S05 productized the overview/explorer/detail/runtime loop without reintroducing full-corpus request-time scoring or a frontend rewrite tax. | Still valid |
| D025-D029 — persist controller/runtime truth and degraded acquisition truth as shared repository contracts | S02 and S06/S07 proved this was the right seam: CLI, HTML, JSON, and health stayed aligned, and degraded/partial states remained explicit under realistic corpus and VPS verification. | Still valid |
| D031-D032 — push price bounds to the API boundary and treat proxy pools as route-local operator transport state | S08 and S09 materially improved acquisition efficiency and operator flow without credential leakage or fake local proof. | Still valid |
| D033-D037 — adopt the PostgreSQL + ClickHouse + object-storage platform with shared config/bootstrap/outbox contracts | S10 proved the platform can boot deterministically and observably; the later slices successfully consumed those exact seams. | Still valid |
| D038-D042 — use minimal versioned evidence envelopes plus immutable manifested Parquet batches | S11 and S14 showed the lake can retain raw proof cheaply while staying inspectable and replay-compatible. | Still valid |
| D043-D045 — decompose PostgreSQL mutable truth into projector-owned current-state/control-plane tables with explicit backfill/cutover proof | S12 and S14 validated the separation: runtime/control-plane and current-state truth moved cleanly off SQLite without silently mutating legacy tables. | Still valid |
| D047-D052 — move analytical serving to replay-safe ClickHouse facts and keep public payload parity at the dashboard boundary | S13 route parity, S14 cutover, and current closeout tests show the adapter/parity strategy worked without rewriting route payload builders. | Still valid |
| D053-D059 — backfill idempotently, keep shadow-mode reads honest, and expose one shared cutover snapshot | S14 and S15 discovered and fixed real drift (`runtime-status` shadow reads, missing change-fact pipeline) before closeout; the decision family held up under correction pressure. | Still valid |
| D060-D064 — bound the post-cutover platform with lifecycle/audit/change-fact/mart contracts and one authoritative cutover verifier | S15 delivered bounded retention, unified audit posture, truthful replay-derived change facts, evidence-linked marts, and a stronger acceptance verifier. The only next-step is rerunning the same verifier on Docker-capable infra. | Still valid; rerun proof on CI/VPS next milestone |

No M002 architectural decision currently needs reversal. The only item that should be revisited operationally is where the authoritative Docker-backed cutover proof runs automatically, not the proof contract itself.

## Success Criteria Results

## Success Criteria Audit

> `.gsd/milestones/M002/M002-ROADMAP.md` does not render a separate success-criteria section on disk. Closeout therefore treated the milestone vision plus the 15 slice-level “After this” commitments as the success contract.

### 1) User-facing M002 product surfaces remain coherent, truthful, and useful across overview, explorer, detail, and runtime.
**Verdict:** MET

**Evidence:**
- S01 delivered the SQL-backed French overview, explicit honesty/freshness/confidence cues, and SQL explorer seam.
- S02 made runtime truth controller-backed and surfaced pause/resume/scheduled/failed states truthfully.
- S03 unified overview/explorer/detail/runtime under the mounted/public shell.
- S04 deepened server-side explorer filters, comparisons, sorting, paging, and detail context handoff.
- S05 made listing detail narrative-first with progressive proof.
- S06 preserved degraded acquisition honesty across overview/detail/runtime/health.
- S07 re-proved the assembled product on a realistic 49,759-listing corpus and the real public VPS entrypoint.
- Current closeout verification reran `tests/test_dashboard.py` inside the integrated pytest suite above.

### 2) Acquisition and operator flow are materially hardened rather than left as a local proof path.
**Verdict:** MET

**Evidence:**
- S08 pushed both min and max price bounds to the Vinted API boundary while preserving local safety guards and requested-URL truth.
- S09 delivered proxy-file/Webshare loading, preflight reachability/diversity proof, route-local sync/async transport state, and real multi-route collection.
- The current milestone state recorded live `proxy-preflight` and proxy-backed `batch` proof in slice artifacts and `.gsd/PROJECT.md`.

### 3) The repo contains a real production-grade polyglot data platform foundation, not placeholders.
**Verdict:** MET

**Evidence:**
- S10 delivered shared PostgreSQL + ClickHouse + S3-compatible config, versioned migrations, deterministic event/manifests, a leased outbox, bootstrap/doctor flows, and Docker-backed smoke coverage.
- Key implementation files include `vinted_radar/platform/config.py`, `vinted_radar/platform/clickhouse_ingest.py`, `vinted_radar/services/lifecycle.py`, `vinted_radar/services/platform_audit.py`, and `scripts/verify_cutover_stack.py`.

### 4) Raw evidence is retained cheaply off the mutable hot path.
**Verdict:** MET

**Evidence:**
- S11 replaced heavyweight hot-path payload duplication with minimal versioned evidence envelopes plus deterministic Parquet/manifests on object storage.
- Historical SQLite evidence export now lands as explicit backfill event/manifests instead of pretending to be live collector output.

### 5) Mutable truth and serving reads move off the monolithic SQLite history path.
**Verdict:** MET

**Evidence:**
- S12 moved runtime control, discovery runs, catalogs, and current listing truth into PostgreSQL mutable truth.
- S13 moved overview/explorer/detail analytics onto ClickHouse facts, rollups, and repository-shaped adapters.
- S14 completed resumable backfill, reconciliation, cutover diagnostics, rollback support, and application/runtime cutover.
- Current closeout verification passed `tests/test_clickhouse_queries.py`, `tests/test_full_backfill.py`, and `tests/test_reconciliation.py` inside the 47-pass suite.

### 6) The post-cutover platform is bounded, auditable, and AI-ready.
**Verdict:** MET

**Evidence:**
- S15 delivered lifecycle TTL/archive/prune control, unified `platform-audit`, truthful replay-derived change facts, listing/segment/price/state/evidence-pack marts, and a strengthened `verify_cutover_stack.py` acceptance contract.
- Current closeout verification passed `tests/test_platform_audit.py` and `tests/test_feature_marts.py` inside the 47-pass suite.

### Operational verification note
**Verdict:** ATTENTION NOTE, NOT FAILURE

`tests/test_cutover_smoke.py` is still skipped in this shell because `docker` is unavailable (`command -v docker` exited 1). That leaves the final container-backed rerun softer than ideal in this workstation session, but it does not invalidate the shipped milestone because slice delivery, cross-slice integration, non-Docker acceptance suites, and public/VPS proof all remain intact.

## Definition of Done Results

## Definition of Done Audit

- **All roadmap slices are complete:** MET  
  The roadmap slice overview in the preloaded milestone context shows S01 through S15 all marked done, and `gsd_complete_milestone` validated milestone completion against slice state before writing the summary.

- **All slice summaries exist:** MET  
  `find .gsd/milestones/M002/slices -maxdepth 2 -name 'S*-SUMMARY.md' | wc -l` returned **15**.

- **All slice UAT artifacts exist:** MET  
  `find .gsd/milestones/M002/slices -maxdepth 2 -name 'S*-UAT.md' | wc -l` returned **15**.

- **The milestone produced substantive non-`.gsd/` implementation:** MET  
  Using the integration-equivalent diff on this `main` branch (`git diff --stat $(git merge-base HEAD origin/main) HEAD -- ':!.gsd/'`) showed **36 changed non-`.gsd/` files** touching application code, migrations, scripts, tests, and README; examples include `vinted_radar/cli.py`, `vinted_radar/dashboard.py`, `vinted_radar/platform/clickhouse_ingest.py`, `vinted_radar/services/full_backfill.py`, `vinted_radar/services/lifecycle.py`, `vinted_radar/services/platform_audit.py`, `vinted_radar/services/reconciliation.py`, `vinted_radar/query/feature_marts.py`, `scripts/verify_cutover_stack.py`, and `infra/clickhouse/migrations/V002__serving_warehouse.sql`.

- **Cross-slice integration points work correctly:** MET  
  The existing M002 validation audit found no unresolved cross-slice mismatch. Two real defects were discovered under integration pressure and fixed before closeout rather than carried forward: shadow-mode runtime read drift in S14 and the missing change-fact pipeline uncovered during S15. Current closeout verification also passed the integrated pytest suite covering dashboard/runtime, ClickHouse queries, full backfill, reconciliation, platform audit, feature marts, and cutover smoke harness wiring (**47 passed, 1 skipped**).

- **Horizontal checklist items were addressed:** N/A  
  `.gsd/milestones/M002/M002-ROADMAP.md` does not contain a `Horizontal Checklist` section on disk.

**Overall definition-of-done verdict:** PASS

## Requirement Outcomes

## Requirement Outcome Verification

### Confirmed status transitions
- **R011: active → validated**  
  Supported by M002/S06 introducing the persisted degraded/partial acquisition-truth contract and M002/S07 validating that contract end to end on a realistic mounted corpus plus the recovered public VPS entrypoint. Current `REQUIREMENTS.md` already reflects this transition with concrete proof against `/`, `/explorer`, `/runtime`, `/api/runtime`, `/api/listings/<id>`, and `/health`.

### Requirements materially advanced without a new status change at closeout
- **R001** was materially advanced by S08/S09 through API-side price bounds, proxy-pool throughput, and preflight-backed operator proof, but remains **active**.
- **R002** was materially advanced by S14 through resumable historical backfill and continuity into PostgreSQL/ClickHouse/lake targets, but remains **active**.
- **R003** was reinforced, not reopened: M002 preserved cautious state truth through overview/detail/degraded-mode and replay-derived warehouse paths, but its status remains **active**.
- **R004** was reinforced by S01/S02/S05/S06 but had already been validated previously; no milestone-closeout status change was needed.
- **R007** was materially advanced by S01 comparative modules and S04 explorer comparisons, but remains **active** because broader contextual intelligence continues into later work.
- **R010** was deepened by S02, S03, S06, S07, S08, S09, S12, and S14, but had already been validated previously; no new status change was needed.
- **R012** was materially advanced by the real overview/explorer/detail/runtime utility loop, but remains **active** because broader utility workflows and exports remain future work.
- **R014** was advanced foundationally by S10/S11 and materially by S15 feature marts/evidence packs, but remains **active** pending actual AI insight generation in M003.
- **R015** was advanced by S15 evidence-linked exploratory exports, but remains **active** pending AI-assisted exploration in M003.
- **R016** was materially advanced by S10-S15 bootstrap/cutover/lifecycle/audit hardening, but remains **active** because commercialization/SaaS work is still future-scoped.

### Unsupported transitions check
No unsupported requirement status transition was found. M002 strengthened many active requirements and fully validated R011, but it did not prematurely mark future AI/commercialization requirements as done.

## Deviations

- The roadmap file on disk did not include separate `Success Criteria`, `Definition of Done`, or `Horizontal Checklist` sections, so closeout used the milestone vision plus the 15 slice-level `After this` commitments as the effective success contract.
- Final container-backed cutover smoke could not be rerun end to end in this shell because `docker` is unavailable here; closeout therefore relied on the non-Docker integrated pytest suite plus existing slice UAT/public-VPS evidence for final verification.

## Follow-ups

- Rerun `scripts/verify_cutover_stack.py` or a non-skipped Docker-backed `tests/test_cutover_smoke.py` in Docker-capable CI/VPS so the authoritative cutover proof is recorded on infrastructure that can launch the full stack.
- Automate scheduled `platform-lifecycle` and `platform-audit` execution with alerting if continuous operational assurance is needed.
- Carry the S15 marts/evidence-pack contract into M003 instead of letting future AI features query raw fact tables ad hoc.
