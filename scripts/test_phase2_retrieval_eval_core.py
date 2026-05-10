"""Tests for shared Phase 2 retrieval recall@k logic (no embedding deps)."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parent
_REPO = _ROOT.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

_spec = importlib.util.spec_from_file_location(
    "phase2_retrieval_eval_core", _ROOT / "phase2_retrieval_eval_core.py"
)
_core = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
_spec.loader.exec_module(_core)


class _FakeIndex:
    """Returns chunk ids from a fixed map keyed by utterance substring."""

    def __init__(self, utterance_to_ids: dict[str, list[str]]) -> None:
        self._m = utterance_to_ids

    def search(self, query: str, k: int) -> list[tuple[str, float]]:
        for key, ids in self._m.items():
            if key in query:
                out = [(cid, 1.0) for cid in ids[:k]]
                return out
        return []


def test_eval_retrieval_recall_at_k_hit() -> None:
    reg_path = _REPO / "evaluation" / "phase2_task_registry.json"
    examples = [
        {
            "example_id": "r1",
            "task_id": "retrieval_law_grounding",
            "utterance": "personal relief question",
            "gold_chunk_ids": ["t::a"],
        },
    ]
    index = _FakeIndex({"personal": ["t::a", "t::b"]})
    import json

    registry = json.loads(reg_path.read_text(encoding="utf-8"))
    hits, n, _per, mrr_sum = _core.eval_retrieval_recall_at_k(index, examples, registry, k=4)
    assert n == 1
    assert hits == 1
    assert mrr_sum == 1.0


def test_eval_retrieval_mrr_second_rank() -> None:
    reg_path = _REPO / "evaluation" / "phase2_task_registry.json"
    examples = [
        {
            "example_id": "r1",
            "task_id": "retrieval_law_grounding",
            "utterance": "personal relief question",
            "gold_chunk_ids": ["t::b"],
        },
    ]
    index = _FakeIndex({"personal": ["t::a", "t::b", "t::c"]})
    import json

    registry = json.loads(reg_path.read_text(encoding="utf-8"))
    hits, n, _per, mrr_sum = _core.eval_retrieval_recall_at_k(index, examples, registry, k=4)
    assert n == 1
    assert hits == 1
    assert mrr_sum == pytest.approx(0.5)


def test_eval_retrieval_recall_at_k_miss() -> None:
    reg_path = _REPO / "evaluation" / "phase2_task_registry.json"
    examples = [
        {
            "example_id": "r1",
            "task_id": "retrieval_law_grounding",
            "utterance": "personal relief question",
            "gold_chunk_ids": ["t::z"],
        },
    ]
    index = _FakeIndex({"personal": ["t::a", "t::b"]})
    import json

    registry = json.loads(reg_path.read_text(encoding="utf-8"))
    hits, n, _per, mrr_sum = _core.eval_retrieval_recall_at_k(index, examples, registry, k=4)
    assert n == 1
    assert hits == 0
    assert mrr_sum == 0.0


def test_retrieval_eval_json_payload_baseline() -> None:
    p = _core.retrieval_eval_json_payload(
        baseline="tfidf_bow",
        k=8,
        n_benchmark_lines=3,
        hits=2,
        evaluated=4,
        per_task={"retrieval_law_grounding": {"evaluated": 4, "hits": 2}},
        mrr_sum=2.0,
    )
    assert p["baseline"] == "tfidf_bow"
    assert p["value"] == 0.5
    assert p["mrr"] == 0.5
    assert p["n_evaluated"] == 4
