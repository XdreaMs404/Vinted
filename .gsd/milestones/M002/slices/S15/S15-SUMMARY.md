---
id: S15
parent: M002
milestone: M002
provides:
  - Bounded-storage lifecycle controls for ClickHouse, transient PostgreSQL control-plane rows, and object-storage retention classes.
  - One operator-facing audit surface that explains reconciliation, ingestion lag, lifecycle drift, and backfill posture across the polyglot platform.
  - Truthful ClickHouse change facts derived during replay/backfill with terminal-page-aware manifest semantics.
  - Stable AI-ready listing-day, segment-day, price-change, state-transition, and evidence-pack exports with explicit traceability.
  - A stronger end-to-end cutover verifier that proves audit posture, warehouse freshness, evidence drill-down, and SQLite analytical hot-path retirement.
requires:
  - slice: S14
    provides: Historical backfill, cross-store reconciliation, cutover diagnostics, and the PostgreSQL + ClickHouse application read path that S15 hardens and extends.
affects:
  - M003
key_files:
  - vinted_radar/services/lifecycle.py
  - vinted_radar/services/platform_audit.py
  - vinted_radar/platform/clickhouse_ingest.py
  - vinted_radar/services/full_backfill.py
  - vinted_radar/query/feature_marts.py
  - vinted_radar/query/overview_clickhouse.py
  - vinted_radar/cli.py
  - vinted_radar/platform/health.py
  - infra/clickhouse/migrations/V002__serving_warehouse.sql
  - scripts/verify_cutover_stack.py
  - README.md
  - tests/test_lifecycle_jobs.py
  - tests/test_platform_audit.py
  - tests/test_clickhouse_ingest.py
  - tests/test_full_backfill.py
  - tests/test_feature_marts.py
  - tests/test_cutover_smoke.py
key_decisions:
  - Archive transient PostgreSQL control-plane history before pruning it, keep ClickHouse bounded with explicit TTL reassertion, and expose the resulting storage posture through `platform-lifecycle`.
  - Consolidate reconciliation, lag, lifecycle drift, and backfill posture into one `platform-audit` contract that is shared by CLI, runtime, and health surfaces.
  - Carry pagination and chunk metadata through replay manifests, and emit follow-up-miss transitions only on the final chunk of a terminal catalog page so derived change facts stay truthful.
  - Expose AI-ready exports as stable ClickHouse marts plus grouped evidence packs with manifest/window/run traceability rather than forcing downstream consumers to rescan raw fact tables.
  - Use `scripts/verify_cutover_stack.py` as the authoritative post-cutover acceptance proof and require platform-audit posture, fresh change facts, evidence drill-down, and route parity in that proof.
patterns_established:
  - Bound platform storage by responsibility: ClickHouse raw/rollup history uses TTL, PostgreSQL keeps only transient control-plane history long enough to archive and prune, and object storage holds durable raw evidence plus lifecycle-governed archives.
  - Mirror one audit contract into CLI, runtime, and health surfaces instead of asking operators to correlate reconciliation, checkpoints, lifecycle posture, and backfill state by hand.
  - Treat replay chunk metadata as part of the truth contract for change-fact derivation; historical backfill must know when a catalog page is terminal before emitting missing-from-scan transitions.
  - Publish downstream-ready analytical surfaces as stable marts and evidence packs that always carry explicit manifest/window/run traceability.
  - Make the final operator proof validate warehouse freshness and evidence drill-down, not just platform liveness and HTTP route reachability.
observability_surfaces:
  - `platform-lifecycle` CLI/report surface for ClickHouse TTL posture, PostgreSQL archive/prune posture, and object-store lifecycle classes.
  - `platform-audit` CLI surface summarizing reconciliation, current-state lag, analytical lag, lifecycle posture, and backfill posture.
  - Mirrored `platform_audit` summary in runtime payloads and `/health`.
  - `feature-marts` export surface with manifest ids, source event ids, run ids, and concrete `evidence-inspect` drill-down examples.
  - Expanded `scripts/verify_cutover_stack.py` acceptance proof covering platform-audit posture, fresh change facts, evidence-pack drill-down, object storage evidence, and ClickHouse route parity.
