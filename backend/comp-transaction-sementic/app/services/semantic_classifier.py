"""Load bundled classifier artifacts and predict semantic labels."""

from __future__ import annotations

import json
import logging
import threading
from dataclasses import dataclass
from pathlib import Path

import joblib
import numpy as np

from .tax_semantic_paths import chosen_classifier_artifact_paths, resolve_repo_relative

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SemanticPrediction:
    label: str
    confidence: float
    model_key: str
    model_version: str
    probabilities: dict[str, float]


class SemanticClassifier:
    def __init__(self, *, pipeline_path: Path, model_key: str, version: str) -> None:
        self.pipeline_path = pipeline_path
        self.model_key = model_key
        self.model_version = f"{model_key}/{version}"
        self._pipeline = joblib.load(pipeline_path)

    def predict(self, text_primary: str) -> SemanticPrediction:
        return self.predict_many([text_primary])[0]

    def predict_many(self, texts: list[str]) -> list[SemanticPrediction]:
        if not texts:
            return []
        pipeline = self._pipeline
        labels = [str(label) for label in pipeline.predict(texts)]
        prob_rows = pipeline.predict_proba(texts) if hasattr(pipeline, "predict_proba") else None
        classes = [str(c) for c in pipeline.classes_] if prob_rows is not None else []
        out: list[SemanticPrediction] = []
        for idx, label in enumerate(labels):
            confidence = 0.0
            probabilities: dict[str, float] = {}
            if prob_rows is not None:
                row = prob_rows[idx]
                probabilities = {cls: float(score) for cls, score in zip(classes, row, strict=True)}
                confidence = float(max(row))
            out.append(
                SemanticPrediction(
                    label=label,
                    confidence=confidence,
                    model_key=self.model_key,
                    model_version=self.model_version,
                    probabilities=probabilities,
                ),
            )
        return out


class HfSemanticClassifier:
    def __init__(self, *, model_dir: Path, label_map_path: Path, model_key: str, version: str) -> None:
        from transformers import AutoModelForSequenceClassification, AutoTokenizer
        import torch

        payload = json.loads(label_map_path.read_text(encoding="utf-8"))
        self._id2label = {int(k): v for k, v in payload["id2label"].items()}
        self.model_key = model_key
        self.model_version = f"{model_key}/{version}"
        self._tokenizer = AutoTokenizer.from_pretrained(model_dir)
        self._model = AutoModelForSequenceClassification.from_pretrained(model_dir)
        self._model.eval()
        self._torch = torch

    def predict(self, text_primary: str, *, max_length: int = 256) -> SemanticPrediction:
        return self.predict_many([text_primary], max_length=max_length)[0]

    def predict_many(
        self,
        texts: list[str],
        *,
        max_length: int = 256,
        batch_size: int = 16,
    ) -> list[SemanticPrediction]:
        if not texts:
            return []
        out: list[SemanticPrediction] = []
        for start in range(0, len(texts), batch_size):
            chunk = texts[start : start + batch_size]
            encoded = self._tokenizer(
                chunk,
                truncation=True,
                max_length=max_length,
                padding=True,
                return_tensors="pt",
            )
            with self._torch.no_grad():
                logits = self._model(**encoded).logits.numpy()
            for row in logits:
                probs = _softmax(row)
                idx = int(np.argmax(probs))
                label = str(self._id2label[idx])
                probabilities = {str(self._id2label[i]): float(probs[i]) for i in range(len(probs))}
                out.append(
                    SemanticPrediction(
                        label=label,
                        confidence=float(probs[idx]),
                        model_key=self.model_key,
                        model_version=self.model_version,
                        probabilities=probabilities,
                    ),
                )
        return out


def _softmax(logits: np.ndarray) -> np.ndarray:
    shifted = logits - np.max(logits)
    exp = np.exp(shifted)
    return exp / np.sum(exp)


class UnavailableSemanticClassifier:
    """No local ML artifacts — Layer-1 deterministic rules still classify known bank codes.

    Remaining rows are labelled ``unknown`` so classify-batch does not 500.
    """

    def __init__(self, *, reason: str) -> None:
        self.model_key = "unavailable"
        self.model_version = "unavailable/none"
        self.reason = reason

    def predict(self, text_primary: str) -> SemanticPrediction:
        return self.predict_many([text_primary])[0]

    def predict_many(self, texts: list[str]) -> list[SemanticPrediction]:
        return [
            SemanticPrediction(
                label="unknown",
                confidence=0.0,
                model_key=self.model_key,
                model_version=self.model_version,
                probabilities={"unknown": 1.0},
            )
            for _ in texts
        ]


ClassifierType = SemanticClassifier | HfSemanticClassifier | UnavailableSemanticClassifier

_classifier_lock = threading.Lock()
_classifier_instance: ClassifierType | None = None

_TFIDF_FALLBACK = (
    "models/transaction-semantic/artifacts/tfidf_logreg/v0.1.0/tfidf_logreg_pipeline.joblib"
)


def _tfidf_fallback_classifier() -> SemanticClassifier | None:
    fallback = resolve_repo_relative(_TFIDF_FALLBACK)
    if not fallback.is_file():
        return None
    return SemanticClassifier(
        pipeline_path=fallback,
        model_key="tfidf_logreg",
        version="v0.1.0",
    )


def _build_semantic_classifier() -> ClassifierType:
    meta = chosen_classifier_artifact_paths()
    model_key = meta["model_key"]
    version = meta["version"]
    if model_key == "tfidf_logreg":
        pipeline_path = resolve_repo_relative(meta["pipeline"])
        if pipeline_path.is_file():
            return SemanticClassifier(
                pipeline_path=pipeline_path,
                model_key=model_key,
                version=version,
            )
        reason = f"Classifier pipeline not found: {pipeline_path}"
        logger.warning("semantic_classifier_unavailable: %s", reason)
        return UnavailableSemanticClassifier(reason=reason)

    hf_dir = resolve_repo_relative(meta["hf_model"])
    label_map = resolve_repo_relative(meta["label_map"])
    if not hf_dir.is_dir() or not label_map.is_file():
        fallback = _tfidf_fallback_classifier()
        if fallback is not None:
            return fallback
        reason = f"HF classifier artifacts missing: {hf_dir}"
        logger.warning("semantic_classifier_unavailable: %s", reason)
        return UnavailableSemanticClassifier(reason=reason)

    try:
        return HfSemanticClassifier(
            model_dir=hf_dir,
            label_map_path=label_map,
            model_key=model_key,
            version=version,
        )
    except ImportError as exc:
        fallback = _tfidf_fallback_classifier()
        if fallback is not None:
            return fallback
        reason = f"HF classifier unavailable (transformers/torch missing): {exc}"
        logger.warning("semantic_classifier_unavailable: %s", reason)
        return UnavailableSemanticClassifier(reason=reason)


def get_semantic_classifier() -> ClassifierType:
    global _classifier_instance
    if _classifier_instance is not None:
        return _classifier_instance
    with _classifier_lock:
        if _classifier_instance is None:
            _classifier_instance = _build_semantic_classifier()
    return _classifier_instance


def preload_semantic_classifier() -> None:
    get_semantic_classifier()


def reset_semantic_classifier_for_tests() -> None:
    """Clear the process-wide singleton (tests only)."""
    global _classifier_instance
    with _classifier_lock:
        _classifier_instance = None
