# S09 concurrency assessment

## Scope

Empirically determine a better default auto-concurrency cap for the new Webshare proxy-pool transport added in S09.

## Method

Used the real local 100-route `data/proxies.txt` Webshare pool and ran repeated live `discover` commands against Vinted with the same transport, same request delay (`0.2s`), same timeout (`10s`), and progressively larger `max-leaf-categories` workloads.

The benchmark series wrote fresh SQLite DBs under `data/benchmarks/` and measured:

- wall-clock duration
- successful scans / failed scans
- unique listing ids discovered
- derived throughput (`successful_scans_per_s`, `unique_ids_per_s`)

## Results

### Screening: 12 leaf categories

| Concurrency | Duration (s) | Successful scans | Failed scans | Unique IDs | Unique IDs/s |
|---|---:|---:|---:|---:|---:|
| 1 | 55.37 | 12 | 0 | 1134 | 20.48 |
| 4 | 20.28 | 12 | 0 | 1118 | 55.13 |
| 8 | 19.00 | 12 | 0 | 1116 | 58.74 |
| 12 | 11.08 | 12 | 0 | 1131 | 102.08 |
| 16 | 15.09 | 12 | 0 | 1132 | 75.02 |

Winner on this workload: **12**.

### Heavy run: 24 leaf categories

| Concurrency | Duration (s) | Successful scans | Failed scans | Unique IDs | Unique IDs/s |
|---|---:|---:|---:|---:|---:|
| 8 | 23.63 | 24 | 0 | 2206 | 93.36 |
| 12 | 20.31 | 24 | 0 | 2204 | 108.52 |
| 16 | 16.03 | 24 | 0 | 2208 | 137.74 |
| 20 | 16.31 | 24 | 0 | 2203 | 135.07 |
| 24 | 15.80 | 24 | 0 | 2217 | 140.32 |

Winner on this workload: **24**.

### Scale run: 32 leaf categories

| Concurrency | Duration (s) | Successful scans | Failed scans | Unique IDs | Unique IDs/s |
|---|---:|---:|---:|---:|---:|
| 24 | 19.11 | 32 | 0 | 2947 | 154.21 |
| 32 | 20.52 | 32 | 0 | 2929 | 142.74 |
| 40 | 20.21 | 32 | 0 | 2943 | 145.62 |

Winner on this workload: **24**.

## Decision

Raise the auto-concurrency cap from **12** to **24** for proxy-pooled runs.

## Why

- `12` was best only when the workload itself had just 12 concurrent leaf scans available.
- Once the workload exposed more parallelism (24 and 32 leaf categories), **24** consistently outperformed 12, 16, 20, 32, and 40.
- All winning runs at `24` completed with **0 failed scans** in these live samples, so the higher cap improved throughput without introducing obvious instability on this proxy pool.

## Code changes made after the benchmark

- Raised `_AUTO_PROXY_CONCURRENCY_CAP` from `12` to `24` in `vinted_radar/cli.py`.
- Updated README/operator docs to match the new default cap.
- Added a regression test proving the auto-cap now clamps a 30-route pool to `24`.

## Verification after tuning

- `python -m pytest tests/test_proxy_config.py tests/test_http.py tests/test_discovery_service.py tests/test_runtime_service.py tests/test_runtime_cli.py tests/test_cli_discover_smoke.py -q` → **37 passed**
- `python -m pytest -q` → **152 passed**

## Recommendation

For the current 100-route Webshare pool:

- leave auto-concurrency enabled for ordinary operator use
- prefer explicit `--concurrency 24` for larger manual discovery runs when you want reproducible behavior
- keep `proxy-preflight` as the first health gate before long runs

## Files / evidence

- `data/benchmarks/s09-screen-results.json`
- `data/benchmarks/s09-heavy-results.json`
- `data/benchmarks/s09-scale-results.json`
- `vinted_radar/cli.py`
- `tests/test_cli_discover_smoke.py`
- `README.md`
