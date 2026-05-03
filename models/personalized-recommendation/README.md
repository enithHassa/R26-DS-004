# `models/personalized-recommendation/`

ML package for **Component 3 — Personalized Recommendation & Predictive Impact
Modeling Engine**. Everything in this folder is offline code: training,
evaluation, and any other work that produces artifacts the service loads at
runtime. The running FastAPI service lives in
`backend/comp-personalized-recommendation/` and only reads the artifacts this
package writes.

## Layout

```
models/personalized-recommendation/
├── data/         # Synthetic dataset generator, cleaning, train/val/test splits
├── features/     # Feature engineering, eligibility flags, derived inputs
├── ranking/      # LightGBM LambdaMART trainer + inference wrapper + SHAP
├── impact/       # Monte Carlo projection engine for predictive impact (FR8)
├── evaluation/   # NDCG/MAP, ablations, backtesting, fairness checks
├── rules/        # YAML rule packs (e.g. sl_tax_2024_25.yaml) consumed by the rules engine
└── artifacts/    # Trained model binaries, SHAP explainers, scaler state (gitignored)
```

## Phase map

| Phase | Delivers into |
| ----- | -------------- |
| 1     | `data/`, `rules/` |
| 2     | `features/` |
| 4     | `ranking/`, `artifacts/` |
| 5     | `impact/` |
| 6     | `evaluation/` |

## Environment

Use the shared ML virtualenv at the repo root:

```bash
source .venv-ml/bin/activate
pip install -r models/requirements-ml.txt
```

MLflow is wired to the local file store by default
(`MLFLOW_TRACKING_URI=file:./mlruns`); override via `.env` to point at the
compose-provided tracking server or any remote store.

## Artifact paths

The service reads artifacts via `ComponentSettings`:

- `COMP_RECOMMENDATION_RULES_PATH` → `rules/sl_tax_2024_25.yaml`
- `COMP_RECOMMENDATION_ARTIFACTS_DIR` → `artifacts/`

Keep those paths stable when publishing new model versions; add version
subfolders inside `artifacts/` (e.g. `artifacts/ltr/v0.1.0/`) rather than
renaming the top-level directory.
