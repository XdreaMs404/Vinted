# S02 — Research

**Date:** 2026-03-22

## Summary

S02 primarily owns **R010** and directly supports **R004** and **R011**.

The runtime gap is real and structural, not cosmetic:

- `vinted_radar/db.py:142` defines **only one runtime table**, `runtime_cycles`.
- `vinted_radar/repository.py:463` exposes runtime truth as **latest cycle + recent cycle history + totals**.
- `vinted_radar/services/runtime.py:179-208` runs continuous mode as **cycle → callback → one blocking `sleep_fn(interval_seconds)`**.
- `vinted_radar/dashboard.py:164` exposes **`/api/runtime` only**; there is **no `/runtime` HTML page**.
- `vinted_radar/cli.py:56`, `:112`, `:176` expose `batch`, `continuous`, and `runtime-status`, but there are **no pause/resume commands**.
- `install_services.sh:54,76` runs the scraper and dashboard as **separate systemd services**, which means the dashboard cannot inspect in-memory scheduler state even on the VPS.

That combination means the product cannot truthfully represent the most important continuous-runtime states:

- **scheduled**: between cycles, the DB only shows the last completed/failed cycle
- **paused**: there is no persisted pause request or pause-start timestamp anywhere
- **next resume timing**: there is no persisted `next_resume_at`
- **elapsed pause time**: there is no persisted `paused_at`
- **recent operator events** beyond cycle failures: there is no control/event model

The slice therefore needs to build a **persisted runtime-controller contract first**, then wire the CLI/API/UI to it.

## Requirement focus

### Primary: R010 — operability

S02 is the slice that must make runtime truth first-class on the same SQLite boundary as the rest of the product. Right now the code only persists **cycle history**, not **current controller/scheduler state**.

### Supporting: R004 — visible truthfulness

The overview home already shows runtime freshness cues, but it currently does so via `latest_cycle.status`. Once S02 introduces `scheduled` / `paused`, the home must stop equating “latest cycle completed” with “runtime is completed”. Otherwise the home will lie under normal continuous operation.

### Supporting: R011 — honest degraded / partial states

Recent failures are partly visible today through `latest_failure` and per-cycle `last_error`, but the runtime surface still cannot distinguish:

- a healthy scheduled wait
- a manual pause
- a stale/crashed process that left `running` behind
- a failed cycle that will retry vs a failed runtime that is halted

S02 needs explicit persisted state so degraded runtime truth remains honest instead of inferred.

## Current verification baseline

Targeted runtime/dashboard regression tests are currently green:

```bash
python -m pytest -q tests/test_runtime_service.py tests/test_runtime_cli.py tests/test_dashboard.py
```

Observed result during research: **11 passed**.

Current local route behavior was also checked with the seeded S01 DB:

```bash
python -m vinted_radar.cli dashboard --db data/vinted-radar-s01.db --host 127.0.0.1 --port 8781
```

HTTP probes confirmed:

- `/` → `200`
- `/api/runtime` → `200`
- `/health` → `200`
- `/runtime` → **`404`**

So the slice truly starts with **JSON-only runtime output plus a small overview card**, not a dedicated runtime page.

## Recommendation

Keep **`runtime_cycles` as immutable per-cycle history** and add a **separate persisted runtime-controller snapshot** for current continuous-loop truth.

That controller layer should own the states the milestone actually cares about:

- current/effective runtime status: `running`, `scheduled`, `paused`, `failed`, maybe `idle`
- current phase when actively running
- active cycle id / last cycle id
- interval seconds
- `next_resume_at`
- `paused_at`
- `last_error` and `last_error_at`
- `updated_at` / heartbeat
- config JSON for the active loop
- optional desired/requested operator state if pause is cooperative rather than immediate

Why a separate controller contract is the best brownfield fit:

1. **`runtime_cycles` means “one actual cycle” today.** Reusing it for `scheduled` or `paused` would muddy cycle history.
2. **New tables are cheap in this repo.** `connect_database()` always runs `executescript(SCHEMA)`, so a new table auto-appears on connect. By contrast, adding columns to `runtime_cycles` requires real migration work because `CREATE TABLE IF NOT EXISTS` will not alter an existing table.
3. **The dashboard service is a different process from the scraper service.** Persisted controller state is the only honest way for `/runtime`, `/`, `/api/runtime`, and `runtime-status` to agree.
4. **S01 already established repository-owned payload boundaries.** S02 should follow that pattern instead of teaching the UI or CLI to infer scheduler state.

