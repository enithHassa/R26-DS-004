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
