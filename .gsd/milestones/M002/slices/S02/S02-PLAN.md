# S02: Runtime Truth + Pause/Resume Surface

**Goal:** Make runtime truth first-class persisted product data so the radar can truthfully show running, scheduled, paused, failed, elapsed pause time, next resume timing, and recent errors across the CLI, API, overview home, and a dedicated `/runtime` page on the same SQLite DB.
**Demo:** Start `python -m vinted_radar.cli continuous --db data/vinted-radar-s02.db --page-limit 1 --max-leaf-categories 1 --state-refresh-limit 2 --interval-seconds 5 --request-delay 0.0 --dashboard --host 127.0.0.1 --port 8781`, use `python -m vinted_radar.cli runtime-pause --db data/vinted-radar-s02.db` and `python -m vinted_radar.cli runtime-resume --db data/vinted-radar-s02.db`, then verify `python -m vinted_radar.cli runtime-status --db data/vinted-radar-s02.db --format json`, `http://127.0.0.1:8781/runtime`, `http://127.0.0.1:8781/api/runtime`, and `http://127.0.0.1:8781/` all agree on controller-backed scheduled/paused/running/failed truth from SQLite instead of the last cycle row.

## Must-Haves

- Persist current runtime-controller truth separately from immutable `runtime_cycles`, using a dedicated `runtime_controller_state` snapshot that can represent status, phase, heartbeat/update time, paused-at, next-resume-at, and last-error truth without muddying cycle history.
- Make continuous orchestration and operator controls use the same DB-backed runtime contract so scheduled windows are persisted between cycles, pause/resume is cooperative and observable before the full interval elapses, and runtime truth stays explicit about degraded or failed states in support of R011 and the already-validated R004 honesty posture.
- Ship the runtime surface through real product entrypoints by adding `/runtime`, extending `/api/runtime`, and updating the overview freshness/runtime copy so M002/S02 advances the roadmap’s runtime-truth ownership for R010 on the same live SQLite boundary.

## Proof Level

- This slice proves: operational
- Real runtime required: yes
- Human/UAT required: yes

## Verification

- `python -m pytest tests/test_runtime_repository.py tests/test_runtime_service.py tests/test_runtime_cli.py tests/test_dashboard.py tests/test_dashboard_cli.py tests/test_db_recovery.py`
- `python -m vinted_radar.cli dashboard --db data/vinted-radar-s01.db --host 127.0.0.1 --port 8781`
- Local operator smoke: run `python -m vinted_radar.cli continuous --db data/vinted-radar-s02.db --page-limit 1 --max-leaf-categories 1 --state-refresh-limit 2 --interval-seconds 5 --request-delay 0.0 --dashboard --host 127.0.0.1 --port 8781`, issue `runtime-pause` and `runtime-resume` from a second terminal, then confirm `/runtime`, `/api/runtime`, `/`, `/health`, and `runtime-status --format json` agree on scheduled vs paused vs running vs failed truth, next resume timing, elapsed pause, and recent errors.

## Observability / Diagnostics

- Runtime signals: persisted controller status/phase, `updated_at` heartbeat, `paused_at`, `next_resume_at`, latest cycle outcome, and recent runtime errors.
- Inspection surfaces: `python -m vinted_radar.cli runtime-status --db ...`, `/runtime`, `/api/runtime`, `/health`, `tests/test_runtime_repository.py`, and the SQLite `runtime_controller_state` plus `runtime_cycles` tables.
- Failure visibility: controller staleness, last error, recent failure history, and the distinction between a healthy scheduled wait and an actually failed or paused runtime remain inspectable from the DB and UI.
- Redaction constraints: keep secrets and proxy credentials out of persisted runtime payloads, CLI output, HTML, and JSON diagnostics.

## Integration Closure

