"""Smoke test for Phase 2 experiment bundle (Step 5)."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent
_REPO = _ROOT.parent


def test_phase2_experiment_run_dry_run(tmp_path: Path) -> None:
    corpus = tmp_path / "c.jsonl"
    corpus.write_text(
        "\n".join(
            [
                json.dumps({"chunk_id": "t::a", "text": "personal relief assessment year"}),
                json.dumps({"chunk_id": "t::b", "text": "tax resident sri lanka days"}),
                json.dumps({"chunk_id": "ird-ira-2017::p0001::c0000", "text": "placeholder statute"}),
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    bench = tmp_path / "b.jsonl"
    rows = [
        {
            "example_id": "r1",
            "task_id": "retrieval_law_grounding",
            "utterance": "personal relief?",
            "gold_chunk_ids": ["t::a"],
        },
        {
            "example_id": "j1",
            "task_id": "joint_nlu_retrieval",
            "utterance": "residence 200 days?",
            "intent": "residence_scope",
            "gold_chunk_ids": ["t::b"],
        },
        {
            "example_id": "i1",
            "task_id": "intent_classification",
            "utterance": "charity donation tax",
            "gold_intent": "donation_relief",
        },
    ]
    with bench.open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")

    cmd = [
        sys.executable,
        str(_ROOT / "phase2_experiment_run.py"),
        "--corpus-jsonl",
        str(corpus),
        "--benchmark",
        str(bench),
        "--k",
        "4",
        "--model-version",
        "test_tf_idf",
        "--dry-run",
        "--notes",
        "pytest",
    ]
    proc = subprocess.run(cmd, cwd=str(_REPO), capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr
    record = json.loads(proc.stdout.strip())
    assert record["component"] == "language-model"
    assert record["model_version"] == "test_tf_idf"
    assert "phase2_eval_outputs" in record
    assert "retrieval" in record["phase2_eval_outputs"]


def test_phase2_experiment_run_dry_run_train_benchmark(tmp_path: Path) -> None:
    corpus = tmp_path / "c.jsonl"
    corpus.write_text(
        "\n".join(
            [
                json.dumps({"chunk_id": "t::a", "text": "personal relief assessment year"}),
                json.dumps({"chunk_id": "t::b", "text": "tax resident sri lanka days"}),
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    train = tmp_path / "train.jsonl"
    train.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "example_id": "i_train",
                        "task_id": "intent_classification",
                        "utterance": "charity donation tax relief",
                        "gold_intent": "donation_relief",
                    }
                ),
                json.dumps(
                    {
                        "example_id": "j_train",
                        "task_id": "joint_nlu_retrieval",
                        "utterance": "extra joint for pool",
                        "intent": "residence_scope",
                        "gold_chunk_ids": ["t::b"],
                    }
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    eval_bench = tmp_path / "eval.jsonl"
    rows = [
        {
            "example_id": "r1",
            "task_id": "retrieval_law_grounding",
            "utterance": "personal relief?",
            "gold_chunk_ids": ["t::a"],
        },
        {
            "example_id": "j1",
            "task_id": "joint_nlu_retrieval",
            "utterance": "residence 200 days?",
            "intent": "residence_scope",
            "gold_chunk_ids": ["t::b"],
        },
    ]
    with eval_bench.open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")

    cmd = [
        sys.executable,
        str(_ROOT / "phase2_experiment_run.py"),
        "--corpus-jsonl",
        str(corpus),
        "--benchmark",
        str(eval_bench),
        "--train-benchmark",
        str(train),
        "--k",
        "4",
        "--model-version",
        "test_held_out",
        "--dry-run",
    ]
    proc = subprocess.run(cmd, cwd=str(_REPO), capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr
    record = json.loads(proc.stdout.strip())
    ds = record["dataset"]
    assert ds["split"] == "held_out_train_eval"
    assert ds["train_benchmark_path"] is not None
    assert ds["train_sample_count"] == 2
    assert ds["sample_count"] == 2
    intent_out = record["phase2_eval_outputs"]["intent"]
    assert intent_out["mode"] == "held_out_train_split"
    joint_out = record["phase2_eval_outputs"]["joint"]
    assert joint_out["mode"] == "held_out_train_split"
