---
estimated_steps: 5
estimated_files: 10
skills_used:
  - test
  - review
---

# T01: Harden state refresh transport and persist probe degradation telemetry

**Slice:** S06 — Acquisition Hardening + Degraded-Mode Visibility
**Milestone:** M002

## Description

Load `test` and `review` before coding. This task hardens the weak acquisition seam itself: item-page probes need proxy support, explicit challenge classification, and persisted degradation telemetry that later product surfaces can trust.

## Steps

1. Extend item-page parsing so 403/429/challenge-shaped pages and transport failures are classified distinctly instead of collapsing into generic `unknown`.
2. Make `build_default_state_refresh_service()` proxy-aware and thread proxy pools through runtime and standalone CLI entrypoints.
3. Add a structured state-refresh probe summary to `StateRefreshReport` and persist it on runtime cycles / runtime status.
4. Keep runtime config redaction intact while exposing only safe acquisition-health diagnostics.
5. Add regression coverage for parser classification, proxy forwarding, runtime persistence, and CLI output.

## Must-Haves

- [ ] Anti-bot / challenge-shaped probe failures are explicitly detectable in parser output or persisted probe summary.
- [ ] Proxy pools reach state refresh in both `batch`/`continuous` runtime flows and the standalone `state-refresh` command.
- [ ] Latest runtime cycle / runtime-status surfaces include structured probe degradation summary, not only a probe count.

## Verification

- `python -m pytest tests/test_item_page_parser.py tests/test_runtime_service.py tests/test_runtime_repository.py tests/test_runtime_cli.py`

## Observability Impact

- Signals added/changed: state-refresh probe degradation summary, anti-bot / HTTP / exception counts, sanitized proxy-aware runtime config.
- How a future agent inspects this: `python -m vinted_radar.cli runtime-status --db <db> --format json`, `python -m vinted_radar.cli state-refresh --db <db> --format json`, latest runtime cycle payloads.
- Failure state exposed: degraded probe counts/reasons stay persisted even when state evaluation falls back to cautious history.

## Inputs

- `vinted_radar/parsers/item_page.py` — current probe classification logic.
- `vinted_radar/services/state_refresh.py` — current probe loop and default factory.
- `vinted_radar/services/runtime.py` — current runtime wiring around state refresh.
- `vinted_radar/repository.py` — runtime-cycle persistence and runtime-status hydration.
- `vinted_radar/db.py` — runtime schema / migrations.
- `vinted_radar/cli.py` — direct `state-refresh` entrypoint and runtime option plumbing.

## Expected Output

- `vinted_radar/parsers/item_page.py` — explicit challenge/degradation classification.
- `vinted_radar/services/state_refresh.py` — proxy-aware refresh factory plus structured probe summary.
- `vinted_radar/services/runtime.py` — persisted state-refresh summary on completed runtime cycles.
- `vinted_radar/repository.py` — runtime-cycle and runtime-status hydration for acquisition telemetry.
- `vinted_radar/db.py` — any schema/migration support needed for the persisted summary.
- `vinted_radar/cli.py` — proxy-aware standalone state-refresh command and updated runtime report output.
- `tests/test_item_page_parser.py` — parser coverage for degraded/challenge responses.
- `tests/test_runtime_service.py` — proxy forwarding + persisted summary coverage.
- `tests/test_runtime_repository.py` — acquisition telemetry visibility in runtime status.
- `tests/test_runtime_cli.py` — CLI coverage for proxy/state-refresh/runtime output.
