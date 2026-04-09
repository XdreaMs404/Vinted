---
estimated_steps: 7
estimated_files: 4
skills_used: []
---

# T01: Add a market registry and domain adapter layer

Why: Multi-market work is unsafe until base URLs, headers, and seed discovery are controlled through one contract.
Do:
- Add a market registry/domain adapter layer describing catalog roots, domain URLs, locale headers, and operator-visible market codes.
- Refactor discovery and HTTP entrypoints to consume that registry instead of embedding `vinted.fr` constants in multiple places.
- Keep FR as the default market so existing scripts still have a safe fallback.
Done when:
- Discovery and HTTP tests can build requests for more than one supported market domain from one explicit registry.

## Inputs

- `vinted_radar/services/discovery.py`
- `vinted_radar/http.py`

## Expected Output

- `vinted_radar/markets.py`
- `tests/test_market_registry.py`

## Verification

python -m pytest tests/test_market_registry.py tests/test_http.py -q
