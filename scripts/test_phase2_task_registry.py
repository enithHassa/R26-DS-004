"""Tests for Phase 2 task registry loading and row validation."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

_ROOT = Path(__file__).resolve().parent
_REPO = _ROOT.parent
_REG = _REPO / "evaluation" / "phase2_task_registry.json"

_spec = importlib.util.spec_from_file_location("phase2_task_registry", _ROOT / "phase2_task_registry.py")
_mod = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
_spec.loader.exec_module(_mod)


def test_default_registry_loads() -> None:
    reg = _mod.load_registry(_REG)
    assert reg.get("registry_version")
    assert _mod.default_task_id(reg) == "retrieval_law_grounding"
    assert "retrieval_law_grounding" in _mod.task_map(reg)


def test_validate_row_retrieval_requires_chunks() -> None:
    reg = _mod.load_registry(_REG)
    err = _mod.validate_example_row(
        {"example_id": "x", "utterance": "q", "task_id": "retrieval_law_grounding", "gold_chunk_ids": []},
        registry=reg,
        line_no=1,
    )
    assert err


def test_validate_row_intent_only_ok() -> None:
    reg = _mod.load_registry(_REG)
    err = _mod.validate_example_row(
        {
            "example_id": "x",
            "utterance": "q?",
            "task_id": "intent_classification",
            "gold_intent": "foo",
            "gold_chunk_ids": [],
        },
        registry=reg,
        line_no=1,
    )
    assert not err


def test_validate_row_joint_requires_intent_and_chunks() -> None:
    reg = _mod.load_registry(_REG)
    err = _mod.validate_example_row(
        {
            "example_id": "x",
            "utterance": "q?",
            "task_id": "joint_nlu_retrieval",
            "gold_chunk_ids": ["a"],
        },
        registry=reg,
        line_no=1,
    )
    assert any("intent" in e.lower() for e in err)


def test_benchmark_template_jsonl_matches_registry() -> None:
    reg = _mod.load_registry(_REG)
    bench = _REPO / "evaluation" / "benchmark_seed_template.jsonl"
    lines = [ln for ln in bench.read_text(encoding="utf-8").splitlines() if ln.strip()]
    errors: list[str] = []
    for i, line in enumerate(lines, start=1):
        errors.extend(_mod.validate_example_row(json.loads(line), registry=reg, line_no=i))
    assert not errors, errors
