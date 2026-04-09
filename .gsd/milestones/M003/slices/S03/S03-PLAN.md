# S03: Market-Aware Identity + Domain Adapters

**Goal:** Introduce market-aware request, identity, and storage boundaries so the collector can scale beyond `vinted.fr` without mixing data or corrupting existing FR truth.
**Demo:** After this: After this: the collector can ingest more than one Vinted market domain into separated market partitions without ID collisions, mixed catalogs, or ambiguous diagnostics, while existing FR reads remain truthful.

## Tasks
- [ ] **T01: Add a market registry and domain adapter layer** — Why: Multi-market work is unsafe until base URLs, headers, and seed discovery are controlled through one contract.
Do:
- Add a market registry/domain adapter layer describing catalog roots, domain URLs, locale headers, and operator-visible market codes.
- Refactor discovery and HTTP entrypoints to consume that registry instead of embedding `vinted.fr` constants in multiple places.
- Keep FR as the default market so existing scripts still have a safe fallback.
Done when:
- Discovery and HTTP tests can build requests for more than one supported market domain from one explicit registry.
  - Estimate: 1.5h
  - Files: vinted_radar/markets.py, vinted_radar/services/discovery.py, vinted_radar/http.py, tests/test_market_registry.py
  - Verify: python -m pytest tests/test_market_registry.py tests/test_http.py -q
- [ ] **T02: Make storage and identity contracts market-aware** — Why: The data model currently assumes one market and can silently collide when another domain reuses IDs or similar URLs.
Do:
- Make hot-path identity and persisted history market-aware in SQLite/current-state paths and the platform projections that acquisition/runtime depend on.
- Add compatibility/backfill logic so existing FR data stays readable and does not require destructive reset unless explicitly chosen.
- Update key uniqueness, foreign keys, and query helpers carefully; treat this as a correctness slice before it is a throughput slice.
Done when:
- Storage-level tests prove market separation and FR compatibility together.
  - Estimate: 2.5h
  - Files: vinted_radar/db.py, vinted_radar/repository.py, vinted_radar/platform/postgres_schema/__init__.py, vinted_radar/platform/clickhouse_schema/__init__.py, tests/test_repository_market_partitioning.py, tests/test_clickhouse_parity.py
  - Verify: python -m pytest tests/test_repository_market_partitioning.py tests/test_postgres_backfill.py tests/test_clickhouse_parity.py -q
- [ ] **T03: Expose market-aware diagnostics without breaking FR defaults** — Why: Operators and product surfaces need to understand which market a run or listing belongs to once multiple domains exist.
Do:
- Extend CLI/runtime/product query surfaces with market filters and diagnostics where needed.
- Preserve a French-first default product surface while making cross-market operation inspectable for operators and benchmark artifacts.
- Ensure benchmark, runtime, and error payloads always carry market identity.
Done when:
- Existing FR flows still work by default and market-specific flows are inspectable through automated tests.
  - Estimate: 1.5h
  - Files: vinted_radar/cli.py, vinted_radar/dashboard.py, vinted_radar/query/overview_clickhouse.py, tests/test_runtime_cli.py, tests/test_dashboard.py
  - Verify: python -m pytest tests/test_runtime_cli.py tests/test_dashboard.py tests/test_clickhouse_queries.py -q
- [ ] **T04: Run a real cross-market smoke benchmark on the VPS** — Why: The slice only retires once cross-market ingestion runs on the real VPS.
Do:
- Benchmark a conservative cross-market smoke profile on the VPS (FR + one additional market) using the new registry and identity contracts.
- Verify that artifacts, runtime surfaces, and stored data stay partitioned by market.
- Record additive yield and any domain-specific failures for later transport/frontier work.
Done when:
- The milestone has a real VPS artifact showing safe multi-market ingestion without identity mixing.
  - Estimate: 1h
  - Files: scripts/run_vps_benchmark.py, .gsd/milestones/M003/benchmarks/
  - Verify: python scripts/run_vps_benchmark.py --host 46.225.113.129 --profile cross-market-smoke --duration-minutes 60 --output .gsd/milestones/M003/benchmarks/cross-market-smoke.json --markdown .gsd/milestones/M003/benchmarks/cross-market-smoke.md
