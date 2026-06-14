# `evaluation/` — Phase 6

Offline evaluation for the personalized recommendation engine.

## Modules

| File | Purpose |
|------|---------|
| `metrics.py` | NDCG@k, MAP@5, MRR, hit@1, precision@5; adoption F1/AUC |
| `dataset.py` | Build ranking/adoption tensors from synthetic profile CSV |
| `fairness.py` | Segment metrics by occupation and income decile |
| `ablation.py` | Rules, feasibility, adoption, LambdaMART ablation arms |
| `runner.py` | Orchestrate frozen-artifact eval + ablations |
| `explainability.py` | SHAP TreeExplainer for pair-wise LambdaMART |
| `report.py` | `EvaluationReport` JSON export |

## CLI

From repo root (requires profile CSV with `split` column):

```bash
.venv-backend/bin/python scripts/run_phase6_evaluation.py \
  --csv "data/synthetic/profiles_corrected_tax (1).csv" \
  --catalog models/personalized-recommendation/rules/strategy_catalog.yaml \
  --user-meta backend/comp-personalized-recommendation/app/artifacts/user_feature_meta.json \
  --artifacts-dir backend/comp-personalized-recommendation/app/artifacts \
  --out-json reports/phase6_eval.json
```

Use `--no-ablation` to evaluate frozen artifacts only (faster).

## API (runtime)

`POST /api/v1/recommendations/explain` — SHAP explanation for `{ profile_id, strategy_code }`.

Requires Phase 4 artifacts and `shap` installed in the service environment.
