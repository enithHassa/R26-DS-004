# Amendment adaptivity — ex08 + Phase 4 demo protocol

## Purpose

Show that approving Act 02/2025 (Section 52 cap 1.2M → 1.8M) changes tax for the same inputs.

## Offline fixtures

| Case | Path | Expectation |
|------|------|-------------|
| ex08 pre | [`models/adaptive-tax/examples/ex08_post_amendment_sec52.json`](../../../models/adaptive-tax/examples/ex08_post_amendment_sec52.json) variant `ex08_pre_amend_2025` | tax `48000` (cap 1.2M, QP 1.5M) |
| ex08 post | same file, variant `ex08_current` | tax `18000` (cap 1.8M) |
| Demo ex04 | [`ex04_salary_qualifying_payment.json`](../../../models/adaptive-tax/examples/ex04_salary_qualifying_payment.json) + runtime override | T1 `48000` → T2 `0` |

Abs delta ex08: `|48000 - 18000| = 30000`.

## Score offline (no HTTP)

```powershell
$env:PYTHONPATH = "backend/comp-adaptive-tax;$PWD"
.\.venv-backend\Scripts\python.exe evaluation/adaptive-tax/amendment_adaptivity/score_adaptivity.py
```

## Live demo (HTTP)

```powershell
.\.venv-backend\Scripts\python.exe scripts/adaptive_tax_phase4_demo.py --allow-stub-pdf
```

See runbook: **Adaptive Tax Phase 4 — Viva demo**.
