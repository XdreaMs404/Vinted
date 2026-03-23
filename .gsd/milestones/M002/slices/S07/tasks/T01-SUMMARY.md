---
id: T01
parent: S07
milestone: M002
provides:
  - Large-corpus mounted serving fast enough for realistic S07 proof, with generated-at reuse, HTML-only mojibake repair, and a stable mounted smoke timeout
key_files:
  - vinted_radar/repository.py
  - vinted_radar/dashboard.py
  - scripts/verify_vps_serving.py
  - README.md
  - tests/test_repository.py
  - tests/test_dashboard.py
key_decisions:
  - Materialize the classified overview snapshot once per repository connection/`now` and keep visible-text repair in HTML only so JSON stays literal.
patterns_established:
  - Reuse one generated timestamp per assembled payload when repository work depends on `now`; otherwise a connection-local cache will still miss within one request.
observability_surfaces:
  - python -m pytest -q
  - data/m001-closeout.db
  - scripts/verify_vps_serving.py
  - http://127.0.0.1:8790/radar/
  - http://127.0.0.1:8790/radar/explorer
  - http://127.0.0.1:8790/radar/runtime
  - http://127.0.0.1:8790/radar/health
duration: 1 session
verification_result: passed
completed_at: 2026-03-23
blocker_discovered: false
---

# T01: Harden mounted large-corpus serving for realistic S07 acceptance

**Eliminated the worst large-corpus mounted-route regressions by materializing the classified snapshot once per request path, reusing one generated timestamp in payload assembly, repairing visible mojibake in HTML, and making the mounted smoke verifier realistic enough for the 50k-listing proof DB.**

## What Happened

The first realistic S07 proof on `data/m001-closeout.db` exposed a real closeout blocker: the product was functionally correct but too slow on the large mounted corpus to treat as an honest final assembly proof. The home route was taking ~22 s and the explorer ~34 s because overview, explorer filters, explorer comparisons, and explorer paging all rebuilt the same classified snapshot CTE repeatedly on the same request path.

I fixed that at the repository seam rather than by trimming the product surface. `RadarRepository` now materializes the classified overview snapshot into a connection-local temp table keyed by the effective request timestamp. `overview_snapshot()`, `explorer_filter_options()`, `explorer_summary()`, `explorer_comparison_modules()`, and `listing_explorer_page()` all reuse that temp table instead of re-running the full CTE each time.

That cache only pays off if the request actually uses one stable `now`, so I also changed `build_dashboard_payload()` and `build_explorer_payload()` to compute `generated_at` once and pass that value through the repository calls on the same request.

The realistic proof also surfaced two product/operator defects that only showed up in the mounted Windows path:

- Git Bash / MSYS rewrote `--base-path /radar` into a bogus Windows filesystem path before Python saw it. I documented the `MSYS_NO_PATHCONV=1` workaround in `README.md`.
- The large historical DB surfaced visible category-path mojibake like `VÃªtements`. I repaired common UTF-8 mojibake in visible HTML only, through `_escape()`, so the product surface reads correctly without mutating the raw JSON diagnostics.

Finally, the mounted smoke verifier default timeout was too tight for a realistic 50k-listing DB. I raised the per-request default to 30 seconds so the harness matches the actual S07 proof shape.

## Verification

Ran the full test suite, the focused dashboard/repository tests, direct payload timing checks on `data/m001-closeout.db`, and mounted route timing checks through the local server.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `python -m pytest tests/test_dashboard.py tests/test_repository.py tests/test_dashboard_cli.py tests/test_cli_smoke.py -q` | 0 | PASS | 2.34s |
| 2 | `python -m pytest -q` | 0 | PASS | 5.25s |
| 3 | `python - <<'PY' ... build_dashboard_payload/build_explorer_payload timings on data/m001-closeout.db ... PY` | 0 | PASS | dashboard ~6.62s / explorer ~6.82s |
| 4 | `python - <<'PY' ... urllib timings for /radar/, /radar/explorer, /radar/runtime, /radar/listings/64882428..., /radar/health ... PY` | 0 | PASS | overview ~5.34s, explorer ~10.51s, runtime ~5.56s, detail ~13.44s, health ~16.71s |

## Diagnostics

The large-corpus timing seam now lives in `vinted_radar/repository.py` and `vinted_radar/dashboard.py`. To inspect it later, rerun the payload timing snippet against `data/m001-closeout.db`, then compare mounted HTTP timings through `http://127.0.0.1:8790/radar/` and `scripts/verify_vps_serving.py`. If visible text regresses into `VÃ...` again, inspect `_escape()` in `vinted_radar/dashboard.py` first.

## Deviations

The written slice intent did not call out HTML-only mojibake repair explicitly, but the first realistic browser proof exposed it as a real product defect on the acceptance surface. I fixed it in the visible HTML layer only and kept JSON literal, consistent with the existing product-vs-diagnostics split.

## Known Issues

This task does not prove the public VPS entrypoint itself. It only removes the local mounted blockers that would have made any honest S07 proof unstable or unreadable.

## Files Created/Modified

- `vinted_radar/repository.py` — materialized/reused the classified snapshot for overview and explorer mounted paths.
- `vinted_radar/dashboard.py` — reused one generated timestamp per payload and repaired visible mojibake in HTML escaping.
- `scripts/verify_vps_serving.py` — raised the default per-request timeout to 30 seconds for realistic mounted proof.
- `README.md` — documented the Git Bash / MSYS mounted-path workaround and the realistic smoke command.
- `tests/test_repository.py` — added snapshot-reuse regression coverage.
- `tests/test_dashboard.py` — added generated-at reuse and visible-text repair regression coverage.