drill_down_paths:
  - .gsd/milestones/M002/slices/S15/tasks/T01-SUMMARY.md
  - .gsd/milestones/M002/slices/S15/tasks/T02-SUMMARY.md
  - .gsd/milestones/M002/slices/S15/tasks/T03-SUMMARY.md
  - .gsd/milestones/M002/slices/S15/tasks/T04-SUMMARY.md
  - .gsd/milestones/M002/slices/S15/tasks/T05-SUMMARY.md
  - .gsd/milestones/M002/slices/S15/tasks/T06-SUMMARY.md
duration: ""
verification_result: passed
completed_at: 2026-03-31T16:18:54.484Z
blocker_discovered: false
---

# S15: Retention, Reconciliation, and AI-Ready Feature Marts

**S15 closed M002's platform migration with bounded-storage lifecycle controls, unified audit/reconciliation visibility, truthful ClickHouse change-fact replay, AI-ready feature marts and evidence packs, and a stronger end-to-end acceptance proof.**

## What Happened

S15 turned the post-cutover platform from merely functional into something operators and future AI work can trust. T01 added `platform-lifecycle`, which reasserts ClickHouse TTL, archives transient PostgreSQL control-plane history before pruning it, and reports explicit object-store retention posture instead of leaving bounded storage implicit. T02 added `platform-audit`, a single contract that composes reconciliation status, PostgreSQL current-state lag, ClickHouse analytical lag, lifecycle dry-run posture, and backfill checkpoint posture, then mirrors that summary into runtime and health payloads.

Mid-slice, T03 stopped the original mart implementation after proving a real contract gap: ClickHouse change tables existed in schema, but the active cutover pipeline never populated them. Rather than ship price-change and state-transition marts as query-time approximations, the slice replanned around repairing the pipeline first. T04 carried terminal-page chunk metadata through historical replay and made ClickHouse ingest derive truthful change facts from seen/probe history. With that missing source repaired, T05 shipped the intended listing-day, segment-day, price-change, state-transition, and evidence-pack exports as ClickHouse-backed downstream surfaces with manifest/window/run traceability. T06 then promoted `scripts/verify_cutover_stack.py` from a generic smoke script into the authoritative operator acceptance artifact by requiring healthy platform-audit posture, fresh change facts, evidence-pack drill-down, and ClickHouse-vs-SQLite route parity.

## Operational Readiness (Q8)
- **Health signal:** `platform-lifecycle --dry-run` reports bounded posture without failed sections, `platform-audit` reports reconciliation `match` with healthy/active current-state and analytical paths, runtime/health payloads expose the same `platform_audit` snapshot, and `scripts/verify_cutover_stack.py` proves doctor health, settled ingest, fresh change facts, evidence drill-down, and route parity together.
- **Failure signal:** lifecycle sections report `failed`, `platform-audit` drifts away from reconciliation `match`, current-state/analytical paths fall to `lagging`/`failed`, feature-mart exports stop carrying fresh change rows or trace IDs, or `verify_cutover_stack.py` reports parity or evidence failures.
- **Recovery procedure:** investigate `platform-audit` first to isolate whether drift is in reconciliation, ingest, lifecycle, or backfill posture; rerun `platform-lifecycle --dry-run` before `--apply`; if change facts or route parity regress, rerun ClickHouse ingest/backfill repair before trusting marts; before live rollout or milestone closeout, rerun `scripts/verify_cutover_stack.py` in the target environment.
- **Monitoring gaps:** the full live cutover smoke remains Docker-gated in shells without Docker, and lifecycle/audit enforcement is exposed as explicit operator commands rather than scheduled automation in this slice.

## Verification

Slice-plan verification was rerun from this shell with the following results:
- `python3 -m pytest tests/test_lifecycle_jobs.py -q` → **3 passed**
- `python3 -m pytest tests/test_platform_audit.py -q` → **3 passed**
- `python3 -m pytest tests/test_clickhouse_ingest.py tests/test_full_backfill.py -q` → **10 passed**
- `python3 -m pytest tests/test_feature_marts.py -q` → **3 passed**
- `python3 -m pytest tests/test_platform_audit.py tests/test_cutover_smoke.py -q` → **3 passed, 1 skipped** (`docker` unavailable in this shell, so the live-stack branch skipped cleanly)

Observability/diagnostic surfaces were explicitly confirmed through those checks: `tests/test_lifecycle_jobs.py` exercises `platform-lifecycle` reporting plus TTL/archive/prune behavior, `tests/test_platform_audit.py` exercises `platform-audit` JSON and runtime/health payload propagation, and `tests/test_cutover_smoke.py` exercises the expanded `verify_cutover_stack.py` acceptance proof contract.

