# S02: Start-to-Start Multi-Lane Runtime Control — UAT

**Milestone:** M003
**Written:** 2026-04-10T09:17:53.468Z

# S02: Start-to-Start Multi-Lane Runtime Control — UAT

**Milestone:** M003  
**Slice:** S02  
**Status:** passed

## Preconditions

- Work from `C:\Users\Alexis\Documents\VintedScrap2`.
- Local Python entrypoint is `python`.
- Approved VPS access works through `bash scripts/vpsctl.sh ...`.
- The live VPS services are running on the synced S02 code.

## Test Case 1 — Local lane-aware repository/runtime/dashboard contracts are green

1. Run:
   `python -m pytest tests/test_runtime_repository.py tests/test_runtime_service.py tests/test_runtime_cli.py tests/test_dashboard.py tests/test_vps_benchmark_runner.py tests/test_http.py -q`
2. **Expected:** exit code 0.
3. **Observed:** pass (`67 passed`).
4. **Observed proof:**
   - lane-aware controller state can be queried without ambiguity
   - benchmark-triggered lanes can force immediate start over a persisted future schedule
   - top-level runtime truth aggregates from active lane views during multi-lane windows
   - CLI/runtime dashboard surfaces expose lane summaries and redact credentials
   - legacy `runtime_cycles` databases reopen after adding `lane_name`

## Test Case 2 — Live VPS serving is back on the lane-aware runtime stack

1. Restart the public services on the VPS after syncing the S02 code.
2. Open `http://46.225.113.129:8765/runtime`.
3. Open `http://46.225.113.129:8765/api/runtime`.
4. Open `http://46.225.113.129:8765/health`.
5. **Expected:** all three routes return HTTP 200, `lane_summaries` is present again, and the public services return to `active` after benchmark windows.
6. **Observed:** pass.

## Test Case 3 — Canonical 30-minute dual-lane VPS proof bundle

1. Run the exact slice-plan command:
   `python scripts/run_vps_benchmark.py --host 46.225.113.129 --profile dual-lane-smoke --duration-minutes 30 --verify-base-url http://46.225.113.129:8765 --output .gsd/milestones/M003/benchmarks/dual-lane-smoke.json --markdown .gsd/milestones/M003/benchmarks/dual-lane-smoke.md`
2. **Expected:** exit code 0.
3. **Expected:** both files exist:
   - `.gsd/milestones/M003/benchmarks/dual-lane-smoke.json`
   - `.gsd/milestones/M003/benchmarks/dual-lane-smoke.md`
4. Inspect the JSON bundle.
5. **Observed:** pass.
6. **Observed proof:**
   - `remote_result.ok == true`
   - `serving_verification.ok == true`
   - `lane_results` contains both `frontier` and `expansion`
   - each lane completed two cycles in the bounded window
   - benchmark window: `2026-04-10T08:51:06+00:00` → `2026-04-10T09:06:37+00:00`

## Test Case 4 — Post-run public serving posture is restored

1. Run a follow-up assertion against the final bundle and the public routes.
2. **Expected:** bundle still satisfies the proof contract and `/runtime`, `/api/runtime`, `/health` each return HTTP 200 after the benchmark ends.
3. **Observed:** pass (`bundle-and-serving-ok`).

## Edge Cases Verified During Closeout

### Edge Case A — Explicit benchmark windows inheriting a future live `next_resume_at`
- **Observed before fix:** the benchmark could wait through most of its window instead of starting immediately.
- **Resolution:** benchmark-triggered lanes now force an immediate start.

### Edge Case B — Orphaned benchmark exports filling the VPS disk
- **Observed before fix:** repeated interrupted runs left many `*.benchmark-export-*.db` files on `/root/Vinted/data`, Docker PostgreSQL became unhealthy, and frontier cycles failed on recovery-mode connection errors.
- **Resolution:** stale exports were removed, PostgreSQL recovered, and the multi-lane proof path now avoids remote snapshot export churn.

### Edge Case C — Sequential endpoint transition races during serving verification
- **Observed before fix:** a healthy `running` → `scheduled` transition between separate `/runtime` / `/api/runtime` / `/health` reads could be misclassified as drift.
- **Resolution:** the verifier now tolerates healthy transition races while still failing real route or health breakage.

## Acceptance Status

- **Passed:** Test cases 1–4.
- **Final verdict:** S02 acceptance passed on the live VPS.
