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

## Retraining from real user data (answers → retrain → better recommendations)

Once taxpayers have submitted behavioural answers and given adoption feedback
("I've done this" / "Not for me" on a recommendation), that data can replace
the synthetic, rules-derived adoption labels the model otherwise trains on.

1. **Export.** From repo root, with the backend's database reachable
   (`DATABASE_MODE`/connection env vars set as the API server itself uses):

   ```
   .venv-backend/bin/python scripts/export_training_data.py \
     --out data/exports/real_training_data.csv
   ```

   Only profiles with at least one `recommendation_feedback` row are
   included by default (`--include-unlabelled` to also export the rest, for
   feature-coverage inspection — those rows carry no real label signal).

2. **Train.** Point `train_phase4_ranking_adoption.py` at that export instead
   of the synthetic CSV:

   ```
   .venv-backend/bin/python scripts/train_phase4_ranking_adoption.py \
     --csv data/exports/real_training_data.csv \
     --catalog models/personalized-recommendation/rules/strategy_catalog.yaml \
     --out-dir backend/comp-personalized-recommendation/app/artifacts
   ```

   The script auto-detects real `adopted__<STRATEGY_CODE>` columns in the
   CSV and uses them as ground truth in place of the synthetic
   eligibility-bit/legacy-matcher labels — printed to stdout as
   `Using real adoption labels from N adopted__* column(s)`. `model_version.txt`
   is written as `phase4-lambdarank-adoption-v1-real-<UTC timestamp>` (or
   `-synthetic-` if no real labels were found in the input), so each retrain
   is distinguishable in the `Recommendation.model_version` column now that
   recommendations are actually persisted.

3. **Deploy.** Restart the FastAPI process. `load_inference_artifacts()` is
   process-cached (`@lru_cache`), so a running server will keep using the old
   artifacts until restarted — there is no hot-reload.

**Not automated yet, by design (documented, not silently missing):** there is
no scheduler/CI job that runs steps 1–3 on a cadence — this stays a manual
command until real feedback volume justifies the extra infrastructure. Real
retraining also needs a meaningful number of real feedback rows before it can
plausibly out-perform the current synthetic-trained model; on day one of
collecting feedback this will not show a visible difference.
