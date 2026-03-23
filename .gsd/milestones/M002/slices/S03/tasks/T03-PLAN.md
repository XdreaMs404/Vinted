---
estimated_steps: 4
estimated_files: 5
skills_used:
  - agent-browser
  - best-practices
  - test
  - review
---

# T03: Validate phone/desktop consultation and ship the VPS operator path

**Slice:** S03 — Responsive French Product Shell + VPS Serving Path
**Milestone:** M002

## Description

Load `agent-browser`, `best-practices`, `test`, and `review` before coding. Once the routes and shell exist, S03 still needs one trustworthy operating path. This task tightens service/docs around the new product routes and makes the smoke verifier the normal way to prove a local or VPS instance is actually serving the product correctly.

## Steps

1. Finish the operator-facing README guidance for local and VPS serving around the new overview/explorer/runtime/detail shell.
2. Align `install_services.sh` with the route contract so a systemd deployment advertises the same URLs and health expectations the product now uses.
3. Extend `scripts/verify_vps_serving.py` and CLI smoke coverage so route reachability, health, and shared-shell assumptions can be checked from one explicit command.
4. Run the local dashboard plus browser verification at desktop and mobile widths, then tighten any drift between docs, CLI output, and actual served routes.

## Must-Haves

- [ ] There is one documented operator path for local and VPS serving of the shared shell.
- [ ] The smoke verifier checks the same routes the product expects users to consult remotely.
- [ ] CLI output, docs, and service defaults all describe the same serving posture.

## Verification

- `python scripts/verify_vps_serving.py --base-url http://127.0.0.1:8782 --listing-id 9101`
- `python -m pytest tests/test_cli_smoke.py tests/test_dashboard_cli.py`

## Inputs

- `README.md` — T01 documentation baseline that now needs final operator guidance.
- `install_services.sh` — systemd installer that must align with the shared shell route set.
- `scripts/verify_vps_serving.py` — smoke verifier introduced in T01 and extended here.
- `tests/test_cli_smoke.py` — CLI smoke seam for operator-facing route/output checks.
- `tests/test_dashboard_cli.py` — dashboard command coverage that should remain aligned with the documented URLs.

## Expected Output

- `README.md` — finalized local/VPS operator guide for the shared shell.
- `install_services.sh` — service setup aligned with the actual product routes and health checks.
- `scripts/verify_vps_serving.py` — complete route/health smoke verifier for shared-shell deployments.
- `tests/test_cli_smoke.py` — CLI smoke coverage for the VPS/local operator path.
- `tests/test_dashboard_cli.py` — dashboard command coverage aligned with the final documented route set.
