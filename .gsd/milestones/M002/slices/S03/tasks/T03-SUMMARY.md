---
id: T03
parent: S03
milestone: M002
provides:
  - One documented local/VPS operator path for the mounted shared shell, reused by CLI output, README guidance, and `install_services.sh`
  - An automated smoke test for `scripts/verify_vps_serving.py` against a real prefixed local server
  - Final route/health verification of the mounted shell through the same base URL a VPS operator would share
key_files:
  - README.md
  - install_services.sh
  - scripts/verify_vps_serving.py
  - tests/test_cli_smoke.py
  - tests/test_dashboard_cli.py
  - vinted_radar/dashboard.py
key_decisions:
  - D027: use a shared `base_path` + optional `public_base_url` serving contract across CLI, HTML route generation, installer guidance, and smoke verification
patterns_established:
  - Treat `scripts/verify_vps_serving.py` as the normal pre-flight proof for a mounted deployment, and keep the explorer payload rich enough that the shared shell navigation remains fully mounted under a proxy prefix
observability_surfaces:
  - `python scripts/verify_vps_serving.py --base-url ... --listing-id ...`
  - `python -m pytest tests/test_cli_smoke.py tests/test_dashboard_cli.py`
  - `/health`
  - browser verification on the mounted `/radar/...` routes
duration: 55m
verification_result: passed
completed_at: 2026-03-23T11:01:31+01:00
blocker_discovered: false
---

# T03: Validate phone/desktop consultation and ship the VPS operator path

**Finished the operator path around the mounted shared shell: the README, installer, CLI output, smoke verifier, and local-prefixed acceptance now all describe and prove the same serving posture.**

## What Happened

T01 and T02 already gave S03 the mechanics and the shell. T03 finished the operator path so future work can treat the mounted product as a stable entrypoint rather than a local-only convenience.

I tightened the README around one explicit mounted-shell contract:
- `--base-path` for the reverse-proxy prefix
- `--public-base-url` for the external advertised URL
- one repeatable `verify_vps_serving.py` command for the public base URL
- one systemd install example that passes the same values through `install_services.sh`

I also tightened `install_services.sh` so the service installer now accepts and forwards:
- `DASHBOARD_BASE_PATH`
- `DASHBOARD_PUBLIC_BASE_URL`

and prints the corresponding smoke-check command after installation. That keeps the systemd service posture aligned with the CLI and the README.

The biggest execution change landed in `tests/test_cli_smoke.py`: I added a real prefixed integration smoke that
- seeds a local dashboard DB
- starts `start_dashboard_server(...)` under `/radar`
- runs `scripts/verify_vps_serving.py` as a subprocess against that mounted base URL
- asserts the script passes

That matters because the serving contract is now proven inside the test suite instead of living only in a manual note.

One late issue surfaced during this work: the smoke script still expected old UI wording from before T02 (`Explorer payload`, old detail hero labels). I changed it to verify route-contract markers that are stable under the new shell: overview heading, explorer filter/results sections, runtime heading, detail proof section, detail API, and `/health` serving metadata. That made the script robust against the shell polish that T02 introduced.

A second late issue surfaced through the smoke test itself: the explorer payload did not expose `home` in `diagnostics`, so the shared nav could not render an `Accueil` link under the mounted prefix on that route. I fixed that in `build_explorer_payload(...)`, which tightened the shared-shell contract and made the smoke path truly route-complete.

## Verification

T03 verification passed at three levels:

1. **CLI + smoke regressions**
   - `python -m pytest tests/test_cli_smoke.py tests/test_dashboard_cli.py`
2. **Mounted operator smoke on the real local server**
   - `python scripts/verify_vps_serving.py --base-url http://127.0.0.1:8782/radar --listing-id 9002`
3. **Browser verification against the mounted base URL**
   - desktop: `/radar/` loaded cleanly with the shared shell and no failed requests / console errors
   - mobile: `/radar/explorer` loaded cleanly, preserved the mounted nav, and still had no horizontal overflow (`scrollWidth <= innerWidth`)

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `python -m pytest tests/test_cli_smoke.py tests/test_dashboard_cli.py` | 0 | ✅ pass | 1.41s |
| 2 | `python scripts/verify_vps_serving.py --base-url http://127.0.0.1:8782/radar --listing-id 9002` | 0 | ✅ pass | ~0.2s |

## Diagnostics

For future inspection:
- `python scripts/verify_vps_serving.py --base-url ... --listing-id ...` is now the authoritative mounted-route smoke check.
- `tests/test_cli_smoke.py::test_verify_vps_serving_script_passes_against_local_prefixed_server` is the automated regression that keeps that operator path honest.
- `/health` exposes the mounted serving metadata (`base_path`, `public_base_url`, example routes`) and is the quickest first read when a deployment looks mis-mounted.
- `python -m vinted_radar.cli dashboard --base-path ... --public-base-url ...` still prints the exact advertised route set a human operator should test.

## Deviations

I made one unplanned product fix during T03: `build_explorer_payload()` now exposes `home` in `diagnostics` so the shared navigation stays complete under the mounted prefix. That wasn’t written in the task plan, but the smoke test made the gap visible and it was part of the serving contract in practice.

## Known Issues

- The mounted operator path is now documented and tested locally, but this slice still does not add authentication or reverse-proxy config generation; the repo intentionally stops at a proxy-friendly app contract plus installer guidance.
- The browser acceptance here proves mounted phone/desktop consultation for the shared shell, not the deeper explorer/detail richness that later slices still own.

## Files Created/Modified

- `README.md` — finalized the mounted local/VPS serving guidance, smoke-check command, and systemd example using the same route contract.
- `install_services.sh` — forwards base-path/public-base-url installer settings into the dashboard service and prints the matching smoke-check command.
- `scripts/verify_vps_serving.py` — now verifies stable route-contract markers that match the shared shell instead of brittle pre-shell wording.
- `tests/test_cli_smoke.py` — added a real prefixed integration smoke for the mounted server + verifier script.
- `tests/test_dashboard_cli.py` — continues to cover the advertised operator URLs, including proxy-aware output.
- `vinted_radar/dashboard.py` — explorer diagnostics now include `home` so the mounted shared nav stays route-complete.
- `.gsd/milestones/M002/slices/S03/S03-PLAN.md` — T03 marked complete.
