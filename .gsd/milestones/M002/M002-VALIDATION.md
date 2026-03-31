---
verdict: needs-attention
remediation_round: 0
---

# Milestone Validation: M002

## Success Criteria Checklist
> Note: `.gsd/milestones/M002/M002-ROADMAP.md` renders the milestone vision and slice-level “After this” commitments but does not include a separate success-criteria section on disk. This validation therefore used the vision plus the 15 slice commitments as the effective success contract.

- [x] **User-facing M002 product surfaces stayed coherent and truthful through the S01-S09 line.** Evidence: S01 delivered the SQL-backed French overview and explorer seam; S02 made runtime truth controller-backed; S03 unified overview/explorer/detail/runtime under a mounted French shell; S04 deepened explorer filters/comparisons; S05 made detail narrative-first; S06 surfaced degraded acquisition explicitly; S07 re-proved the assembled product on a realistic 49,759-listing mounted corpus plus the real public VPS entrypoint.
- [x] **Acquisition/operator flow was materially hardened instead of remaining a thin local proof path.** Evidence: S08 pushed both min/max price bounds to the Vinted API boundary while preserving local guards and requested-URL truth; S09 added proxy-file/Webshare pool loading, preflight reachability/diversity checks, and real multi-route transport instead of retry-only proxy failover.
- [x] **The repo now contains a real polyglot platform foundation, not just future placeholders.** Evidence: S10 delivered shared PostgreSQL + ClickHouse + S3-compatible config, versioned migrations, `platform-bootstrap`, `platform-doctor`, deterministic event/manifests, a leased outbox, and a real Docker-backed platform smoke path.
- [x] **Raw evidence is now retained cheaply off the mutable hot path.** Evidence: S11 replaced heavyweight raw-card copying with a minimal evidence envelope, wrote deterministic manifested Parquet batches to object storage, emitted collector-side discovery/probe evidence, and added evidence export/inspect tooling.
- [x] **Mutable truth and serving reads moved off the monolithic SQLite history path.** Evidence: S12 introduced PostgreSQL mutable truth and projector-backed control-plane/current-state writes; S13 introduced ClickHouse facts, rollups, latest-serving tables, replay-safe ingest, and route parity checks; S14 added full backfill, reconciliation, cutover diagnostics, and application/runtime cutover onto PostgreSQL + ClickHouse with SQLite reduced to fallback/shadow safety.
- [x] **The post-cutover platform is now bounded, auditable, and AI-ready.** Evidence: S15 added lifecycle TTL/archive/prune controls, a unified `platform-audit` surface, truthful change-fact replay, AI-ready listing/segment/price/state/evidence-pack marts, and a stronger `verify_cutover_stack.py` acceptance contract.
- [~] **Final container-backed cutover proof in this shell is only partially evidenced.** Current validation reran `python3 -m pytest tests/test_platform_audit.py tests/test_cutover_smoke.py -q` and got `3 passed, 1 skipped`; `command -v docker` returned exit code `1`, so the live-stack branch remains environment-gated. This is an operational-verification note, not a slice-delivery failure.

