# Diagnostics scripts

These scripts are one-off probes used to inspect Vinted transport, cookies, impersonation, parser behavior, and raw API payloads.

They are **not** part of the product runtime or test suite.

## Notes

- Generated artifacts belong in `scripts/diagnostics/output/`.
- Keep production code under `vinted_radar/`.
- Keep formal tests under `tests/`.
- If a diagnostic script becomes durable, promote it into a proper CLI command or a tested helper.
