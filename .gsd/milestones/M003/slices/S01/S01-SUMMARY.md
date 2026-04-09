---
id: S01
parent: M003
milestone: M003
provides:
  - A deterministic acquisition scorecard contract that later slices can reuse for transport, lane, frontier, and market comparisons.
  - Operator CLI commands to build, inspect, and re-render redacted benchmark artifacts from spec files, raw experiment payloads, or saved VPS runner bundles.
  - A preserve-live VPS benchmark harness that produces local benchmark bundles with copied SQLite snapshots plus resource/storage evidence.
  - A durable FR baseline artifact set that downstream slices can compare mechanically rather than by hand-copied shell output.
requires:
  []
affects:
  - S02
  - S03
  - S04
  - S05
  - S06
  - S07
key_files:
  - vinted_radar/services/acquisition_benchmark.py
  - vinted_radar/cli.py
  - scripts/run_vps_benchmark.py
  - tests/test_acquisition_benchmark.py
  - tests/test_acquisition_benchmark_cli.py
  - tests/test_vps_benchmark_runner.py
  - .gsd/milestones/M003/benchmarks/baseline-fr-page1.json
  - .gsd/milestones/M003/benchmarks/baseline-fr-page1.md
  - .gsd/milestones/M003/benchmarks/_closeout-baseline-fr-page1.json
  - .gsd/milestones/M003/benchmarks/_closeout-baseline-fr-page1.md
  - .gsd/milestones/M003/M003-RESEARCH.md
  - README.md
  - .gsd/PROJECT.md
  - .gsd/KNOWLEDGE.md
key_decisions:
  - D049: rank acquisition benchmark leaderboards by net new listings/hour first, then duplicate ratio, challenge rate, degraded count, bytes/new listing, mean CPU, peak RAM, and experiment ID for deterministic ties.
  - D050: use repeatable JSON spec files for benchmark CLI input, resolve relative db_path values from the spec file directory, and redact proxy URLs plus secret-shaped config keys before printing or writing reports.
  - D051: default the VPS benchmark runner to preserve-live mode so it snapshots the live SQLite DB, runs bounded cycles against the snapshot, and labels live-db runs as destructive.
  - D052: auto-load .env.vps SSH defaults/askpass, carry the configured identity file through SSH/SCP, and upload the remote experiment helper as a temporary file for unattended VPS execution.
patterns_established:
  - One normalized acquisition benchmark report contract now feeds service logic, CLI rendering, saved artifacts, and VPS experiment bundles, so later slices compare the same score fields everywhere.
  - Benchmark artifacts are safe to share because proxy credentials, DSNs, tokens, and password-shaped config values are redacted before stdout or file persistence.
  - The preserve-live VPS posture is now the default experimental harness: copy the live DB, benchmark the copy, export evidence locally, and leave systemd services plus the live DB untouched unless an operator explicitly chooses a destructive mode.
  - Saved scripts/run_vps_benchmark.py bundles are now first-class CLI inputs through their nested benchmark_report payload, so downstream slices can inspect VPS results without manual extraction.
observability_surfaces:
  - Benchmark JSON and Markdown artifacts under .gsd/milestones/M003/benchmarks/ expose methodology, leaderboard ranking, winner reason, observed config, and artifact paths.
  - The VPS runner captures cycle-by-cycle resource snapshots, DB/storage growth, remote service posture, exit codes, and copied snapshot metadata inside each bundle.
  - M003-RESEARCH now records the refreshed FR baseline metrics and the operational constraint that the live VPS benchmark path must use the project virtualenv Python interpreter.
  - Operational readiness: health signal = runner exits 0 and writes both JSON/Markdown artifacts with preserved live service posture; failure signal = non-zero cycle exit, missing artifacts, or remote interpreter/import failures in the captured stderr; recovery = rerun with the detected virtualenv interpreter or explicit --remote-python and inspect the saved bundle before retrying; monitoring gap = current closeout baseline is still short-window and does not yet provide long-duration stability alerts.
drill_down_paths:
  - .gsd/milestones/M003/slices/S01/tasks/T01-SUMMARY.md
  - .gsd/milestones/M003/slices/S01/tasks/T02-SUMMARY.md
  - .gsd/milestones/M003/slices/S01/tasks/T03-SUMMARY.md
  - .gsd/milestones/M003/slices/S01/tasks/T04-SUMMARY.md
duration: ""
verification_result: passed
completed_at: 2026-04-09T13:49:24.240Z
blocker_discovered: false
---

# S01: Acquisition Benchmark Scorecards + VPS Experiment Harness

**Delivered the benchmark substrate for M003: deterministic acquisition scorecards, redacted CLI/report flows, a preserve-live VPS experiment harness, and durable FR baseline artifacts that future slices can compare mechanically.**

## What Happened

