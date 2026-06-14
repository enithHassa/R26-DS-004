"""Tests for TF-IDF intent centroid baseline and eval helpers."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

_ROOT = Path(__file__).resolve().parent
_REPO = _ROOT.parent

_spec = importlib.util.spec_from_file_location("phase2_intent_tfidf", _ROOT / "phase2_intent_tfidf.py")
_intent_mod = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
_spec.loader.exec_module(_intent_mod)

_spec2 = importlib.util.spec_from_file_location("phase2_task_registry", _ROOT / "phase2_task_registry.py")
_reg_mod = importlib.util.module_from_spec(_spec2)
assert _spec2.loader is not None
_spec2.loader.exec_module(_reg_mod)


def test_centroid_classifier_single_class() -> None:
    clf = _intent_mod.TfidfIntentCentroidClassifier()
    clf.fit(
        ["personal relief amount", "how much relief"],
        ["personal_relief", "personal_relief"],
    )
    assert clf.predict(["what is personal relief"]) == ["personal_relief"]


def test_centroid_classifier_two_classes() -> None:
    clf = _intent_mod.TfidfIntentCentroidClassifier()
    clf.fit(
        ["relief for individuals", "tax resident 183 days", "resident status sri lanka"],
        ["personal_relief", "residence_scope", "residence_scope"],
    )
    p = clf.predict(["days in country for resident"])[0]
    assert p == "residence_scope"


def test_loocv_runs_on_synthetic_benchmark(tmp_path: Path) -> None:
    reg_path = _REPO / "evaluation" / "phase2_task_registry.json"
    registry = _reg_mod.load_registry(reg_path)
    bench = tmp_path / "b.jsonl"
    rows = [
        {
            "example_id": "a1",
            "task_id": "intent_classification",
            "utterance": "question about relief",
            "gold_intent": "a",
        },
        {
            "example_id": "a2",
            "task_id": "intent_classification",
            "utterance": "another relief question",
            "gold_intent": "a",
        },
        {
            "example_id": "b1",
            "task_id": "joint_nlu_retrieval",
            "utterance": "tax resident days",
            "intent": "b",
            "gold_chunk_ids": ["x"],
        },
    ]
    with bench.open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")

    _spec_ev = importlib.util.spec_from_file_location(
        "phase2_eval_intent_tfidf", _ROOT / "phase2_eval_intent_tfidf.py"
    )
    ev = importlib.util.module_from_spec(_spec_ev)
    assert _spec_ev.loader is not None
    _spec_ev.loader.exec_module(ev)

    loaded = ev._load_benchmark_rows(bench)
    intent_rows = ev._intent_rows(loaded, registry)
    assert len(intent_rows) == 3
    hits, n, _ = ev._loocv(intent_rows, registry)
    assert n == 3
    assert 0 <= hits <= n


def test_holdout_deterministic_seed(tmp_path: Path) -> None:
    reg_path = _REPO / "evaluation" / "phase2_task_registry.json"
    registry = _reg_mod.load_registry(reg_path)
    bench = tmp_path / "b.jsonl"
    rows = [
        {"example_id": str(i), "task_id": "intent_classification", "utterance": f"u{i}", "gold_intent": "c"}
        for i in range(5)
    ]
    with bench.open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")

    _spec_ev = importlib.util.spec_from_file_location(
        "phase2_eval_intent_tfidf", _ROOT / "phase2_eval_intent_tfidf.py"
    )
    ev = importlib.util.module_from_spec(_spec_ev)
    assert _spec_ev.loader is not None
    _spec_ev.loader.exec_module(ev)

    loaded = ev._load_benchmark_rows(bench)
    intent_rows = ev._intent_rows(loaded, registry)
    h1, n1, _ = ev._holdout(intent_rows, registry, test_fraction=0.4, seed=7)
    h2, n2, _ = ev._holdout(intent_rows, registry, test_fraction=0.4, seed=7)
    assert n1 == n2 and h1 == h2
