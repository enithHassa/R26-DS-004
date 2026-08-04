# Calculation accuracy

## Method

Named golden examples `ex01`–`ex08` under [`models/adaptive-tax/examples/`](../../models/adaptive-tax/examples/).

```powershell
$env:PYTHONPATH = "backend/comp-adaptive-tax;$PWD"
$env:COMP_ADAPTIVE_TAX_KG_MODE = "file"
.\.venv-backend\Scripts\python.exe -m pytest backend/comp-adaptive-tax/tests/test_rule_engine_examples.py -q --tb=short
```

`ex08` encodes pre/post Act 02/2025 Sec 52 variants (counts as one named example with two assertions).

## RESULTS

| Date (UTC+5:30) | Command | Result |
|-----------------|---------|--------|
| 2026-08-03 | `pytest .../test_rule_engine_examples.py` | **11 passed** covering **ex01–ex08** (8/8 named examples; ex08 expands to multiple variant tests) |

Dissertation Chapter 4 claim: **calculation accuracy = 8/8**.