The safest S02 posture is:

- **repository-owned runtime snapshot contract**
- **cooperative continuous-loop pause/schedule logic**
- **flat Typer commands for control/status**
- **new French-first `/runtime` SSR page**
- **brownfield-compatible `/api/runtime` extension**, preserving existing keys while adding richer controller fields

This follows D016 and D019, and it matches the `debug-like-expert` rule: **verify, don’t assume**. Scheduled/paused truth must come from persisted state, not from the last cycle row or from UI wording.

## What should be proven first?

### 1. Repository/runtime contract before UI

First prove a truthful repository contract that can answer, from SQLite alone:

- what the runtime is doing **now**
- when it will resume next
- whether it is paused and since when
- what the last few failures/errors were
- what the latest completed/failed cycle was

This should become the boundary consumed by:

- `runtime-status`
- `/api/runtime`
- `/runtime`
- overview freshness/runtime copy on `/`

If this contract is fuzzy, the page and CLI will drift immediately.

### 2. Continuous-loop scheduling/pause semantics before CLI polish

The current `run_continuous()` implementation uses one blocking sleep:

- `vinted_radar/services/runtime.py:208` → `self.sleep_fn(interval_seconds)`

That means even if a pause request were written into SQLite, the loop would not see it until the full interval elapsed. S02 therefore has to replace the one-shot sleep with a **polling / heartbeat wait loop** or equivalent cooperative scheduler step.

The planner should treat this as a core runtime task, not a UI detail.

### 3. Runtime page route only after API truth is stable

`vinted_radar/dashboard.py` currently has the natural page-building seams:

- route dispatch in `DashboardApplication.__call__`
- `build_dashboard_payload()`
- `build_explorer_payload()`
- `render_dashboard_html()`
- `render_explorer_html()`

The natural S02 addition is:

- `build_runtime_payload()`
- `render_runtime_html()`
- route branch for `/runtime`

But that should come **after** the repository/runtime contract is truthful.

### 4. Health/recovery fallout last

If S02 introduces a new authoritative runtime table, it must be reflected in:

- `vinted_radar/db_health.py`
- `vinted_radar/db_recovery.py`
- `tests/test_db_recovery.py`

Otherwise copied/recovered databases will silently lose the very runtime truth S02 just created.

## Implementation landscape

### `vinted_radar/db.py`

- `runtime_cycles` schema lives at `vinted_radar/db.py:142`.
- `_apply_migrations()` currently only handles listing-column backfills plus `PRAGMA user_version = 1`.
- Important constraint: **new tables are much easier than new columns** in this codebase.

### `vinted_radar/repository.py`

Existing runtime persistence/query seam:

- `start_runtime_cycle()` → `vinted_radar/repository.py:377`
- `update_runtime_cycle_phase()` → `:408`
- `complete_runtime_cycle()` → `:415`
- `runtime_status()` → `:463`

Today `runtime_status()` only returns:

- `latest_cycle`
- `recent_cycles`
- `latest_failure`
- `totals`

This is the right place to grow a **controller snapshot + recent errors + computed elapsed/scheduled fields** while keeping the old keys available for compatibility.

Also important: `overview_snapshot()` already pulls `runtime_status()` into the overview payload. So if S02 changes runtime truth, the overview home can consume it from the repository boundary instead of inventing another path.

### `vinted_radar/services/runtime.py`

This file already contains the correct orchestration ownership boundary:

- `RadarRuntimeService.run_cycle()` → `vinted_radar/services/runtime.py:74`
- `RadarRuntimeService.run_continuous()` → `:179`

Useful existing test seams:

- injected `discovery_service_factory`
- injected `state_refresh_service_factory`
- injected `sleep_fn`

That makes deterministic pause/schedule tests feasible without hitting the network or sleeping in real time.

Key current limitation:

- the service persists phase transitions during a cycle
- then it sleeps out-of-band between cycles
- so there is **no durable scheduled state window** at all

Also note: a hard crash can leave a `running` cycle behind forever because there is no heartbeat/staleness signal today.

### `vinted_radar/cli.py`

Current relevant commands:

- `batch` → `vinted_radar/cli.py:56`
- `continuous` → `:112`
- `runtime-status` → `:176`
- `dashboard` → `:653`

There is **no pause/resume command surface** today; `rg -n "pause|resume" vinted_radar/cli.py README.md install_services.sh tests/test_runtime_cli.py` returned no hits.

Important planner note: the CLI is currently **flat**, not a nested command tree. A low-churn S02 fit is likely:

- `runtime-pause`
- `runtime-resume`
- maybe `runtime-schedule` or a richer `runtime-status`

rather than a larger Typer sub-app refactor.

Also relevant:

- `dashboard --now` already exists for deterministic rendering.
- `runtime-status` currently has **no `--now`**. If elapsed-pause / next-resume values become human-readable CLI output, a deterministic clock option will make testing much easier.

### `vinted_radar/dashboard.py`

Current route map:

- `/`
- `/api/dashboard`
- `/explorer`
- `/api/explorer`
- `/api/runtime`
- `/api/listings/<id>`
- `/health`

There is **no `/runtime` route** today.

Important runtime-related spots:

- `/api/runtime` branch → `vinted_radar/dashboard.py:164`
- overview diagnostics links include only JSON runtime → `:512-516`, `:723-726`
- overview runtime panel is still a small section inside `render_dashboard_html()` → around `:760`

Natural S02 change:

- add `/runtime`
- extend diagnostics links to include it
- optionally keep `/api/runtime` query-compatible with `limit`
- update overview runtime/freshness copy to reflect controller state

Also important for deterministic testing: `DashboardApplication` already carries `now`, so runtime payload code can follow the same pattern as the existing overview/explorer payload builders.

### `install_services.sh`

Relevant lines:

- continuous scraper service → `install_services.sh:54`
- dashboard service → `install_services.sh:76`

This is a strong architectural clue: the live VPS posture is already **separate reader/writer processes over one SQLite DB**. The runtime page cannot depend on process memory or shell-local timers.

Also note the only operator control documented there today is **systemctl stop/restart**. That is outside the app and outside the DB, so the product cannot distinguish “paused intentionally” from “stopped / dead / sleeping” through its own surfaces.

### `vinted_radar/db_health.py` and `vinted_radar/db_recovery.py`

- `CRITICAL_TABLES` lives at `vinted_radar/db_health.py:7`
- recovery order mirrors it at `vinted_radar/db_recovery.py:12`

If S02 adds a new authoritative runtime-state table, this pair must be updated or database copy/recovery tooling will lag the runtime model.

### `README.md`

Relevant current docs:

- operator workflow and route list → `README.md:40-73`
- runtime diagnostics description → `README.md:79-89`

README currently documents only:

- `runtime-status`
- `/api/runtime`
- cycle-level status/phase/error fields

S02 will need to document:

- new pause/resume commands if added
- `/runtime`
- scheduled/paused/next-resume semantics
- any distinction between controller state and latest cycle state

## Surprises and constraints

### The overview home will lie unless it stops reading `latest_cycle.status`

S01 currently uses runtime cycle state in the overview freshness card. That worked when the only meaningful statuses were cycle statuses.

After S02, a healthy continuous radar will often be:

- **latest cycle = completed**
- **current controller state = scheduled**

If the home continues to render `latest_cycle.status`, it will tell the user the runtime is “completed” during normal healthy waiting windows. S02 must update the home to read controller truth.

### Web controls would be a bigger jump than they look

`DashboardApplication` is currently GET-only. If S02 wants actual pause/resume buttons in the browser, it needs the app’s first state-changing HTTP handlers.

That is possible, but it is more scope than a read-only runtime page plus CLI controls. The lower-risk S02 posture is:

- **CLI controls** for pause/resume
- **SSR runtime page** for visibility
- **JSON API** for diagnostics

### Failure state is ambiguous unless cycle failure and controller state stay separate

Continuous mode currently runs with `continue_on_error=True` from the CLI. So a failed cycle does **not necessarily mean** the runtime is halted.

The planner should avoid one overloaded “status” field that tries to mean both:

- current controller state
- latest cycle outcome

Those are distinct truths.

### Pause should probably be cooperative, not mid-request abortive

Discovery and state-refresh work span external HTTP calls and DB writes. The safest M002 shape is likely:

- if pause is requested during an active cycle, **finish the current cycle**
- then enter `paused`
- make that behavior explicit in the CLI/API/page if surfaced

That avoids having S02 turn into a request-abort / partial-cycle recovery problem.

### A heartbeat/staleness field would materially improve honesty

Current code can leave `running` behind forever if the process dies at the wrong moment. A controller snapshot with `updated_at` or a heartbeat is the cleanest way to keep “running” honest.

## Likely task split for the planner

### Task group 1 — Persistence and repository contract

Files:

- `vinted_radar/db.py`
- `vinted_radar/repository.py`
- maybe a new runtime-repository test file
- `vinted_radar/db_health.py`
- `vinted_radar/db_recovery.py`
- `tests/test_db_recovery.py`