## Slice Delivery Audit
| Slice | Roadmap claim | Delivered evidence | Verdict |
|---|---|---|---|
| S01 | `/` becomes a SQL-backed market overview with first comparative modules and a real explorer seam | Summary/UAT show `overview_snapshot()`, French overview home, honest comparison modules, SQL-paged `/explorer`, and verified `/api/dashboard`, `/api/explorer`, `/api/runtime`, `/health`, and detail JSON diagnostics | Pass |
| S02 | Runtime can show running/paused/scheduled/failed truth via page, API, and CLI | Summary/UAT show `runtime_controller_state`, cooperative pause/resume, dedicated `/runtime`, controller-backed `/api/runtime` + `/health`, and live CLI smoke for pause/resume transitions | Pass |
| S03 | Product becomes a coherent French-first responsive shell served through a mounted/VPS-style path | Summary/UAT show shared shell across overview/explorer/runtime/detail, mounted `base_path`/`public_base_url` contract, mobile/desktop browser proof, and `verify_vps_serving.py` smoke | Pass |
| S04 | Explorer supports real corpus filters/sorts/paging/comparisons without leaving the product | Summary/UAT show repository-owned classified explorer snapshot, filter-first workspace, price-band/state/category/brand/condition support, context-preserving detail loop, and historical DB/browser proof | Pass |
| S05 | Listing detail becomes narrative-first with progressive proof | Summary/UAT show reusable narrative/provenance contract, French detail page led by plain-language reading, progressive disclosures, preserved explorer context, and route/browser proof | Pass |
| S06 | Acquisition hardening + degraded-mode visibility keep uncertainty explicit | Summary/UAT show proxy-aware state refresh, structured degraded probe telemetry, shared acquisition block on HTML/JSON/runtime/health surfaces, and degraded local proof DB/browser verification | Pass |
| S07 | Assembled radar is proven end to end on realistic corpus and real VPS entrypoint | Summary/UAT show realistic 49,759-listing mounted proof, desktop/mobile browser verification, public VPS smoke, public contract assertions, and recovery from the corrupted live DB | Pass |
| S08 | Discovery/runtime can constrain min/max price at the API boundary | Summary/UAT show `max_price` on shared options/CLI/runtime config, `price_from` + `price_to` URL emission, preserved local guards, and contract checks | Pass |
| S09 | Operators can use a local Webshare proxy pool with real multi-route transport | Summary/UAT show proxy-file/data-proxies loading, masked metadata, route-local HTTP lanes, `proxy-preflight`, live `batch` smoke, and safe `runtime-status` output | Pass |
| S10 | Repo can boot the PostgreSQL + ClickHouse + object-store platform with shared config, migrations, and outbox plumbing | Summary/UAT show validated config, versioned migrations, bootstrap/doctor, deterministic event/manifest contracts, leased outbox, Docker-backed smoke, and operator readiness text | Pass |
| S11 | Discovery and state refresh emit minimal evidence fragments into manifested Parquet lake storage | Summary/UAT show shared minimal evidence envelope, immutable Parquet/manifests, collector-side batch emission, and export/inspect tooling for replay/debug | Pass |
| S12 | Runtime control, discovery runs, catalogs, and current listing truth live in PostgreSQL through projector-backed writes | Summary/UAT show PostgreSQL V003 schema, mutable-truth projectors, PostgreSQL-backed runtime/control-plane cutover under flags, and explicit `postgres-backfill` coverage | Pass |
| S13 | Overview/explorer/detail analytics read from ClickHouse facts and rollups | Summary/UAT show ClickHouse serving schema, replay-safe ingest, repository-shaped query adapter, route parity verifier, and ingest-status observability | Pass |
| S14 | Historical SQLite evidence is backfilled into PostgreSQL/ClickHouse/lake and the application cuts over end to end | Summary/UAT show resumable full backfill, reconciliation, shared cutover snapshot, product/runtime cutover, rollback runbook, and smoke coverage; only the Docker-backed live-stack branch was skipped in this shell | Pass (env note) |
| S15 | Retention, reconciliation, and AI-ready marts keep the platform bounded, auditable, and ready for grounded intelligence | Summary/UAT show lifecycle controls, unified platform audit, repaired truthful change-fact replay, feature marts/evidence packs with traceability, and stronger cutover verifier; Docker-backed live-stack proof remains env-gated here | Pass (env note) |

## Cross-Slice Integration
## Boundary audit

