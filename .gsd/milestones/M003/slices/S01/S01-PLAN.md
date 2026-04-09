# S01: Acquisition Benchmark Scorecards + VPS Experiment Harness

**Goal:** Build the benchmark and reporting substrate that will decide every later optimization by measured VPS outcomes rather than theory.
**Demo:** After this: After this: one command can run comparable VPS acquisition experiments and produce a leaderboard ranking profiles by net new listings/hour, duplicate ratio, challenge rate, bytes/new listing, and resource footprint.

## Tasks
- [x] **T01: Added the acquisition benchmark service contract with repository-window ingestion, explicit score fields, and deterministic leaderboard tests.** — Why: Later slices need one stable definition of “better”, or the project will regress into intuition-led tuning.
Do:
- Add a benchmark domain/service that normalizes experiment config, run windows, and outcome metrics from discovery runs, catalog scans, runtime cycles, and DB/file growth.
- Define explicit score fields for net new listings per hour, duplicate ratio, challenge/degraded counts, bytes per new listing, and CPU/RAM snapshots.
- Reuse the existing price-filter and long-run audit patterns where they already fit instead of inventing a second reporting style.
Done when:
- The benchmark service can ingest synthetic fixtures and render a deterministic winner table from stored run facts.
  - Estimate: 1.5h
  - Files: vinted_radar/services/acquisition_benchmark.py, vinted_radar/repository.py, vinted_radar/db.py, tests/test_acquisition_benchmark.py
  - Verify: python -m pytest tests/test_acquisition_benchmark.py -q
- [x] **T02: Added acquisition benchmark CLI commands that build redacted leaderboard artifacts from spec files or saved experiment bundles.** — Why: The scorecard is only useful if operators and auto-mode can run it through first-class commands.
Do:
- Add CLI commands to run benchmark comparisons, inspect leaderboards, and export JSON/Markdown artifacts.
- Keep outputs safe for logs: redact proxy credentials, avoid secret leakage, and include explicit artifact paths.
- Make the rendered reports explain methodology, compared profiles, and why a winner ranked above alternatives.
Done when:
- A benchmark run can be launched and rendered entirely through CLI entrypoints without ad hoc notebooks or manual SQL.
  - Estimate: 1h
  - Files: vinted_radar/cli.py, vinted_radar/services/acquisition_benchmark.py, tests/test_acquisition_benchmark_cli.py, README.md
  - Verify: python -m pytest tests/test_acquisition_benchmark.py tests/test_acquisition_benchmark_cli.py -q
- [x] **T03: Added a VPS benchmark runner that snapshots the live DB safely, executes bounded remote acquisition cycles, and emits local benchmark bundles with resource evidence.** — Why: The user explicitly wants the system to test itself on the real VPS, not rely on copied shell output.
Do:
- Create a remote benchmark runner script that connects to the VPS, launches bounded experiments with safe configs, collects resulting DB/metric snapshots, and writes local JSON/Markdown artifacts under `.gsd/milestones/M003/benchmarks/`.
- Ensure the runner can preserve the live service posture when required and can label destructive vs non-destructive modes clearly.
- Include resource snapshots (`ps`, `vmstat`, disk growth) in the collected artifact bundle.
Done when:
- One script can drive a bounded VPS experiment end to end and leave a reproducible artifact bundle behind.
  - Estimate: 1.5h
  - Files: scripts/run_vps_benchmark.py, tests/test_vps_benchmark_runner.py, .gsd/milestones/M003/benchmarks/.gitkeep
  - Verify: python -m pytest tests/test_vps_benchmark_runner.py -q
- [x] **T04: Captured the real VPS baseline artifact and hardened the benchmark runner for unattended SSH execution.** — Why: The milestone needs a real baseline floor before any optimization claims can be judged.
Do:
- Use the new runner to benchmark the current FR `page_limit=1` production-like profile on the real VPS.
- Persist the JSON/Markdown outputs under `.gsd/milestones/M003/benchmarks/` and summarize the baseline in the milestone research artifact.
- Capture enough window length to normalize run cadence, duplicates, challenge pressure, and storage growth.
Done when:
- The repo contains a durable baseline artifact future slices can compare against mechanically.
  - Estimate: 1h
  - Files: scripts/run_vps_benchmark.py, .gsd/milestones/M003/M003-RESEARCH.md
  - Verify: python scripts/run_vps_benchmark.py --host 46.225.113.129 --profile baseline-fr-page1 --duration-minutes 90 --output .gsd/milestones/M003/benchmarks/baseline-fr-page1.json --markdown .gsd/milestones/M003/benchmarks/baseline-fr-page1.md