Goal:

- add controller persistence
- expose one repository-owned runtime snapshot contract
- compute elapsed-pause / next-resume deterministically
- preserve brownfield compatibility keys where practical

### Task group 2 — Runtime orchestration and operator control

Files:

- `vinted_radar/services/runtime.py`
- `vinted_radar/cli.py`
- `tests/test_runtime_service.py`
- `tests/test_runtime_cli.py`

Goal:

- persist scheduled windows
- support pause/resume requests through the DB
- replace one-shot sleep with cooperative polling / heartbeat
- make CLI status/control consume the same runtime contract

### Task group 3 — Runtime HTML/API surface

Files:

- `vinted_radar/dashboard.py`
- `tests/test_dashboard.py`
- `tests/test_dashboard_cli.py`
- `README.md`

Goal:

- add `/runtime`
- extend `/api/runtime`
- wire overview/runtime links and summary copy
- keep the page French-first and evidence-backed

## Verification plan

### Contract verification

Add repository-level assertions for:

- controller state transitions (`running` → `scheduled` → `paused` → `scheduled` / `running`)
- `paused_at` / elapsed pause computation
- `next_resume_at` computation
- recent error selection
- compatibility keys (`latest_cycle`, `recent_cycles`, `latest_failure`, `totals`) if preserved
- deterministic `now` behavior

### Runtime service verification

Extend `tests/test_runtime_service.py` to prove:

- continuous mode persists `scheduled` between cycles
- a pause request is observed without waiting a real full interval
- resume clears pause and restarts scheduling truthfully
- cycle failures remain visible while the controller still plans the next run when appropriate

The existing injected factories and `sleep_fn` already make this practical.

### CLI verification

Extend `tests/test_runtime_cli.py` to prove:

- `runtime-status` prints the richer current-state fields
- pause/resume commands mutate the DB truth correctly
- dashboard/continuous commands print the runtime page URL if `/runtime` is added

### UI/API verification

Extend `tests/test_dashboard.py` to prove:

- `/runtime` returns `200` HTML
- `/api/runtime` returns the new runtime snapshot contract
- overview `/` shows scheduled/paused truth from the controller state, not from the last completed cycle

Recommended local smoke after implementation:

```bash
python -m vinted_radar.cli dashboard --db data/vinted-radar-s01.db --host 127.0.0.1 --port 8781
```

Then verify:

- `GET /runtime`
- `GET /api/runtime`
- `GET /`
- `GET /health`

For browser/UAT verification, follow the `agent-browser` skill posture: navigate, assert explicit text/selector states, then re-check logs. Do not infer success from prose alone.

### Documentation / operational verification

Update README and verify any new runtime table is included in health/recovery tooling.

## UI / UX guidance from loaded skills

Specific skill rules that matter here:

- **`accessibility`**: status cues must not rely on color alone; the runtime page should keep semantic landmarks, visible focus states, and explicit text labels for running/paused/failed/scheduled states.
- **`make-interfaces-feel-better`** + **`userinterface-wiki`**: elapsed pause and countdown values should use **tabular numbers** so they do not jitter as values change; this is especially relevant for timestamps, durations, and counts.
- **`best-practices`**: if the slice adds any state-changing web controls later, do not use GET side effects; use POST and keep the read path cheap and semantic.
- **`debug-like-expert`**: do not infer runtime truth from the last cycle row, from service expectations, or from “it should be sleeping now”; persist the scheduler truth and read it back.

## Skill discovery

Directly relevant non-installed skills discovered during research:

- **Typer CLI**: `narumiruna/agent-skills@python-cli-typer`
  - install command: `npx skills add narumiruna/agent-skills@python-cli-typer`
  - relevance: directly relevant to CLI command design, but only **18 installs**
- **SQLite**: `martinholovsky/claude-skills-generator@sqlite-database-expert`
  - install command: `npx skills add martinholovsky/claude-skills-generator@sqlite-database-expert`
  - relevance: strongest SQLite-specific result and highest adoption here (**685 installs**)

No install was performed.

## Bottom line for the planner

Treat S02 as **runtime-controller persistence + cooperative scheduler control + dedicated runtime surface**.

Do **not** start with HTML.

If the repository/runtime contract is correct first, the CLI, `/api/runtime`, `/runtime`, and even the overview home can all tell the same truth from the same DB. If that contract stays cycle-only, every surface in S02 will still be guessing.
