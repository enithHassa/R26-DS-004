"""Tests for Phase 2 Step 3 joint eval (intent + retrieval)."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent
_REPO = _ROOT.parent

_spec = importlib.util.spec_from_file_location(
    "phase2_eval_joint_tfidf", _ROOT / "phase2_eval_joint_tfidf.py"
)
_ev = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
_spec.loader.exec_module(_ev)

_spec_r = importlib.util.spec_from_file_location("phase2_task_registry", _ROOT / "phase2_task_registry.py")
_reg = importlib.util.module_from_spec(_spec_r)
assert _spec_r.loader is not None
_spec_r.loader.exec_module(_reg)


def test_joint_loocv_runs(tmp_path: Path) -> None:
    reg_path = _REPO / "evaluation" / "phase2_task_registry.json"
    registry = _reg.load_registry(reg_path)

    corpus = tmp_path / "c.jsonl"
    corpus.write_text(
        "\n".join(
            [
                json.dumps({"chunk_id": "x::res", "text": "tax resident residence sri lanka 183 days"}),
                json.dumps({"chunk_id": "x::don", "text": "approved charity donation relief deduction"}),
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    bench = tmp_path / "b.jsonl"
    rows = [
        {
            "example_id": "i1",
            "task_id": "intent_classification",
            "utterance": "unrelated filler intent training",
            "gold_intent": "filler",
        },
        {
            "example_id": "j1",
            "task_id": "joint_nlu_retrieval",
            "utterance": "Am I tax resident in Sri Lanka with 200 days?",
            "intent": "residence_scope",
            "gold_chunk_ids": ["x::res"],
        },
        {
            "example_id": "j2",
            "task_id": "joint_nlu_retrieval",
            "utterance": "Can I claim relief for donations to an approved charity?",
            "intent": "donation_relief",
            "gold_chunk_ids": ["x::don"],
        },
    ]
    with bench.open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")

    sys.path.insert(0, str(_REPO / "backend" / "comp-language-model"))
    from app.services.tfidf_chunk_index import TfidfChunkIndex  # noqa: E402, PLC0415

    all_rows = _ev._load_benchmark_rows(bench)
    pool = _ev._intent_training_pool(all_rows, registry)
    joint_rows = _ev._joint_rows(all_rows, registry)
    assert len(joint_rows) == 2
    assert len(pool) == 3

    index = TfidfChunkIndex.from_jsonl(corpus)
    details, joint_hits, n, intent_hits, retrieval_hits = _ev._eval_joint_loocv(
        pool, joint_rows, registry, index, k=4
    )
    assert n == 2
    assert len(details) == 2
    assert 0 <= joint_hits <= n
    assert 0 <= intent_hits <= n
    assert 0 <= retrieval_hits <= n


def test_joint_fixed_train_held_out(tmp_path: Path) -> None:
    """Step 10: intent fit on train file only; score joint rows from eval file."""
    reg_path = _REPO / "evaluation" / "phase2_task_registry.json"
    registry = _reg.load_registry(reg_path)

    corpus = tmp_path / "c.jsonl"
    corpus.write_text(
        "\n".join(
            [
                json.dumps({"chunk_id": "x::res", "text": "tax resident residence sri lanka 183 days"}),
                json.dumps({"chunk_id": "x::don", "text": "approved charity donation relief deduction"}),
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    train_bench = tmp_path / "train.jsonl"
    train_bench.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "example_id": "i_train",
                        "task_id": "intent_classification",
                        "utterance": "tax resident status rules sri lanka 183 days statute",
                        "gold_intent": "residence_scope",
                    }
                ),
                json.dumps(
                    {
                        "example_id": "j_train",
                        "task_id": "joint_nlu_retrieval",
                        "utterance": "how many days to be resident in country for tax",
                        "intent": "residence_scope",
                        "gold_chunk_ids": ["x::res"],
                    }
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    eval_bench = tmp_path / "eval.jsonl"
    eval_bench.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "example_id": "j_eval",
                        "task_id": "joint_nlu_retrieval",
                        "utterance": "Am I tax resident in Sri Lanka with 200 days?",
                        "intent": "residence_scope",
                        "gold_chunk_ids": ["x::res"],
                    }
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    sys.path.insert(0, str(_REPO / "backend" / "comp-language-model"))
    from app.services.tfidf_chunk_index import TfidfChunkIndex  # noqa: E402, PLC0415

    train_rows = _ev._load_benchmark_rows(train_bench)
    eval_rows = _ev._load_benchmark_rows(eval_bench)
    pool = _ev._intent_training_pool(train_rows, registry)
    joint_rows = _ev._joint_rows(eval_rows, registry)
    assert len(pool) == 2
    assert len(joint_rows) == 1

    index = TfidfChunkIndex.from_jsonl(corpus)
    details, joint_hits, n, intent_hits, retrieval_hits = _ev._eval_joint_fixed_train(
        pool, joint_rows, registry, index, k=4
    )
    assert n == 1
    assert len(details) == 1
    assert details[0]["intent_match"] is True
    assert details[0]["retrieval_match"] is True
    assert details[0]["joint_match"] is True
    assert joint_hits == intent_hits == retrieval_hits == 1