S01 replaced intuition-led acquisition tuning with one shared measurement contract and one repeatable experiment path. T01 added the acquisition benchmark service that ingests repository windows plus storage/resource snapshots and computes the explicit winner fields this milestone needs: net new listings/hour, duplicate ratio, challenge rate, degraded counts, bytes per new listing, mean CPU, and peak RAM, with a deterministic tie-break order captured in D049. T02 turned that service into operator-facing CLI surfaces by adding acquisition-benchmark and acquisition-benchmark-report, portable spec-file loading, artifact writing, and redaction of proxy credentials plus secret-shaped config keys (D050). During slice closeout I also fixed the last integration gap: acquisition-benchmark-report now accepts the full JSON bundle shape emitted by scripts/run_vps_benchmark.py via the nested top-level benchmark_report field, so saved VPS experiment bundles can be re-rendered directly instead of requiring manual JSON extraction. T03 added scripts/run_vps_benchmark.py as the real VPS harness, defaulting to preserve-live mode so experiments run against a temporary remote SQLite snapshot while leaving live services and the live DB untouched (D051). T04 hardened that runner for unattended SSH execution by auto-loading .env.vps defaults, carrying the identity file through SSH/SCP, auto-detecting a usable remote Python interpreter, and uploading the remote helper as a temporary file rather than inlining multiline Python over ssh -c (D052). The slice now leaves durable benchmark artifacts under .gsd/milestones/M003/benchmarks/, including the refreshed baseline-fr-page1 bundle plus closeout probe bundles. The latest closeout run proved the end-to-end contract on the real VPS in preserve-live mode: one bounded FR page_limit=1 cycle completed successfully against a copied snapshot, wrote JSON/Markdown artifacts locally, preserved live service posture, captured resource/storage evidence, and produced a truthful leaderboard entry for the current baseline profile. Together these changes give downstream slices a mechanical baseline and a reusable experiment harness for lane, transport, market, and frontier comparisons.

## Verification

Verified the slice at the code and live-artifact levels. `python -m pytest tests/test_acquisition_benchmark.py tests/test_acquisition_benchmark_cli.py tests/test_vps_benchmark_runner.py -q` passed with 12 tests, covering deterministic ranking, redacted CLI/report flows, nested VPS runner bundle re-rendering, preserve-live runner behavior, and failure-path bundle persistence. `python scripts/run_vps_benchmark.py --host 46.225.113.129 --profile baseline-fr-page1 --duration-minutes 2 --output .gsd/milestones/M003/benchmarks/_closeout-baseline-fr-page1.json --markdown .gsd/milestones/M003/benchmarks/_closeout-baseline-fr-page1.md` completed successfully in preserve-live mode, wrote both artifacts, and recorded one successful bounded cycle on the real VPS without mutating the live DB. `python -m vinted_radar.cli acquisition-benchmark-report --input .gsd/milestones/M003/benchmarks/_closeout-baseline-fr-page1.json --format markdown` then re-rendered that saved runner bundle directly, confirming the operator-facing report path now works on the exact bundle shape emitted by the VPS harness. The closeout bundle reports 471.46 net new listings/hour, duplicate ratio 0.9670, challenge rate 0.0000, degraded count 2, bytes/new listing 45702.74, mean CPU 11.31%, and peak RAM 169.13 MB for the bounded FR baseline profile.

## Requirements Advanced

None.

## Requirements Validated

None.

## New Requirements Surfaced

None.

## Requirements Invalidated or Re-scoped

None.

## Deviations

The original T04 task plan targeted a 90-minute baseline run. Slice closeout used bounded 2-minute preserve-live windows instead so the slice could finish with durable proof quickly and without turning closeout into a long endurance soak. The summary and research artifacts are explicit that this is a short-window baseline suitable for mechanical comparison, not a final long-window stability claim. I also fixed an integration bug discovered during closeout: the report CLI originally rejected the full saved VPS bundle shape until nested benchmark_report support was added.

## Known Limitations

The current baseline evidence covers only the FR page_limit=1 profile and only a short preserve-live window; future slices still need multi-profile comparisons and longer windows before making stronger stability or cadence claims. The measured baseline still shows high duplicate ratios and some degraded probes, which is expected for the current acquisition posture but means later transport/frontier slices must improve useful yield rather than raw request activity alone. The live VPS benchmark path still depends on using the project virtualenv Python interpreter on the host.

## Follow-ups

Run longer-window preserve-live benchmarks for the same baseline profile to establish endurance expectations. Benchmark new lane, transport, concurrency, and frontier candidates against the saved baseline bundles instead of ad hoc shell comparisons. Keep reusing acquisition-benchmark-report directly on saved runner bundles so later slices compare artifacts without manual JSON surgery.

## Files Created/Modified

- `vinted_radar/services/acquisition_benchmark.py` — Added the normalized acquisition benchmark domain/service contract, score computation, report rendering helpers, and benchmark artifact writing logic.
- `vinted_radar/cli.py` — Added acquisition benchmark CLI entrypoints and, during closeout, taught acquisition-benchmark-report to read full VPS runner bundles through their nested benchmark_report payload.
- `scripts/run_vps_benchmark.py` — Added the preserve-live VPS experiment harness, unattended SSH transport hardening, remote-Python detection, and local artifact bundle writing.
- `tests/test_acquisition_benchmark.py` — Locked the deterministic ranking and repository-backed benchmark fact collection contract.
- `tests/test_acquisition_benchmark_cli.py` — Covered spec-file CLI flows, report redaction, and direct re-rendering of saved VPS runner bundles.
- `tests/test_vps_benchmark_runner.py` — Covered preserve-live execution, destructive labeling, failure-path bundle persistence, and unattended SSH/env transport behavior.
- `README.md` — Documented the benchmark CLI flow, artifact contract, and the fact that acquisition-benchmark-report accepts saved VPS runner bundles.
- `.gsd/milestones/M003/M003-RESEARCH.md` — Recorded the real VPS baseline finding and refreshed the research artifact with the measured short-window FR baseline metrics.
- `.gsd/milestones/M003/benchmarks/baseline-fr-page1.json` — Persisted the durable named FR baseline benchmark bundle for downstream mechanical comparisons.
- `.gsd/milestones/M003/benchmarks/baseline-fr-page1.md` — Persisted the human-readable FR baseline benchmark summary and leaderboard output.
- `.gsd/PROJECT.md` — Refreshed project state and verification notes to include the completed S01 benchmark substrate and direct runner-bundle re-render proof.
- `.gsd/KNOWLEDGE.md` — Added the reusable rule that acquisition-benchmark-report can consume full VPS runner bundles directly via the nested benchmark_report field.
