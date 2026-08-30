"""Resolve Component 1 taxonomy, rulebook, and model artifact paths."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any


def repo_root() -> Path:
    return Path(__file__).resolve().parents[4]


def taxonomy_yaml_path() -> Path:
    return repo_root() / "models" / "transaction-semantic" / "taxonomy.yaml"


def rulebook_yaml_path() -> Path:
    return repo_root() / "models" / "transaction-semantic" / "rules" / "sl_tax_rules_ira_2017_v1.yaml"


def artifact_paths_json_path() -> Path:
    return (
        repo_root()
        / "models"
        / "transaction-semantic"
        / "evaluation"
        / "artifact_paths.json"
    )


@lru_cache(maxsize=1)
def load_artifact_paths() -> dict[str, Any]:
    path = artifact_paths_json_path()
    return json.loads(path.read_text(encoding="utf-8"))


def resolve_repo_relative(path_str: str) -> Path:
    return repo_root() / path_str


def chosen_classifier_artifact_paths() -> dict[str, str]:
    data = load_artifact_paths()
    chosen = data.get("chosen_classifier", {})
    model_key = str(chosen.get("model_key", "tfidf_logreg"))
    version = str(chosen.get("version", data.get("bundle_version", "v0.1.0")))
    artifacts = data.get("artifacts", {})
    bundle = artifacts.get(model_key, {})
    bundle_version = str(bundle.get("version", version))
    prefix = f"models/transaction-semantic/artifacts/{model_key}/{bundle_version}"
    if model_key == "tfidf_logreg":
        return {
            "model_key": model_key,
            "version": bundle_version,
            "pipeline": bundle.get(
                "pipeline",
                f"{prefix}/tfidf_logreg_pipeline.joblib",
            ),
        }
    return {
        "model_key": model_key,
        "version": bundle_version,
        "hf_model": bundle.get("hf_model", f"{prefix}/hf_model"),
        "label_map": bundle.get("export", f"{prefix}/export") + "/label2id.json",
    }
