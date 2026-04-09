---
estimated_steps: 7
estimated_files: 5
skills_used: []
---

# T03: Expose market-aware diagnostics without breaking FR defaults

Why: Operators and product surfaces need to understand which market a run or listing belongs to once multiple domains exist.
Do:
- Extend CLI/runtime/product query surfaces with market filters and diagnostics where needed.
- Preserve a French-first default product surface while making cross-market operation inspectable for operators and benchmark artifacts.
- Ensure benchmark, runtime, and error payloads always carry market identity.
Done when:
- Existing FR flows still work by default and market-specific flows are inspectable through automated tests.

## Inputs

- `vinted_radar/cli.py`
- `vinted_radar/dashboard.py`

## Expected Output

- `market-aware runtime/benchmark/CLI surfaces`
- `FR-compatible operator defaults`

## Verification

python -m pytest tests/test_runtime_cli.py tests/test_dashboard.py tests/test_clickhouse_queries.py -q
