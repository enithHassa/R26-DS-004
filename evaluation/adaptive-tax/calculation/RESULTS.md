# Calculation accuracy

## Method

Named golden examples under [`models/adaptive-tax/examples/`](../../models/adaptive-tax/examples/).

```powershell
$env:PYTHONPATH = "backend/comp-adaptive-tax;$PWD"
$env:COMP_ADAPTIVE_TAX_KG_MODE = "file"
.\.venv-backend\Scripts\python.exe -m pytest backend/comp-adaptive-tax/tests/test_rule_engine_examples.py -q --tb=short
```

- **ex01–ex08:** core Phase 3/4 + dual-YA Sec 52 (`ex08` expands to multiple variants)
- **ex09–ex17:** Phase 5 covered-area goldens (First Schedule edges, carry-forward, donations, employment FWH, business, investment, APIT credit)

## Phase 6 filing-line regression

Included in Phase 6.9 runner (`evaluation/adaptive-tax/phase6/run_chapter4_metrics.py`):

```powershell
$env:PYTHONPATH = "backend/comp-adaptive-tax;$PWD"
$env:COMP_ADAPTIVE_TAX_KG_MODE = "file"
$env:COMP_ADAPTIVE_TAX_PROVENANCE_MODE = "strict"
.\.venv-backend\Scripts\python.exe -m pytest `
  backend/comp-adaptive-tax/tests/test_phase6_foundation.py `
  backend/comp-adaptive-tax/tests/test_phase68_viva.py `
  backend/comp-adaptive-tax/tests/test_employment_sec5.py `
  backend/comp-adaptive-tax/tests/test_investment_income.py `
  backend/comp-adaptive-tax/tests/test_sec52_qualifying_payments.py `
  backend/comp-adaptive-tax/tests/test_business_income.py `
  backend/comp-adaptive-tax/tests/test_other_income.py `
  backend/comp-adaptive-tax/tests/test_qp_ya_acceptance.py -q --tb=short
```

## RESULTS

| Date (UTC+5:30) | Command | Result |
|-----------------|---------|--------|
| 2026-08-03 | `pytest .../test_rule_engine_examples.py` | **11 passed** covering **ex01–ex08** |
| 2026-08-07 | Phase 5.9 `run_chapter4_metrics.py` | **23 passed** covering **17** example files (**ex01–ex17**) |
| 2026-08-11 | Phase 6.9 `run_chapter4_metrics.py` | Phase 5 goldens + filing-line suite (see latest `runs/phase6_9_*.json`) |

Dissertation Chapter 4 claim: **calculation accuracy = all covered-area goldens pass** (ex01–ex08 required; ex09–ex17 included for Phase 5 areas). Phase 6 adds catalog filing-line regression on top.
