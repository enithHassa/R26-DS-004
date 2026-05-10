# Evaluation & path registry

- **`artifact_paths.json`** — stable pointers to each model’s **`v0.1.0`** bundle under `../artifacts/`. Use this from services or scripts instead of hard-coding paths.
- **`model_runs_compare.csv`** *(optional)* — copy your Colab / Drive comparison sheet here if you want it versioned next to the path registry.

When you train **`v0.2.0`**, add sibling folders under each `artifacts/<model>/`, update the JSON, and keep old versions until the API no longer needs them.