- **S01 → S02/S03/S04/S05/S06/S07:** The SQL-backed overview, explorer seam, and honesty vocabulary were actually consumed downstream. S02 extends freshness/runtime wording; S03 wraps the same route split in the mounted shell; S04 reuses the lens vocabulary for explorer filters/comparisons; S05 preserves explorer context into detail; S06 carries degraded acquisition truth through the same overview/explorer/detail/runtime surfaces; S07 re-proves the assembled loop.
- **S02 → S03/S06/S07:** Controller-backed runtime truth was preserved as a separate boundary. S03 makes `/runtime` part of the mounted shell, S06 layers acquisition health without collapsing it into controller state, and S07 verifies both truths together on realistic corpus and public VPS surfaces.
- **S04 → S05:** Explorer context handoff is aligned. S04 establishes the authoritative explorer → detail analytical loop and S05 explicitly keeps that active explorer lens visible in both HTML and JSON detail responses.
- **S06 → S07/S08/S09:** Acquisition honesty and operator plumbing align. S07 re-proves degraded-mode product behavior, S08 extends the shared acquisition/runtime option path with `max_price`, and S09 extends the same operator path with proxy-pool transport and preflight instead of inventing a parallel flow.
- **S10 → S11/S12/S13:** The platform foundation was consumed consistently. S11 reuses S10 event/manifests/object-store prefixes for immutable lake writes, S12 reuses those seams for PostgreSQL projector/backfill work, and S13 reuses them for replay-safe ClickHouse ingest and checkpoint state.
- **S12 + S13 → S14:** The mutable-truth and analytical-serving boundaries close correctly into cutover. S14 backfills SQLite into PostgreSQL/ClickHouse/lake, exposes one shared cutover snapshot, and moves dashboard/runtime/CLI reads onto PostgreSQL + ClickHouse with SQLite retained only for fallback/shadow safety.
- **S14 → S15:** The cutover path was hardened rather than bypassed. S15 adds lifecycle, unified audit, truthful change-fact replay, marts, and stronger end-to-end proof on top of the existing cutover snapshot and reconciliation contract.

## Mismatches found

No unresolved cross-slice boundary mismatch was found. Two integration defects were discovered inside execution and fixed before closeout rather than left outstanding:

1. **S14 shadow-mode runtime read path drift** — `runtime-status` incorrectly tried PostgreSQL during `dual-write-shadow`; S14 fixed it so shadow-mode reads continue honoring SQLite until `polyglot-cutover` is enabled.
2. **S15 change-fact pipeline gap** — mart work initially exposed that the cutover pipeline did not populate the advertised change tables; S15 replanned, repaired replay/change-fact derivation, and only then shipped marts.

Those are signs of successful reconciliation pressure, not evidence of an unresolved boundary break.

## Requirement Coverage
- `.gsd/REQUIREMENTS.md` currently reports **9 active requirements** and **9 mapped**; there is **no unmapped active requirement** at the project level.
- M002 directly **advanced or validated** the requirements it was expected to touch:
  - **R001** via S08/S09 acquisition efficiency and proxy-pool operator flow.
  - **R002** via S14 historical backfill/current-state migration continuity.
  - **R004** validated in S01 and deepened in S02/S05/S06.
  - **R007** advanced by S01’s first comparative modules and S04’s deeper explorer comparisons.
  - **R008** materially advanced by S13’s ClickHouse-backed overview serving path.
  - **R009** deepened by S03/S05/S07 user-facing shell/detail/integration work and by S13 analytical cutover.
  - **R010** strengthened repeatedly across S02, S03, S06, S07, S08, S09, S12, and S14.
  - **R011** validated through S06 + S07 and reinforced by S14 cutover visibility.
  - **R012** advanced across S01/S03/S04/S05/S07 and now has a real overview/explorer/detail/runtime utility loop.
  - **R014** advanced foundationally by S10/S11 and materially by S15 feature marts/evidence packs.
  - **R015** advanced foundationally by S15’s evidence-linked analytical exports.
  - **R016** materially advanced across S10-S15 through bootstrap, cutover, lifecycle, audit, and operational hardening.
