---
id: S03
parent: M002
milestone: M002
provides:
  - A shared French-first responsive shell across overview, explorer, runtime, and HTML listing detail
  - A mounted VPS/local serving contract built around `base_path` + optional `public_base_url`
  - One repeatable route/health smoke verifier for the mounted product shell
requires:
  - slice: S01
    provides: SQL-backed overview home, explorer paging seam, and the French market-summary contract that the shared shell now wraps
  - slice: S02
    provides: controller-backed runtime truth and dedicated `/runtime` semantics that the shared shell and mounted serving path now expose remotely
affects:
  - S04
  - S05
  - S06
  - S07
key_files:
  - vinted_radar/serving.py
  - vinted_radar/dashboard.py
  - vinted_radar/cli.py
  - README.md
  - install_services.sh
  - scripts/verify_vps_serving.py
  - tests/test_dashboard.py
  - tests/test_dashboard_cli.py
  - tests/test_runtime_cli.py
  - tests/test_cli_smoke.py
  - data/vinted-radar-s03.db
key_decisions:
  - D027
patterns_established:
  - Drive mounted route generation through a shared route contract and keep every HTML route inside one shared shell instead of letting page-specific HTML invent its own links and layout rules
observability_surfaces:
  - `python scripts/verify_vps_serving.py --base-url ... --listing-id ...`
  - `/health`
  - `python -m pytest tests/test_dashboard.py tests/test_dashboard_cli.py tests/test_cli_smoke.py`
  - mounted browser checks on `/radar/`, `/radar/explorer`, `/radar/runtime`, `/radar/listings/<id>`
drill_down_paths:
  - `.gsd/milestones/M002/slices/S03/tasks/T01-SUMMARY.md`
  - `.gsd/milestones/M002/slices/S03/tasks/T02-SUMMARY.md`
  - `.gsd/milestones/M002/slices/S03/tasks/T03-SUMMARY.md`
  - `.gsd/milestones/M002/slices/S03/S03-UAT.md`
duration: 1 session
verification_result: passed
completed_at: 2026-03-23T11:04:58+01:00
---

# S03: Responsive French Product Shell + VPS Serving Path

**S03 turned the M002 product into one mounted, French-first, phone/desktop-consultable web shell: overview, explorer, runtime, and HTML listing detail now share the same SSR navigation and can be served cleanly behind a VPS proxy prefix.**

## What Happened

S03 started by making route generation and operator output truthful under a mounted prefix.

`vinted_radar/serving.py` now owns the route contract: `base_path`, optional `public_base_url`, mounted route generation, and the advertised operator URLs printed by the CLI. On top of that, `vinted_radar/dashboard.py` stopped assuming root-mounted localhost links and gained a stable HTML listing-detail route at `/listings/<id>` alongside the existing JSON detail endpoint.

That same route contract now flows through:
- the WSGI app
- `/health.serving`
- CLI dashboard-capable commands
- the systemd installer
- `scripts/verify_vps_serving.py`

Once the routes were safe, S03 rebuilt the HTML shell itself.

`vinted_radar/dashboard.py` now has one shared shell seam for all four product routes:
- one palette and type system
- one primary navigation with `aria-current`
- one skip-link / landmark pattern
- one responsive panel/button/card vocabulary
- French-first product copy at the shell layer

The overview kept its SQL-backed market summary and honesty modules, but now lives inside the same shell as the explorer, runtime, and detail pages.

The explorer changed the most visually. The old table-first brownfield layout was replaced as the primary reading path by responsive listing cards with:
- title / id / brand
- price + freshness chips
- seller visibility
- estimated publication + radar timing
- latest probe
- direct actions to HTML detail, JSON detail, targeted explorer state, and Vinted

That change matters because S03’s acceptance bar was phone/desktop consultability, not just a better desktop screenshot.

The runtime route also stopped behaving like a route-local admin screen. It now uses the same shared shell and exposes controller facts, recent cycles, failures, and runtime semantics through responsive cards instead of a table-first layout.

The detail route is now structurally part of the same product. It uses the shared shell, French-first visible labels, translated freshness/state/basis/confidence wording, translated transition descriptions, and a stable HTML route that no longer forces the user back to JSON-first drill-down.

T03 then finished the operator path:
- README now documents one mounted local/VPS serving contract and one repeatable smoke-check command
- `install_services.sh` forwards `DASHBOARD_BASE_PATH` and `DASHBOARD_PUBLIC_BASE_URL` into the dashboard service and prints the matching smoke command
- `tests/test_cli_smoke.py` now proves `verify_vps_serving.py` against a real prefixed local server

Two useful late fixes landed because the new smoke path was real enough to catch them:
- the smoke verifier had to be updated to validate route-contract markers that survive shell polish, not old wording from before T02
- explorer diagnostics needed an explicit `home` route so the shared nav stayed complete under `/radar`

## Verification

S03 verification passed in four layers:

1. **Route/shell regressions**
   - `python -m pytest tests/test_dashboard.py`
2. **CLI + mounted smoke regressions**
   - `python -m pytest tests/test_cli_smoke.py tests/test_dashboard_cli.py`
3. **Mounted route smoke on the real local server**
   - `python scripts/verify_vps_serving.py --base-url http://127.0.0.1:8782/radar --listing-id 9002`