- Upstream surfaces consumed: `vinted_radar/repository.py`, `vinted_radar/services/runtime.py`, `vinted_radar/cli.py`, `vinted_radar/dashboard.py`, S01’s `overview_snapshot()` freshness cues, and the existing SQLite runtime/history tables.
- New wiring introduced in this slice: repository-owned controller snapshot contract, cooperative scheduler pause/resume loop, CLI control commands, `/runtime` SSR/API payloads, and overview-home runtime wording that now reads controller truth.
- What remains before the milestone is truly usable end-to-end: S03 still needs the responsive French VPS shell, S06 still needs degraded acquisition hardening on top of the runtime truth, and S07 still needs live remote acceptance closure.

## Tasks

- [ ] **T01: Persist the runtime-controller snapshot and repository contract** `est:1h30m`
  - Why: S02 cannot truthfully show scheduled, paused, next-resume, or elapsed-pause state until SQLite can represent current controller truth separately from per-cycle history, and that new truth must survive health/recovery tooling.
  - Files: `vinted_radar/db.py`, `vinted_radar/repository.py`, `vinted_radar/db_health.py`, `vinted_radar/db_recovery.py`, `tests/test_runtime_repository.py`, `tests/test_db_recovery.py`
  - Do: add a dedicated `runtime_controller_state` snapshot/table plus any brownfield-safe migration/backfill needed; extend the repository-owned runtime payload to return controller state, computed elapsed pause/next resume/heartbeat staleness, recent failures, and compatibility cycle keys; update DB health/recovery so the new runtime truth remains a first-class critical table.
  - Verify: `python -m pytest tests/test_runtime_repository.py tests/test_db_recovery.py`
  - Done when: SQLite alone can answer “what is the runtime doing now?” and copied/recovered databases keep that controller truth instead of dropping it.
- [ ] **T02: Make continuous runtime and CLI controls honor the persisted controller truth** `est:1h30m`
  - Why: The slice’s main operability claim only becomes real when continuous mode persists scheduled windows, observes pause/resume requests quickly, and the operator CLI reads and writes the same controller contract.
  - Files: `vinted_radar/services/runtime.py`, `vinted_radar/cli.py`, `vinted_radar/repository.py`, `tests/test_runtime_service.py`, `tests/test_runtime_cli.py`
  - Do: replace the one-shot interval sleep with a cooperative polling/heartbeat wait loop that persists running/scheduled/paused/failed transitions; add pause/resume commands and richer runtime-status output on top of the repository contract; keep failure state explicit without conflating the latest cycle result with the current controller state.
  - Verify: `python -m pytest tests/test_runtime_service.py tests/test_runtime_cli.py`
  - Done when: pause can be observed before the full interval elapses, resume re-establishes scheduling truthfully, and CLI status/control surfaces show controller truth plus recent cycle evidence from the DB.
- [ ] **T03: Expose runtime truth through `/runtime`, `/api/runtime`, and the overview shell** `est:1h15m`
  - Why: R010 and the slice demo only land for the product when the same persisted runtime truth becomes visible on the real dashboard surfaces, not just through repository tests or CLI tables.
  - Files: `vinted_radar/dashboard.py`, `vinted_radar/cli.py`, `README.md`, `tests/test_dashboard.py`, `tests/test_dashboard_cli.py`
  - Do: add a dedicated French-first `/runtime` page and payload builder on top of the repository contract, extend `/api/runtime` without breaking compatibility keys, update overview/runtime copy and dashboard CLI URL output to point at `/runtime`, and document paused/scheduled/next-resume semantics.
  - Verify: `python -m pytest tests/test_dashboard.py tests/test_dashboard_cli.py`
  - Done when: `/runtime`, `/api/runtime`, `/`, and local dashboard command output all reflect the same persisted controller truth and a healthy waiting radar is shown as scheduled rather than “completed”.

## Files Likely Touched

- `vinted_radar/db.py`
- `vinted_radar/repository.py`
- `vinted_radar/services/runtime.py`
- `vinted_radar/cli.py`
- `vinted_radar/dashboard.py`
- `vinted_radar/db_health.py`
- `vinted_radar/db_recovery.py`
- `tests/test_runtime_repository.py`
- `tests/test_runtime_service.py`
- `tests/test_runtime_cli.py`
- `tests/test_dashboard.py`
- `tests/test_dashboard_cli.py`
- `tests/test_db_recovery.py`
- `README.md`
