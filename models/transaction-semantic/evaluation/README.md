# Evaluation & path registry

- **`artifact_paths.json`** — stable pointers to each model’s **`v0.1.0`** bundle under `../artifacts/`. Use this from services or scripts instead of hard-coding paths.
- **`model_runs_compare.csv`** *(optional)* — copy your Colab / Drive comparison sheet here if you want it versioned next to the path registry.
- **`generate_paper_figures.py`** — IEEE one-column PNGs/PDFs for Results (F1 comparison + DistilBERT confusion matrix). Outputs under **`figures/`**.

```bash
MPLCONFIGDIR=/tmp/matplotlib \
  .venv-ml/bin/python models/transaction-semantic/evaluation/generate_paper_figures.py
```

Requires DistilBERT export CSVs from Colab Cell 9b:
`artifacts/distilbert_multilingual/v0.1.0/export/confusion_matrix_test.csv`.

When you train **`v0.2.0`**, add sibling folders under each `artifacts/<model>/`, update the JSON, and keep old versions until the API no longer needs them.
