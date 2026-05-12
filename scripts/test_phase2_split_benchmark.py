"""Tests for phase2_split_benchmark (Step 9)."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

_ROOT = Path(__file__).resolve().parent

_spec = importlib.util.spec_from_file_location("phase2_split_benchmark", _ROOT / "phase2_split_benchmark.py")
_sp = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
_spec.loader.exec_module(_sp)


def test_explicit_split(tmp_path: Path) -> None:
    bench = tmp_path / "b.jsonl"
    rows = [
        {"example_id": "a", "split": "train", "utterance": "x", "task_id": "intent_classification", "gold_intent": "i"},
        {"example_id": "b", "split": "dev", "utterance": "y", "task_id": "intent_classification", "gold_intent": "j"},
        {"example_id": "c", "split": "test", "utterance": "z", "task_id": "intent_classification", "gold_intent": "k"},
    ]
    bench.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")
    loaded = _sp._load_rows(bench)
    buckets = _sp.assign_explicit(loaded)
    assert len(buckets["train"]) == 1 and buckets["train"][0]["example_id"] == "a"
    assert len(buckets["dev"]) == 1
    assert len(buckets["test"]) == 1


def test_explicit_rejects_bad_split(tmp_path: Path) -> None:
    bench = tmp_path / "b.jsonl"
    bench.write_text(
        json.dumps({"example_id": "a", "split": "oops", "utterance": "x"}) + "\n", encoding="utf-8"
    )
    try:
        _sp.assign_explicit(_sp._load_rows(bench))
        raise AssertionError("expected ValueError")
    except ValueError:
        pass


def test_hash_split_partitions_all_rows(tmp_path: Path) -> None:
    bench = tmp_path / "b.jsonl"
    lines = []
    for i in range(30):
        lines.append(json.dumps({"example_id": f"id_{i}", "utterance": f"u{i}"}))
    bench.write_text("\n".join(lines) + "\n", encoding="utf-8")
    buckets = _sp.assign_hash(
        _sp._load_rows(bench),
        train_frac=0.7,
        dev_frac=0.15,
        seed="t",
    )
    total = sum(len(v) for v in buckets.values())
    assert total == 30
    assert all("split" in r for bucket in buckets.values() for r in bucket)
