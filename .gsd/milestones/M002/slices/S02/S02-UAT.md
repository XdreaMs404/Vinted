# S02: Runtime Truth + Pause/Resume Surface — UAT

**Milestone:** M002  
**Slice:** S02  
**Written:** 2026-03-23

## UAT Type

- UAT mode: mixed
- Why this mode is sufficient: S02 claims both contract-level runtime truth and a real operator surface. The slice therefore needs repository/test proof plus a live continuous loop exercised through CLI, HTTP, and browser.

## Preconditions

- Python dependencies are installed and the project runs from `C:\Users\Alexis\Documents\VintedScrap2`.
- Port `8781` is free.
- Start the local continuous runtime in one terminal:

```bash
python -m vinted_radar.cli continuous \
  --db data/vinted-radar-s02.db \
  --page-limit 1 \
  --max-leaf-categories 1 \
  --state-refresh-limit 2 \
  --interval-seconds 5 \
  --request-delay 0.0 \
  --dashboard \
  --host 127.0.0.1 \
  --port 8781
```

- Open `http://127.0.0.1:8781/` and `http://127.0.0.1:8781/runtime` in a browser.

## Smoke Test

Run `python -m vinted_radar.cli runtime-status --db data/vinted-radar-s02.db --format json` while the continuous loop is alive.

Expected quick signal:
- top-level `status` and nested `controller.status` match
- `latest_cycle` is present
- `updated_at` heartbeat is recent
- `/runtime`, `/api/runtime`, and `/health` all load successfully

## Test Cases

### 1. Runtime page reflects controller truth, not only the last cycle row

1. Open `http://127.0.0.1:8781/runtime`.
2. Read the status pills and the “État courant du contrôleur” section.
3. Compare that page with `http://127.0.0.1:8781/api/runtime`.
4. **Expected:** the page shows the current controller status/phase (`en cours`, `planifié`, or `en pause`) plus heartbeat fields, while the JSON still exposes `latest_cycle` separately.

### 2. Pause request becomes visible before the full interval elapses

1. While the loop is running, run:

```bash
python -m vinted_radar.cli runtime-pause --db data/vinted-radar-s02.db
```

2. Immediately inspect `runtime-status --format json`, `/api/runtime`, and `/health`.
3. Wait until the active cycle finishes if the runtime was already mid-cycle.
4. **Expected:**
   - if the runtime was mid-cycle, the first read may still show `running` with a pause request pending or still processing the current cycle
   - once the cycle finishes, `status = paused` appears in both `runtime-status` and `/api/runtime`
   - `/health` reports `current_runtime_status = paused`
   - `/runtime` shows a persisted `paused_at`

### 3. Resume request restores scheduling truthfully

1. From a second terminal, run:

```bash
python -m vinted_radar.cli runtime-resume --db data/vinted-radar-s02.db
```

2. Inspect `runtime-status --format json`, `/api/runtime`, `/health`, and `/runtime`.
3. **Expected:**
   - the controller leaves `paused`
   - the runtime returns to `scheduled` or quickly back to `running`
   - `next_resume_at` is visible when scheduled
   - `/health` and `/api/runtime` agree on the current controller status

### 4. Overview home reads controller truth instead of calling the runtime “completed” during a healthy wait

1. Open `http://127.0.0.1:8781/`.
2. Inspect the freshness card and the runtime/incidents panel.
3. **Expected:** the home uses `Runtime actuel` from controller truth (`planifié`, `en pause`, `en cours`) rather than implying that the whole runtime is merely `completed` because the last cycle ended cleanly.

## Edge Cases

### Pause requested during an active cycle

1. Trigger `runtime-pause` while `runtime-status` shows `running`.
2. **Expected:** the current cycle finishes cleanly; the controller then moves to `paused` without losing the cycle history row.

### Latest cycle completed but current runtime is only waiting

1. Resume the loop and inspect `/api/runtime` during the wait window before the next cycle starts.
2. **Expected:** `latest_cycle.status` can still be `completed`, but top-level/controller status is `scheduled` and `/health.current_runtime_status` matches it.

## Failure Signals

- `/runtime` is missing or returns 404.
- `/api/runtime` exposes only cycle history and has no controller-backed top-level fields.
- `/health` disagrees with `/api/runtime` on the current runtime state outside of a transient in-flight request window.
- `runtime-pause` has no visible effect before the next full interval completes.
- `runtime-resume` clears pause state but does not restore `scheduled` / `running` truth.
- The overview home still phrases the runtime as if the last completed cycle were the current runtime state.
- Browser load on `/runtime` produces console errors or failed requests during normal rendering.

## Requirements Proved By This UAT

- R010 — proves that the local continuous runtime can expose truthful running/paused/scheduled operator state through CLI and web surfaces on the same SQLite boundary.
- R004 — proves that runtime freshness and operator state remain visibly inspectable rather than hidden behind a single last-cycle summary.

## Not Proven By This UAT

- Remote VPS serving quality on phone and desktop — that belongs to S03 and S07.
- Degraded acquisition messaging under persistent anti-bot failure — that belongs to S06.
- Full explorer/detail shell coherence — later M002 slices still own that work.

## Notes for Tester

- Live acquisition may succeed or fail depending on Vinted/anti-bot conditions. S02 is still a pass if the controller truth remains honest about `running`, `paused`, `scheduled`, `failed`, `paused_at`, and `next_resume_at`.
- If you see a real failed cycle, check whether the controller returns to `scheduled` afterward; that distinction is exactly what this slice is meant to make visible.
