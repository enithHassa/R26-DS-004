# `artifacts/`

Trained model binaries, serialized scalers/encoders, SHAP explainers, and
other outputs of the training pipeline. Everything in this directory is
ignored by git (see `.gitignore`) because it is reproducible from the
training code plus the rule pack.

Version bumps live as subfolders:

```
artifacts/
├── ltr/
│   ├── v0.1.0/
│   │   ├── model.txt        # LightGBM dump
│   │   ├── preprocess.joblib
│   │   └── shap_explainer.joblib
│   └── v0.2.0/
└── impact/
    └── v0.1.0/
```

The FastAPI service reads from the latest version folder it recognizes; the
version string is surfaced back to clients as `model_version` in the
recommendation response.

## Phase 4 (WP6) layout

When present next to the service (`backend/.../app/artifacts/` or
`COMP_RECOMMENDATION_ARTIFACTS_DIR`), **`phase4_manifest.json`** selects
**Phase 4** inference:

- `phase4_adoption_model.joblib` — user-level multi-label adoption (LightGBM).
- `phase4_lambdarank_model.joblib` — user×strategy LambdaMART ranker.
- `user_feature_meta.json`, `pair_feature_meta.json`, `strategy_ids.joblib`,
  optional `scoring_weights.yaml`.

Train from repo root:

`python scripts/train_phase4_ranking_adoption.py --csv <profiles.csv> --catalog models/personalized-recommendation/rules/strategy_catalog.yaml --out-dir <artifact_dir> [--legacy-matcher path/to/strategy_matcher_model.joblib]`

If `phase4_manifest.json` is missing, the service falls back to the legacy
single `strategy_matcher_model.joblib` + `feature_meta.json`.
