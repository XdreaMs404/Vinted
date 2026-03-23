---
id: T03
parent: S06
milestone: M002
provides:
  - README/UAT guidance plus served-browser proof for degraded acquisition behavior on the seeded S06 demo DB
key_files:
  - README.md
  - .gsd/milestones/M002/slices/S06/S06-UAT.md
  - .gsd/milestones/M002/slices/S06/tasks/T03-SUMMARY.md
key_decisions:
  - Re-prove degraded acquisition on the served product routes, not only through repository/unit tests.
patterns_established:
  - Seed the S06 demo DB from `tests.test_dashboard._seed_dashboard_db()` before browser proof so UI/UAT stays aligned with route regression fixtures.
observability_surfaces:
  - README.md
  - .gsd/milestones/M002/slices/S06/S06-UAT.md
  - http://127.0.0.1:8786/
  - http://127.0.0.1:8786/explorer?root=Femmes&q=robe&page_size=2&sort=view_desc
  - http://127.0.0.1:8786/runtime
  - http://127.0.0.1:8786/listings/9002?root=Femmes&state=active&price_band=40_plus_eur&sort=view_desc&page_size=12
  - http://127.0.0.1:8786/api/runtime
  - http://127.0.0.1:8786/health
  - .artifacts/browser/2026-03-23T15-11-53-531Z-session/s06-browser-timeline.json
duration: 1 session
verification_result: passed
completed_at: 2026-03-23
blocker_discovered: false
---

# T03: Document and re-prove degraded-mode behavior with seeded browser UAT

**Updated operator docs/UAT for S06, seeded a reproducible degraded demo DB, re-served the app locally, and browser-verified overview, explorer, detail, runtime, `/api/runtime`, and `/health` against the same degraded acquisition contract.**

## What Happened

T03 turned the new S06 behavior into something repeatable for the next agent instead of leaving it trapped in code and test fixtures.

I first updated `README.md` so the operator docs explain the new acquisition-health states (`healthy`, `partial`, `degraded`), the proxy-aware `state-refresh` path, and the right inspection surfaces (`runtime-status`, `state-refresh --format json`, `/api/runtime`, `/health`, and the visible product routes).

I then wrote `.gsd/milestones/M002/slices/S06/S06-UAT.md` as a mixed-mode UAT: regenerate the seeded `data/vinted-radar-s06.db`, serve the product locally on port `8786`, verify the home/explorer/detail/runtime HTML routes, then verify `/api/runtime` and `/health` against the same degraded acquisition truth.

For the actual proof, I regenerated `data/vinted-radar-s06.db` from `tests.test_dashboard._seed_dashboard_db()`, served the dashboard locally, and browser-verified all six routes. The served product showed the intended separation cleanly: overview and explorer exposed `acquisition dégradée` without breaking the market read, the detail page surfaced `Dernière probe dégradée` and provenance `historique radar après probe dégradée`, the runtime page separated scheduler state from acquisition health with a dedicated panel, and `/api/runtime` + `/health` both exposed the same degraded acquisition JSON (`status: degraded`, `anti_bot_challenge_count: 1`, `recent_scan_failure_count: 0`). I also wrote the browser action timeline to `.artifacts/browser/.../s06-browser-timeline.json` for later replay/debugging.

While doing the browser proof, I caught and fixed small but real product issues the tests alone did not highlight: stale server state after code edits required explicit server restarts for truthful verification, and the explorer/runtime acquisition warning copy needed final cleanup so the visible product layer stayed French-first instead of leaking raw English reason strings or cramped labels.

## Verification

Ran the T03 doc/route/CLI test slice, then the full suite, then served-browser verification on the seeded S06 demo DB.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `python -m pytest tests/test_dashboard.py tests/test_dashboard_cli.py tests/test_runtime_cli.py -q` | 0 | PASS | 1.77s |
| 2 | `python -m pytest -q` | 0 | PASS | 5.26s |

## Diagnostics

The authoritative human-flow proof now lives in `.gsd/milestones/M002/slices/S06/S06-UAT.md`, and the browser sequence is captured in `.artifacts/browser/2026-03-23T15-11-53-531Z-session/s06-browser-timeline.json`. If the served product later looks wrong, regenerate `data/vinted-radar-s06.db`, re-run the server on `8786`, then compare the HTML routes with `/api/runtime` and `/health` before assuming the repository contract drifted.

## Deviations

The task plan did not explicitly call for cleaning up the explorer/runtime acquisition copy after browser proof, but the served pages still leaked raw English reason strings until that was fixed. That translation stayed in the product layer only; the machine-facing JSON remained literal.

## Known Issues

This task proves S06 locally on a seeded degraded dataset. It does not prove real VPS behavior under live anti-bot pressure over time; that remains S07 work.

## Files Created/Modified

- `README.md` — documented proxy-aware state refresh and the new degraded acquisition inspection surfaces.
- `.gsd/milestones/M002/slices/S06/S06-UAT.md` — recorded the repeatable served-browser UAT for S06.
- `.gsd/milestones/M002/slices/S06/tasks/T03-SUMMARY.md` — captured the verification story and artifacts for the final task.
