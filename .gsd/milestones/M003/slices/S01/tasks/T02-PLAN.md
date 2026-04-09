---
estimated_steps: 7
estimated_files: 4
skills_used: []
---

# T02: Add CLI and report renderers for benchmark artifacts

Why: The scorecard is only useful if operators and auto-mode can run it through first-class commands.
Do:
- Add CLI commands to run benchmark comparisons, inspect leaderboards, and export JSON/Markdown artifacts.
- Keep outputs safe for logs: redact proxy credentials, avoid secret leakage, and include explicit artifact paths.
- Make the rendered reports explain methodology, compared profiles, and why a winner ranked above alternatives.
Done when:
- A benchmark run can be launched and rendered entirely through CLI entrypoints without ad hoc notebooks or manual SQL.

## Inputs

- `vinted_radar/cli.py`
- `tests/test_price_filter_benchmark.py`

## Expected Output

- `vinted_radar/cli.py benchmark commands`
- `tests/test_acquisition_benchmark_cli.py`

## Verification

python -m pytest tests/test_acquisition_benchmark.py tests/test_acquisition_benchmark_cli.py -q
