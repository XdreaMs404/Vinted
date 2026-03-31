# S15: Retention, Reconciliation, and AI-Ready Feature Marts — UAT

**Milestone:** M002
**Written:** 2026-03-31T16:18:54.484Z

# S15: Retention, Reconciliation, and AI-Ready Feature Marts — UAT

**Milestone:** M002
**Written:** 2026-03-31T12:52:10+02:00

# S15 UAT — Retention, Reconciliation, and AI-Ready Feature Marts

## Objective
Prove that the cut-over platform stays bounded and auditable day to day, derives truthful change facts during replay/backfill, exposes AI-ready marts with evidence drill-down, and closes with a stronger operator acceptance proof.

## Acceptance checks
1. **Lifecycle posture:** `python3 -m pytest tests/test_lifecycle_jobs.py -q`
   - Expected: ClickHouse TTL enforcement, PostgreSQL archive/prune behavior, object-store lifecycle classes, and `platform-lifecycle` rendering all pass.
2. **Audit surface:** `python3 -m pytest tests/test_platform_audit.py -q`
   - Expected: `platform-audit` aggregates reconciliation, current-state lag, analytical lag, lifecycle posture, and backfill posture, then mirrors that summary into runtime and health payloads.
3. **Truthful change-fact replay:** `python3 -m pytest tests/test_clickhouse_ingest.py tests/test_full_backfill.py -q`
   - Expected: replay-safe ingest/backfill derives populated price/state change facts and respects terminal-page chunk semantics.
4. **AI-ready marts and evidence packs:** `python3 -m pytest tests/test_feature_marts.py -q`
   - Expected: listing-day, segment-day, price-change, state-transition, and evidence-pack exports are populated and traceable.
5. **Final acceptance proof:** `python3 -m pytest tests/test_platform_audit.py tests/test_cutover_smoke.py -q`
   - Expected: platform audit, feature-mart freshness, evidence-pack drill-down, and route parity proof pass; Docker-gated live smoke may skip cleanly in shells without Docker.

## Result
**Pass with environment note.** All slice-plan verification checks passed in this shell. The only environment caveat is the Docker-backed portion of `tests/test_cutover_smoke.py`, which skipped cleanly because this shell does not expose a `docker` binary.

## Operator notes
- `platform-lifecycle --dry-run` is the storage-posture view; `--apply` is the bounded-storage action path.
- `platform-audit` is the day-to-day trust surface and is also mirrored into runtime/health payloads.
- `feature-marts --format json` is the stable downstream export for listing-day, segment-day, price-change, state-transition, and evidence-pack consumers.
- `scripts/verify_cutover_stack.py` is the authoritative acceptance artifact before live rollout, milestone validation, or future grounded-AI work built on these marts.
