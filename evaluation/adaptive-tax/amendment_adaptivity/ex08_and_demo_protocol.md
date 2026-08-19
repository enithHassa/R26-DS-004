# Amendment adaptivity — ex08 + Phase 4/5 demo protocol

## Purpose

Show that YA / Act 02/2025 Section 52 cap change (1.2M → 1.8M) changes tax for the same inputs.

**Primary viva path (Phase 5.4):** switch `assessment_year` on ex08 — no approve required.

## Offline fixtures

| Case | Path | Expectation |
|------|------|-------------|
| ex08 YA 2024/25 | [`ex08_post_amendment_sec52.json`](../../../models/adaptive-tax/examples/ex08_post_amendment_sec52.json) variant `ex08_ya_2024_25` | tax `42000` (cap 1.2M, QP 1.5M) |
| ex08 YA 2025/26 | same file, variant `ex08_ya_2025_26` | tax `0` (cap 1.8M + personal relief 1.8M) |
| ex10 carry-forward | [`ex10_qp_carry_forward.json`](../../../models/adaptive-tax/examples/ex10_qp_carry_forward.json) | bf 800k + QP 500k → allowed 1.3M; carry_out 500k |
| Demo ex04 (optional) | [`ex04_salary_qualifying_payment.json`](../../../models/adaptive-tax/examples/ex04_salary_qualifying_payment.json) + runtime override | T1 `36000` → T2 `0` |

Abs delta ex08: `|42000 - 0| = 42000`.

## Score offline (no HTTP)

```powershell
$env:PYTHONPATH = "backend/comp-adaptive-tax;$PWD"
.\.venv-backend\Scripts\python.exe evaluation/adaptive-tax/amendment_adaptivity/score_adaptivity.py
```

## Live demo (HTTP)

```powershell
.\.venv-backend\Scripts\python.exe scripts/adaptive_tax_phase4_demo.py --allow-stub-pdf
# Optional legacy approve path:
.\.venv-backend\Scripts\python.exe scripts/adaptive_tax_phase4_demo.py --allow-stub-pdf --with-approve
```

See runbook: **Adaptive Tax Phase 4 — Viva demo**.
