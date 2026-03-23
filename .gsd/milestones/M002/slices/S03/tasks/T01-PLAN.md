---
estimated_steps: 4
estimated_files: 7
skills_used:
  - best-practices
  - test
  - review
---

# T01: Introduce the proxy-aware serving contract and stable product routes

**Slice:** S03 — Responsive French Product Shell + VPS Serving Path
**Milestone:** M002

## Description

Load `best-practices`, `test`, and `review` before coding. This task closes the remote-serving gap before visual polish can be trusted. The dashboard must stop assuming localhost-only links and expose stable HTML routes for runtime and listing detail so the shared shell has real product endpoints to wrap.

## Steps

1. Extend `vinted_radar/dashboard.py` route helpers so URL generation can honor a configured external/base URL or reverse-proxy base path instead of baking in localhost assumptions.
2. Add an HTML `/listings/<id>` route that reuses the existing repository/detail payload boundary while keeping `/api/listings/<id>` as the machine-readable proof surface.
3. Update `vinted_radar/cli.py`, `README.md`, and `install_services.sh` so local/VPS serving instructions and printed URLs match the new route/base-url contract.
4. Add `scripts/verify_vps_serving.py` plus route/CLI regressions that prove `/`, `/explorer`, `/runtime`, `/listings/<id>`, and `/health` stay healthy behind the configured base URL.

## Must-Haves

- [ ] Route generation supports a proxy/base-url aware serving posture instead of hardcoding localhost semantics.
- [ ] HTML listing-detail and runtime routes exist as first-class product endpoints without breaking the current JSON diagnostics routes.
- [ ] Operator docs and install scripts advertise one consistent serving contract that a VPS deployment can actually follow.

## Verification

- `python -m pytest tests/test_dashboard.py tests/test_dashboard_cli.py`
- `python scripts/verify_vps_serving.py --base-url http://127.0.0.1:8782 --listing-id 9101`

## Observability Impact

- Signals added/changed: base-url / route-generation behavior, HTML route availability for detail/runtime, and route-level VPS smoke-check output.
- How a future agent inspects this: run `python scripts/verify_vps_serving.py --base-url ... --listing-id ...`, inspect printed dashboard URLs from `python -m vinted_radar.cli dashboard ...`, and hit `/health` plus the HTML routes through the configured base URL.
- Failure state exposed: localhost-only links, missing HTML detail/runtime routes, or proxy/base-path regressions fail explicitly in route tests and the smoke verifier.

## Inputs

- `vinted_radar/dashboard.py` — current route map and URL generation logic that still assumes a local serving posture.
- `vinted_radar/cli.py` — dashboard command output that needs to print the new shared route set truthfully.
- `README.md` — current local/VPS usage docs that still describe a narrower route posture.
- `install_services.sh` — current service installer that needs to align with the new serving contract.
- `tests/test_dashboard.py` — existing WSGI route regressions that should expand to the new HTML detail/runtime path.
- `tests/test_dashboard_cli.py` — CLI output coverage that should reflect the revised URLs.

## Expected Output

- `vinted_radar/dashboard.py` — proxy-aware route/base-url handling plus first-class HTML detail/runtime endpoints.
- `vinted_radar/cli.py` — dashboard command output aligned with the new route contract.
- `README.md` — updated local/VPS serving instructions that no longer assume localhost-only navigation.
- `install_services.sh` — service defaults/documentation aligned with the revised serving posture.
- `scripts/verify_vps_serving.py` — repeatable smoke verifier for base URL, route health, and HTML route reachability.
- `tests/test_dashboard.py` — route regression coverage for the new HTML/product endpoints.
- `tests/test_dashboard_cli.py` — CLI output coverage for the revised dashboard/runtime/detail URLs.
