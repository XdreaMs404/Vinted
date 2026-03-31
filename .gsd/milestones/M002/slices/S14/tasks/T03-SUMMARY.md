---
id: T03
parent: S14
milestone: M002
provides: []
requires: []
affects: []
key_files: ["vinted_radar/query/overview_clickhouse.py", "vinted_radar/dashboard.py", "vinted_radar/cli.py", "vinted_radar/services/discovery.py", "vinted_radar/services/state_refresh.py", "tests/test_dashboard.py", "tests/test_state_refresh_service.py", "tests/test_runtime_cli.py"]
key_decisions: ["Keep ClickHouse as the analytics backend but inject a separate PostgreSQL control-plane repository into the product query adapter for runtime and controller surfaces.", "Treat PostgreSQL write activation as sufficient to move runtime control-plane commands onto PostgreSQL even before full polyglot reads are enabled.", "Project state-refresh probe rows directly into PostgreSQL mutable truth instead of waiting for outbox replay so live item-state truth stays current during cutover."]
patterns_established: []
drill_down_paths: []
observability_surfaces: []
duration: ""
verification_result: "Ran `python3 -m pytest tests/test_dashboard.py tests/test_runtime_service.py tests/test_state_refresh_service.py tests/test_runtime_cli.py -q` and it passed all 40 tests. The run proved the task’s required dashboard/runtime behavior plus the new dashboard control-plane regression, direct mutable-truth probe projection, and PostgreSQL runtime control-plane injection when platform writes are enabled."
completed_at: 2026-03-31T13:32:24.406Z
blocker_discovered: false
---

# T03: Cut dashboard, runtime, CLI read paths, and live mutable-truth writes over to the PostgreSQL + ClickHouse platform stack with SQLite kept only as a fallback.

> Cut dashboard, runtime, CLI read paths, and live mutable-truth writes over to the PostgreSQL + ClickHouse platform stack with SQLite kept only as a fallback.

## What Happened
---
id: T03
parent: S14
milestone: M002
key_files:
  - vinted_radar/query/overview_clickhouse.py
  - vinted_radar/dashboard.py
  - vinted_radar/cli.py
  - vinted_radar/services/discovery.py
  - vinted_radar/services/state_refresh.py
  - tests/test_dashboard.py
  - tests/test_state_refresh_service.py
  - tests/test_runtime_cli.py
key_decisions:
  - Keep ClickHouse as the analytics backend but inject a separate PostgreSQL control-plane repository into the product query adapter for runtime and controller surfaces.
  - Treat PostgreSQL write activation as sufficient to move runtime control-plane commands onto PostgreSQL even before full polyglot reads are enabled.
  - Project state-refresh probe rows directly into PostgreSQL mutable truth instead of waiting for outbox replay so live item-state truth stays current during cutover.
duration: ""
verification_result: passed
completed_at: 2026-03-31T13:32:24.406Z
blocker_discovered: false
---

# T03: Cut dashboard, runtime, CLI read paths, and live mutable-truth writes over to the PostgreSQL + ClickHouse platform stack with SQLite kept only as a fallback.

**Cut dashboard, runtime, CLI read paths, and live mutable-truth writes over to the PostgreSQL + ClickHouse platform stack with SQLite kept only as a fallback.**

## What Happened

Finished the real application cutover instead of leaving only resume notes. Discovery now opens PostgreSQL mutable-truth projection whenever the platform path is active, and state refresh now projects probe rows directly into PostgreSQL while still emitting evidence batches. The ClickHouse product adapter now accepts a separate PostgreSQL control-plane repository so dashboard and CLI polyglot reads can keep ClickHouse for analytics/state-history while reading runtime/controller truth from PostgreSQL. Dashboard polyglot routes now thread that control-plane repository through /api/dashboard, /api/runtime, /runtime, and /health. CLI runtime commands now move to PostgreSQL whenever PostgreSQL writes are enabled, and the operator read commands that still bypassed the cutover stack now open the polyglot backend as well. Added focused regressions for dashboard control-plane reads, state-refresh mutable-truth projection, and runtime CLI control-plane injection.

## Verification

Ran `python3 -m pytest tests/test_dashboard.py tests/test_runtime_service.py tests/test_state_refresh_service.py tests/test_runtime_cli.py -q` and it passed all 40 tests. The run proved the task’s required dashboard/runtime behavior plus the new dashboard control-plane regression, direct mutable-truth probe projection, and PostgreSQL runtime control-plane injection when platform writes are enabled.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `python3 -m pytest tests/test_dashboard.py tests/test_runtime_service.py tests/test_state_refresh_service.py tests/test_runtime_cli.py -q` | 0 | ✅ pass | 1780ms |


## Deviations

Expanded verification beyond the task-plan minimum to include tests/test_state_refresh_service.py and tests/test_runtime_cli.py because the cutover changed live probe projection and runtime command wiring in addition to dashboard/runtime payloads. Also used python3 instead of python because the local shell exposes python3.

## Known Issues

None.

## Files Created/Modified

- `vinted_radar/query/overview_clickhouse.py`
- `vinted_radar/dashboard.py`
- `vinted_radar/cli.py`
- `vinted_radar/services/discovery.py`
- `vinted_radar/services/state_refresh.py`
- `tests/test_dashboard.py`
- `tests/test_state_refresh_service.py`
- `tests/test_runtime_cli.py`


## Deviations
Expanded verification beyond the task-plan minimum to include tests/test_state_refresh_service.py and tests/test_runtime_cli.py because the cutover changed live probe projection and runtime command wiring in addition to dashboard/runtime payloads. Also used python3 instead of python because the local shell exposes python3.

## Known Issues
None.
