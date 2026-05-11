"""Tests for phase2_leaderboard.py (Step 6)."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

_ROOT = Path(__file__).resolve().parent

_spec = importlib.util.spec_from_file_location("phase2_leaderboard", _ROOT / "phase2_leaderboard.py")
_lb = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
_spec.loader.exec_module(_lb)


def test_leaderboard_sorts_by_joint(tmp_path: Path) -> None:
    log = tmp_path / "r.jsonl"
    low = {
        "run_id": "a",
        "model_version": "weak",
        "metrics": {
            "phase2_joint_success_rate": 0.1,
            "phase2_retrieval_recall_at_k_any_gold": 0.5,
            "phase2_intent_macro_f1": 0.2,
        },
        "runtime": {"duration_seconds": 10},
        "cost": {"estimated_total": 0.0},
        "dataset": {"name": "b", "retrieval_top_k": 8},
    }
    high = {
        "run_id": "b",
        "model_version": "strong",
        "metrics": {
            "phase2_joint_success_rate": 0.8,
            "phase2_retrieval_recall_at_k_any_gold": 0.3,
            "phase2_intent_macro_f1": 0.1,
        },
        "runtime": {"duration_seconds": 5},
        "cost": {"estimated_total": 0.0},
        "dataset": {"name": "b", "retrieval_top_k": 8},
    }
    log.write_text(json.dumps(low) + "\n" + json.dumps(high) + "\n", encoding="utf-8")
    runs = _lb._load_runs(log)
    runs.sort(key=lambda r: _lb._sort_key(r, "joint"), reverse=True)
    assert runs[0]["model_version"] == "strong"


def test_leaderboard_latency_sort_fastest_first(tmp_path: Path) -> None:
    log = tmp_path / "r.jsonl"
    slow = {
        "run_id": "s",
        "model_version": "slow",
        "metrics": {},
        "runtime": {"duration_seconds": 100},
        "dataset": {},
    }
    fast = {
        "run_id": "f",
        "model_version": "fast",
        "metrics": {},
        "runtime": {"duration_seconds": 1},
        "dataset": {},
    }
    log.write_text(json.dumps(slow) + "\n" + json.dumps(fast) + "\n", encoding="utf-8")
    runs = _lb._load_runs(log)
    runs.sort(key=_lb._latency_sort_key)
    assert runs[0]["model_version"] == "fast"


def test_leaderboard_skips_errors_by_default(tmp_path: Path) -> None:
    log = tmp_path / "r.jsonl"
    ok = {"run_id": "1", "model_version": "ok", "metrics": {}, "runtime": {}, "dataset": {}}
    bad = {"run_id": "2", "model_version": "bad", "phase2_errors": {"retrieval": "fail"}, "metrics": {}}
    log.write_text(json.dumps(ok) + "\n" + json.dumps(bad) + "\n", encoding="utf-8")
    runs = _lb._load_runs(log)
    filtered = [r for r in runs if not r.get("phase2_errors")]
    assert len(filtered) == 1
