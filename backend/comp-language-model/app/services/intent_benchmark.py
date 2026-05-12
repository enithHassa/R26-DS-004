"""Build intent classifier from Phase 2 benchmark JSONL (intent + joint rows)."""

from __future__ import annotations

import json
from pathlib import Path

from app.services.intent_tfidf_centroid import TfidfIntentCentroidClassifier

# Aligned with evaluation/phase2_task_registry.json intent_eval_task_ids
_INTENT_TASK_IDS = frozenset({"intent_classification", "joint_nlu_retrieval"})


def _gold_intent(row: dict[str, object]) -> str | None:
    for key in ("gold_intent", "intent"):
        v = row.get(key)
        if isinstance(v, str) and v.strip():
            return v.strip()
    return None


def load_intent_training_pairs(benchmark_path: Path) -> tuple[list[str], list[str]]:
    utterances: list[str] = []
    labels: list[str] = []
    with benchmark_path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            tid = row.get("task_id")
            if tid is None or (isinstance(tid, str) and not tid.strip()):
                continue
            tid = str(tid).strip()
            if tid not in _INTENT_TASK_IDS:
                continue
            lab = _gold_intent(row)
            if lab is None:
                continue
            utt = str(row.get("utterance") or "")
            if not utt.strip():
                continue
            utterances.append(utt)
            labels.append(lab)
    return utterances, labels


def build_intent_classifier(benchmark_path: Path) -> TfidfIntentCentroidClassifier | None:
    """Return fitted classifier, or ``None`` if benchmark missing / no training rows."""
    if not benchmark_path.is_file():
        return None
    utts, labs = load_intent_training_pairs(benchmark_path)
    if not utts:
        return None
    clf = TfidfIntentCentroidClassifier()
    clf.fit(utts, labs)
    return clf