## Requirements Advanced

- R014 — Delivered AI-ready feature marts and evidence packs that keep future insights grounded in observed windows, manifest ids, and run traceability instead of raw-event rescans.
- R015 — Created structured analytical exports that a future AI-assisted exploration surface can query and drill back to evidence without inventing an entirely new storage boundary.
- R016 — Added bounded-storage lifecycle controls, unified audit posture, and a stronger operator acceptance proof that materially harden the platform for later SaaS-style operations.

## Requirements Validated

None.

## New Requirements Surfaced

None.

## Requirements Invalidated or Re-scoped

None.

## Deviations

The original T03 mart implementation was blocked because the warehouse schema advertised change tables that the cutover pipeline did not actually populate. Instead of shipping an approximation, the slice replanned into T04 (repair change-fact replay), T05 (ship marts on top of populated change facts), and T06 (strengthen acceptance proof). Local verification used `python3` instead of `python` because this workstation does not expose a `python` launcher. The Docker-backed live-smoke branch of `tests/test_cutover_smoke.py` skipped cleanly in this shell because no `docker` binary is available.

## Known Limitations

The full container-backed acceptance proof still needs a Docker-capable environment for a non-skipped run. `platform-lifecycle` and `platform-audit` now provide the right bounded-storage and trust surfaces, but regular scheduling/alerting of those commands remains an operator automation concern outside this slice. The new marts are AI-ready inputs; M003 still needs to turn them into actual grounded AI product behavior.

## Follow-ups

Before milestone validation or any real rollout, run `scripts/verify_cutover_stack.py` in a Docker-capable CI/VPS environment. If continuous enforcement is desired, wire `platform-lifecycle --apply` and `platform-audit` into scheduled automation and alerting. Future M003 grounded-intelligence work should consume the new feature-mart and evidence-pack contracts instead of rescanning raw ClickHouse facts.

## Files Created/Modified

- `vinted_radar/services/lifecycle.py` — Implements lifecycle jobs for ClickHouse TTL enforcement, PostgreSQL archive/prune behavior, and object-store lifecycle posture reporting.
- `vinted_radar/services/platform_audit.py` — Builds the unified audit report that composes reconciliation, lag, lifecycle, and backfill posture.
- `vinted_radar/platform/clickhouse_ingest.py` — Repairs replay-time change-fact derivation so price/state change marts have truthful populated inputs.
- `vinted_radar/services/full_backfill.py` — Carries terminal-page chunk metadata through replay manifests so missing-from-scan transitions are derived safely during backfill.
- `vinted_radar/query/feature_marts.py` — Adds ClickHouse-backed listing-day, segment-day, price-change, state-transition, and evidence-pack exports.
- `vinted_radar/query/overview_clickhouse.py` — Exposes the new feature-mart export contract through the ClickHouse product query adapter.
- `vinted_radar/cli.py` — Adds operator-facing `platform-lifecycle`, `platform-audit`, and `feature-marts` surfaces and wires them into the existing CLI.
- `vinted_radar/platform/health.py` — Mirrors the new audit and lifecycle posture into runtime/health-facing diagnostics.
- `infra/clickhouse/migrations/V002__serving_warehouse.sql` — Defines the stable ClickHouse mart views used by downstream feature-mart exports.
- `scripts/verify_cutover_stack.py` — Extends final acceptance proof to require platform-audit posture, fresh change facts, evidence-pack drill-down, and route parity.
- `README.md` — Documents the richer acceptance proof and operator-facing lifecycle/audit contract.
- `tests/test_lifecycle_jobs.py` — Regression coverage for lifecycle config, CLI rendering, TTL enforcement, archive/prune behavior, and object-store lifecycle rules.
- `tests/test_platform_audit.py` — Regression coverage for audit aggregation, CLI JSON output, and runtime/health payload propagation.
- `tests/test_clickhouse_ingest.py` — Regression coverage for replay-safe primary fact dedupe and derived change-fact insertion.
- `tests/test_full_backfill.py` — Regression coverage for terminal-chunk-aware replay manifests used during historical backfill.
- `tests/test_feature_marts.py` — Regression coverage for mart exports, evidence packs, traceability, and CLI JSON output.
- `tests/test_cutover_smoke.py` — Acceptance coverage for the expanded end-to-end cutover verifier.
