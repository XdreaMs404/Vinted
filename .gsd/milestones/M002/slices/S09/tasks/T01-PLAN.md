---
estimated_steps: 5
estimated_files: 7
skills_used:
  - code-optimizer
  - test
---

# T01: Establish the Webshare proxy-pool contract and safe operator inputs

**Slice:** S09 — High-Throughput Proxy Pool + Webshare Acquisition Operator Flow
**Milestone:** M002

## Description

Turn the provided Webshare pool into a real operator input contract instead of an ad hoc command-line hack. The task must accept raw `host:port:user:pass` entries, support a gitignored local proxy file, and keep runtime/config surfaces credential-safe.

## Steps

1. Add a dedicated proxy helper module that normalizes raw Webshare entries and URL-form proxies into one canonical internal form.
2. Add CLI/runtime helpers for repeatable `--proxy`, `--proxy-file`, and implicit local `data/proxies.txt` loading.
3. Persist only safe proxy-pool metadata such as pool size / transport mode, never raw credentials, in runtime-facing config.
4. Update the relevant CLI help text and README operator guidance for the new local proxy contract.
5. Add regression coverage for parsing, file loading, and CLI forwarding behavior.

## Must-Haves

- [ ] Raw Webshare entries and proxy URLs normalize into one canonical proxy form.
- [ ] `discover`, `batch`, `continuous`, and `state-refresh` can all load the same local proxy file contract.
- [ ] Runtime-facing config/output expose only safe proxy-pool metadata.

## Verification

- `python -m pytest tests/test_proxy_config.py tests/test_cli_discover_smoke.py tests/test_runtime_cli.py -q`

## Observability Impact

- Signals added/changed: safe `proxy_pool_size` / `transport_mode` runtime config metadata and clearer operator CLI hints.
- How a future agent inspects this: `python -m vinted_radar.cli runtime-status --db <db> --format json` plus the CLI `--help` output and README examples.
- Failure state exposed: invalid proxy-file input now fails at the config boundary instead of surfacing later as opaque transport errors.

## Inputs

- `vinted_radar/cli.py` — current proxy option handling.
- `vinted_radar/services/runtime.py` — current runtime config serialization path.
- `README.md` — current operator documentation.

## Expected Output

- `vinted_radar/proxies.py` — proxy normalization and loading helpers.
- `vinted_radar/cli.py` — shared proxy-file aware operator input path.
- `vinted_radar/services/runtime.py` — safe runtime config metadata for proxy-pool activation.
- `README.md` — local proxy-file operator docs.
- `tests/test_proxy_config.py` — proxy parsing and file-loading coverage.
- `tests/test_cli_discover_smoke.py` — discover CLI forwarding coverage.
- `tests/test_runtime_cli.py` — runtime/state-refresh CLI proxy-file coverage.
