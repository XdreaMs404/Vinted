# S12: PostgreSQL Control Plane + Current-State Projection — UAT

**Milestone:** M002
**Written:** 2026-03-31T06:18:58.559Z

## UAT Type

- UAT mode: artifact-driven
- Why this mode is sufficient: S12 is primarily a platform/runtime slice. The highest-value acceptance proof is a focused regression pack plus a prompt-generation smoke that verifies the project can continue dispatching auto-mode task units safely after the T04 recovery failure.

## Preconditions

- Python dependencies from `pyproject.toml` are installed.
- Node is available locally for the prompt-generation smoke.
- Run from the project root.
- No live PostgreSQL/ClickHouse stack is required for this UAT because the slice proof uses the repo’s focused unit/integration coverage and temporary SQLite fixtures.

## Smoke Test

1. Run `python3 -m pytest tests/test_runtime_cli.py tests/test_runtime_service.py tests/test_postgres_backfill.py -q`.
2. Confirm the suite exits `0`.
3. **Expected:** PostgreSQL control-plane CLI behavior, external-control-plane runtime execution, and mutable-truth backfill coverage all pass together.

## Test Cases

### 1. PostgreSQL mutable-truth schema and baseline wiring

1. Run `python3 -m pytest tests/test_postgres_schema.py tests/test_platform_config.py tests/test_data_platform_bootstrap.py -q`.
2. Wait for the command to finish.
3. **Expected:** The suite exits `0`, proving schema V003 expectations, platform config wiring, and bootstrap/doctor assumptions all match the S12 mutable-truth contract.

### 2. Runtime control-plane cutover under the polyglot-read path

1. Run `python3 -m pytest tests/test_runtime_cli.py -q`.
2. Review the polyglot-read runtime-status and pause/resume coverage.
3. **Expected:** The suite exits `0`, and the PostgreSQL-backed runtime-status / runtime-pause / runtime-resume paths remain green.

### 3. Backfill plus no-SQLite-fallback smoke

1. Run `python3 -m pytest tests/test_postgres_backfill.py tests/test_runtime_service.py -q`.
2. Confirm the backfill coverage passes.
3. Confirm the external-control-plane runtime smoke passes.
4. **Expected:** The suite exits `0`, and the runtime smoke proves SQLite `runtime_cycles` and `runtime_controller_state` stay empty when runtime truth is redirected to the injected external control-plane repository.

## Edge Cases

### Auto-mode prompt regeneration after the T04 recovery incident

1. Run:
   `node --input-type=module - <<'JS'
   import { buildExecuteTaskPrompt } from '/home/utilisateur/.gsd/agent/extensions/gsd/auto-prompts.js';
   const prompt = await buildExecuteTaskPrompt('M002','S13','ClickHouse Serving Warehouse + Rollups','T01','ClickHouse fact + rollup schema','/home/utilisateur/Vinted');
   if (!prompt.includes('## Output Templates')) throw new Error('missing Output Templates block');
   if (!prompt.includes('### Output Template: Task Summary')) throw new Error('missing Task Summary inline template');
   if (prompt.includes('~/.gsd/agent/extensions/gsd/templates')) throw new Error('stale tilde template path still present');
   console.log('execute-task-prompt-inline-ok');
   JS`
2. **Expected:** The command prints `execute-task-prompt-inline-ok` and exits `0`.

## Failure Signals

- Any failure in `tests/test_runtime_cli.py`, `tests/test_runtime_service.py`, or `tests/test_postgres_backfill.py`.
- A regenerated `execute-task` prompt that lacks the inline Task Summary block or still emits the stale user-home template path.
- Runtime smoke coverage that starts writing rows back into SQLite `runtime_cycles` or `runtime_controller_state` when an external control-plane repository is injected.

## Requirements Proved By This UAT

- R010 — proves the runtime operator contract still works while the control plane is redirected onto PostgreSQL mutable truth.
- R016 — proves the first bounded mutable-truth/control-plane platform cutover is real, observable, and guarded against silent fallback.

## Not Proven By This UAT

- S13 ClickHouse serving marts or analytical parity.
- S14 historical end-to-end cutover from SQLite into PostgreSQL, ClickHouse, and the Parquet lake.
- Overview/explorer/detail application reads from PostgreSQL or ClickHouse on a live stack.
- VPS/live-environment acceptance on the post-S12 platform path.

## Notes for Tester

- This slice is intentionally infrastructure-heavy. Favor the focused regression commands above over ad-hoc product browsing.
- The project-level `.gsd/OVERRIDES.md` is expected to remain active so future auto task prompts prefer their inlined templates.