4. **Browser verification**
   - desktop: `/radar/` rendered the shared shell cleanly and kept console/network clean
   - mobile: `/radar/explorer` stayed readable without horizontal overflow; earlier S03 browser passes also validated mobile overview/detail/runtime behavior on the same shell

## Requirements Advanced

- R009 — S03 turns the product into a clearer information architecture across overview, explorer, runtime, and detail instead of one mixed proof screen.
- R010 — S03 makes the runtime page part of the real mounted product path, not only a local CLI/operator artifact.
- R012 — S03 deepens daily utility by making exploration, detail, and runtime feel like one coherent product surface instead of disconnected routes.
- R004 — S03 carries coverage/freshness/confidence honesty through the mounted shell rather than leaving those signals trapped in a local-only route posture.

## Requirements Validated

- none — the relevant requirements were already validated earlier at smaller scope; S03 broadens and productizes them for the mounted remote path.

## New Requirements Surfaced

- none

## Requirements Invalidated or Re-scoped

- none

## Deviations

- Runtime cycles were moved from a table-first representation to responsive cards during T02 because phone-width consultation would otherwise remain desktop-biased.
- Explorer diagnostics gained an explicit `home` route during T03 because the mounted smoke test revealed that the shared nav was incomplete on that route under `/radar`.

## Known Limitations

- The shared shell is now coherent, but S04 still needs deeper explorer filters/comparison workflows before the browsing surface is fully rich.
- The detail route is structurally integrated and translated, but it is not yet narrative-first; S05 still owns the richer plain-language reading and progressive disclosure.
- S03 documents a proxy-friendly serving contract, but it does not ship reverse-proxy config or auth. The repo deliberately stops at the application/service boundary here.

## Follow-ups

- S04 should extend the explorer and comparison paths inside the new shell instead of adding standalone route-local UI.
- S05 should reuse the shared shell and mounted-route contract while replacing the current proof-first detail body with narrative-first reading.
- S06 should surface degraded acquisition truth inside the same shell and mounted operator path rather than inventing a parallel admin seam.
- S07 should reuse `verify_vps_serving.py` and `S03-UAT.md` as the base acceptance harness for the live VPS closeout.

## Files Created/Modified

- `vinted_radar/serving.py` — shared mounted-route contract for CLI and SSR pages.
- `vinted_radar/dashboard.py` — proxy-aware route handling, shared shell, responsive explorer/runtime/detail layouts, localized visible copy, and route-complete explorer diagnostics.
- `vinted_radar/cli.py` — base-path/public-base-url aware advertised URLs for dashboard-capable commands.
- `README.md` — mounted local/VPS serving contract plus smoke-check guidance.
- `install_services.sh` — service forwarding for mounted dashboard settings and matching smoke output.
- `scripts/verify_vps_serving.py` — mounted route/health verifier aligned with the shared shell.
- `tests/test_dashboard.py` — regressions for the shared shell, prefixed routes, and mobile-safe explorer structure.
- `tests/test_dashboard_cli.py` — dashboard CLI coverage for local and proxy-aware operator URLs.
- `tests/test_runtime_cli.py` — dashboard-capable runtime commands stay aligned with the advertised route set.
- `tests/test_cli_smoke.py` — real prefixed integration smoke for the verifier script.
- `data/vinted-radar-s03.db` — seeded local slice DB used for S03 browser/operator verification.
- `README.md`, `.gsd/PROJECT.md`, `.gsd/KNOWLEDGE.md`, `.gsd/milestones/M002/M002-ROADMAP.md`, `.gsd/milestones/M002/slices/S03/S03-UAT.md` — updated project/context artifacts for the completed slice.

## Forward Intelligence

### What the next slice should know
- The mounted route contract is now part of the product surface. If a future route hardcodes `/explorer` or `/runtime` directly in HTML, it is regressing S03.
- The explorer and runtime pages are now shell-complete and mobile-safe enough to build on. Later slices should extend these routes, not replace them with isolated mini-apps.
- `verify_vps_serving.py` is cheap enough to rerun before and after route work; use it.

### What's fragile
- Explorer/detail content richness still depends on brownfield payload seams underneath the shell — especially the detail payload. S05 will need to improve that body without breaking the mounted route contract.
- Mounted navigation relies on diagnostics/home links being kept complete on every route payload. If a later payload omits one of those diagnostics keys, the shared nav can silently regress.

### Authoritative diagnostics
- `python scripts/verify_vps_serving.py --base-url ... --listing-id ...` — fastest end-to-end mounted route proof.
- `/health` — quickest serving-contract sanity check (`base_path`, `public_base_url`, example routes`).
- `tests/test_cli_smoke.py::test_verify_vps_serving_script_passes_against_local_prefixed_server` — automated regression for the mounted operator path.

### What assumptions changed
- “A local route working at `/` is enough to call the product proxy-friendly.” — false; S03 proved the mounted `/radar` path needs its own route contract and smoke proof.
- “Responsive polish can wait until later once the routes exist.” — false; the explorer/runtime/detail routes were not genuinely consultable on phone until the shell/layout work landed.
- “Operator docs can lag the implementation.” — false; S03’s mounted smoke test caught real drift between docs, shell output, and payload diagnostics.
