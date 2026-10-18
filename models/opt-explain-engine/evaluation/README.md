# OE Engine evaluation

## Cohen's kappa (expert validation of relief recommendations)

Synthetic **40-taxpayer** demo (160 claim pairs):

```powershell
.\.venv-backend\Scripts\python.exe scripts/run_oe_engine_kappa.py `
  --csv models/opt-explain-engine/evaluation/fixtures/kappa_40_taxpayers.csv `
  --out-json reports/oe_engine_kappa.json
```

Regenerate labels:

```powershell
.\.venv-backend\Scripts\python.exe models/opt-explain-engine/evaluation/generate_kappa_40_taxpayers.py
```

Protocol: `KAPPA_PROTOCOL.md`
