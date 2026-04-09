# S01: Acquisition Benchmark Scorecards + VPS Experiment Harness — UAT

**Milestone:** M003
**Written:** 2026-04-09T13:49:24.241Z

# S01 UAT — Acquisition Benchmark Scorecards + VPS Experiment Harness

## Preconditions
- Use the repository root `C:\Users\Alexis\Documents\VintedScrap2`.
- Python environment is available locally via `python`.
- VPS SSH access is configured through the repo-local `.env.vps` file and the approved host `46.225.113.129` is reachable.
- The remote host still has the project checkout at `/root/Vinted` and the usable interpreter at `/root/Vinted/venv/bin/python`.

## Test Case 1 — Local benchmark contract stays green
1. Run `python -m pytest tests/test_acquisition_benchmark.py tests/test_acquisition_benchmark_cli.py tests/test_vps_benchmark_runner.py -q`.
   - Expected: exit code 0.
   - Expected: all benchmark, CLI, and VPS runner tests pass (currently 12 passed).
2. Confirm the test run covers the CLI/report flow and VPS runner path rather than only pure service functions.
   - Expected: `tests/test_acquisition_benchmark_cli.py` and `tests/test_vps_benchmark_runner.py` both execute.

## Test Case 2 — Saved VPS bundle can be re-rendered directly
1. Run `python -m vinted_radar.cli acquisition-benchmark-report --input .gsd/milestones/M003/benchmarks/_closeout-baseline-fr-page1.json --format markdown`.
   - Expected: exit code 0.
   - Expected: markdown output includes `## Leaderboard`, winner `baseline-fr-page1`, and the FR baseline metrics from the saved bundle.
2. Inspect the rendered output for secret leakage.
   - Expected: no raw proxy passwords, tokens, or credential-bearing DSNs appear in stdout.
3. Confirm the command works against the full runner bundle path without manually extracting `benchmark_report` first.
   - Expected: no JSON-shape error is raised.

## Test Case 3 — Run a fresh bounded preserve-live VPS experiment
1. Run:
   `python scripts/run_vps_benchmark.py --host 46.225.113.129 --profile baseline-fr-page1 --duration-minutes 2 --output .gsd/milestones/M003/benchmarks/_uat-baseline-fr-page1.json --markdown .gsd/milestones/M003/benchmarks/_uat-baseline-fr-page1.md`
   - Expected: exit code 0.
   - Expected: the command prints the JSON artifact path, Markdown artifact path, preserve-live mode, experiment window, and cycle count.
2. Open `.gsd/milestones/M003/benchmarks/_uat-baseline-fr-page1.md`.
   - Expected: the file exists and contains sections for Execution posture, Profile, Remote experiment window, Cycle outcomes, Resource snapshots, and Acquisition benchmark report.
3. Verify preserve-live posture in the markdown artifact.
   - Expected: `Mode: preserve-live`, `Destructive: no`, and wording that the live DB plus live services remain untouched.
4. Verify the artifact contains observed benchmark metrics.
   - Expected: leaderboard row includes net new listings/hour, duplicate ratio, challenge rate, degraded count, bytes/new listing, mean CPU, and peak RAM.

## Test Case 4 — Artifact bundle is mechanically reusable by later slices
1. Run `python -m vinted_radar.cli acquisition-benchmark-report --input .gsd/milestones/M003/benchmarks/_uat-baseline-fr-page1.json --json-out .gsd/milestones/M003/benchmarks/_uat-rerender.json --markdown-out .gsd/milestones/M003/benchmarks/_uat-rerender.md`.
   - Expected: exit code 0.
   - Expected: both rerendered artifact files are written.
2. Compare `_uat-baseline-fr-page1.md` and `_uat-rerender.md` at a high level.
   - Expected: both describe the same profile, methodology, and winner ordering logic, even if timestamps differ.
3. Confirm the rerendered JSON is safe to share.
   - Expected: redacted credential-bearing fields remain masked.

## Edge Cases
- If the remote host falls back to bare `python3` and fails to import `typer`, the runner must still surface a truthful failure bundle instead of silently succeeding.
- If a later slice passes a raw experiments array or a full report JSON instead of a runner bundle, `acquisition-benchmark-report` should still render successfully.
- If a benchmark profile writes no secrets, the report should remain unchanged except for normal redaction-safe formatting.

## Acceptance Notes
- This slice is accepted when the benchmark contract is green locally, a real preserve-live VPS benchmark writes durable artifacts, and those saved runner bundles can be re-rendered directly through the CLI without manual JSON extraction.