- **R003** was not a new M002 target, but no slice evidence suggests regression of the cautious state taxonomy; S06/S13/S15 instead preserve its truthfulness in degraded, warehouse, and replay-derived paths.
- **R013** remains intentionally future-scoped to M003 and is therefore not a coverage gap against M002.
- Conclusion: no M002-owned or M002-advanced requirement lacks slice evidence, and M002 did not introduce any new requirement-coverage hole.

## Verification Class Compliance
## Contract — Pass
Contract coverage is strong across the whole milestone. Evidence includes S01 overview/repository/dashboard contract tests, S02 runtime repository/service/CLI tests, S04/S05 route/detail coverage, S08 discovery/runtime price-bound contract checks, S10 config/bootstrap/event/outbox tests, S11 parser/evidence-envelope/lake-writer/export tests, S12 PostgreSQL schema/backfill/runtime tests, S13 ClickHouse schema/ingest/query/parity tests, S14 backfill/reconciliation/dashboard/runtime tests, and S15 lifecycle/audit/feature-mart tests.

## Integration — Pass
Integration evidence is also strong. S07 proves the assembled overview/explorer/detail/runtime loop on a realistic corpus and the public VPS. S11 shows collector writes reaching manifested object storage. S12 shows projector-backed PostgreSQL mutable truth. S13 shows replay-safe outbox-to-ClickHouse ingest plus route parity. S14 shows full backfill, cross-store reconciliation, cutover diagnostics, and cutover smoke coverage. S15 extends the end-to-end verifier to include audit posture, change facts, evidence drill-down, and route parity.

## Operational — Needs attention (minor, environment-gated)
Operational verification is materially addressed but not fully closed in this shell. Positive evidence: S10 ran a real Docker-backed platform smoke; S07 proved public VPS serving/recovery; S14 added cutover diagnostics, rollback runbook, and cutover smoke; S15 added lifecycle, audit, lag, and stronger acceptance proof. Current validation reran `python3 -m pytest tests/test_platform_audit.py tests/test_cutover_smoke.py -q` and got `3 passed, 1 skipped`.

The remaining gap is explicit: `docker` is not available in this environment (`command -v docker` exited `1`), so the live-stack branch of cutover smoke still lacks a non-skipped rerun here. This does **not** indicate a feature gap, but it does leave the final operational proof class slightly softer than ideal for milestone sealing.

## UAT — Pass
UAT coverage is strong and appropriately matched to slice type. S01-S07 provide browser/UAT evidence for the French overview, runtime, mounted shell, explorer, detail, degraded-mode messaging, realistic-corpus behavior, mobile responsiveness, and public VPS serving. S08-S09 provide operator UAT for price bounds, proxy preflight, and live proxy-backed collection. S10-S15 provide platform acceptance-check UATs for bootstrap, evidence lake, PostgreSQL control plane, ClickHouse warehouse, cutover, lifecycle, audit, and feature marts.

## Deferred work inventory
- Rerun `scripts/verify_cutover_stack.py` or a non-skipped Docker-backed `tests/test_cutover_smoke.py` in Docker-capable CI/VPS before treating rollout-proof as fully closed.
- After milestone closeout, automate scheduled `platform-lifecycle` / `platform-audit` execution and alerting if continuous operational assurance is desired.


## Verdict Rationale
All 15 roadmap slices are substantiated by their summaries and UAT artifacts, and no unresolved cross-slice delivery mismatch was found. The milestone clearly delivered the intended product evolution: the user-facing French market-intelligence experience from S01-S09 stayed coherent and truthful, while S10-S15 replaced the monolithic SQLite hot path with a bootable PostgreSQL + ClickHouse + object-storage platform, backfill/cutover machinery, and AI-ready evidence/mart seams.

The only notable gap is operational-verification depth in the current shell: the Docker-gated live-stack branch of the final cutover smoke remains skipped because this environment has no `docker` binary. That is important enough to document, but it is not a material product or architecture shortfall and does not require new remediation slices. For that reason the milestone is best classified as **needs-attention** rather than **needs-remediation**.
