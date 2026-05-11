# Transaction semantic — trained artifacts (local / release)

Large binaries are **not committed** (root `.gitignore`: `*.joblib`, `*.safetensors`, …). This folder holds copies from Colab/Drive for local inference.

## Layout (current)

```
artifacts/
├── tfidf_logreg/v0.1.0/
│   ├── tfidf_logreg_pipeline.joblib
│   └── export/
├── xlm_roberta/v0.1.0/
│   ├── hf_model/
│   └── export/
└── distilbert_multilingual/v0.1.0/
    ├── hf_model/
    └── export/
```

**Note:** The DistilBERT bundle was normalized under `distilbert_multilingual/` (typo `istilbert_*` removed).

## Versioning

- **`v0.1.0`** — first bundled checkpoint set in-repo.
- For **`v0.2.0`**, duplicate the tree, retrain, then point **`evaluation/artifact_paths.json`** at the new folder.

Machine-readable paths for code: **`../evaluation/artifact_paths.json`**.
