"""Load and validate Phase 2 benchmark rows against evaluation/phase2_task_registry.json."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parent
_REPO_ROOT = _ROOT.parent
_DEFAULT_REGISTRY = _REPO_ROOT / "evaluation" / "phase2_task_registry.json"


def load_registry(path: Path | None = None) -> dict[str, Any]:
    p = path or _DEFAULT_REGISTRY
    if not p.is_file():
        raise FileNotFoundError(f"task registry not found: {p}")
    return json.loads(p.read_text(encoding="utf-8"))


def task_map(registry: dict[str, Any]) -> dict[str, dict[str, Any]]:
    tasks = registry.get("tasks") or []
    return {str(t["task_id"]): t for t in tasks if t.get("task_id")}


def default_task_id(registry: dict[str, Any]) -> str:
    return str(registry.get("default_task_id") or "retrieval_law_grounding")


def _non_empty_str(row: dict[str, Any], key: str) -> bool:
    v = row.get(key)
    return isinstance(v, str) and bool(v.strip())


def _intent_value(row: dict[str, Any], task: dict[str, Any]) -> str | None:
    aliases = (task.get("gold_field_aliases") or {}).get("gold_intent") or ["gold_intent", "intent"]
    for key in aliases:
        v = row.get(key)
        if isinstance(v, str) and v.strip():
            return v.strip()
    return None


def _gold_chunks(row: dict[str, Any]) -> list[Any]:
    g = row.get("gold_chunk_ids")
    if g is None:
        return []
    if not isinstance(g, list):
        return []
    return g


def validate_example_row(
    row: dict[str, Any],
    *,
    registry: dict[str, Any],
    line_no: int | None = None,
) -> list[str]:
    """Return human-readable errors; empty list means OK for task shape."""
    tmap = task_map(registry)
    tid = row.get("task_id")
    if tid is None or (isinstance(tid, str) and not tid.strip()):
        tid = default_task_id(registry)
    else:
        tid = str(tid).strip()

    if tid not in tmap:
        loc = f"line {line_no}" if line_no is not None else f"example_id={row.get('example_id')!r}"
        return [f"{loc}: unknown task_id {tid!r}"]

    task = tmap[tid]
    if task.get("status") == "planned":
        loc = f"line {line_no}" if line_no is not None else f"example_id={row.get('example_id')!r}"
        return [f"{loc}: task {tid!r} is marked planned — use active tasks for benchmark gold data"]

    val = task.get("validation") or {}
    errs: list[str] = []
    loc = f"line {line_no}" if line_no is not None else f"example_id={row.get('example_id', '?')!r}"

    for key in val.get("required_fields") or []:
        if not _non_empty_str(row, key):
            errs.append(f"{loc}: missing or empty required field {key!r} for task {tid!r}")

    min_chunks = int(val.get("gold_chunk_ids_min_count", 0))
    chunks = _gold_chunks(row)
    if min_chunks > 0 and len(chunks) < min_chunks:
        errs.append(
            f"{loc}: task {tid!r} requires at least {min_chunks} gold_chunk_ids (got {len(chunks)})"
        )

    if val.get("require_intent_label"):
        if _intent_value(row, task) is None:
            errs.append(
                f"{loc}: task {tid!r} requires an intent label (gold_intent or intent)"
            )

    return errs


def retrieval_eval_task_ids(registry: dict[str, Any]) -> set[str]:
    """Tasks for which TF-IDF / dense recall@k against gold_chunk_ids is defined."""
    _ = registry  # reserved for future: drive from JSON ``eval_harness`` flags
    return {
        "retrieval_law_grounding",
        "joint_nlu_retrieval",
    }


def intent_eval_task_ids(registry: dict[str, Any]) -> set[str]:
    """Tasks that carry a gold intent label (Phase 2 Step 2 NLU baselines)."""
    _ = registry
    return {
        "intent_classification",
        "joint_nlu_retrieval",
    }


def joint_eval_task_ids(registry: dict[str, Any]) -> set[str]:
    """Tasks scored by Phase 2 Step 3 (intent ∧ retrieval@k)."""
    _ = registry
    return {"joint_nlu_retrieval"}


def gold_intent_for_row(row: dict[str, Any], registry: dict[str, Any]) -> str | None:
    """Resolve intent label using task-specific aliases; None if missing."""
    tmap = task_map(registry)
    tid = row.get("task_id")
    if tid is None or (isinstance(tid, str) and not str(tid).strip()):
        tid = default_task_id(registry)
    else:
        tid = str(tid).strip()
    task = tmap.get(tid) or {}
    return _intent_value(row, task)
