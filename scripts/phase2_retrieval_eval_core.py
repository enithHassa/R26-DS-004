"""Shared recall@k and MRR@k eval loop for Phase 2 retrieval baselines (TF-IDF and dense).

``value`` / recall: fraction of examples with ≥1 gold chunk in top-k.
``mrr``: mean reciprocal rank of the first gold chunk in the ranked top-k list (0 if none).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Protocol

from phase2_task_registry import (
    default_task_id,
    load_registry,
    retrieval_eval_task_ids,
    task_map,
)


class ChunkSearchIndex(Protocol):
    def search(self, query: str, k: int) -> list[tuple[str, float]]: ...


def load_benchmark_examples(path: Path) -> list[dict[str, object]]:
    examples: list[dict[str, object]] = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            examples.append(json.loads(line))
    return examples


def _first_gold_rank(top_chunk_ids: list[str], gold: set[str]) -> int | None:
    for i, cid in enumerate(top_chunk_ids, start=1):
        if cid in gold:
            return i
    return None


def eval_retrieval_recall_at_k(
    index: ChunkSearchIndex,
    examples: list[dict[str, object]],
    registry: dict[str, object],
    k: int,
) -> tuple[int, int, dict[str, dict[str, int]], float]:
    """Returns hits, evaluated count, per_task {tid: {evaluated, hits}}, sum of reciprocal ranks.

    MRR contribution per row: 1/rank of the first gold chunk in the top-k list (0 if none).
    Mean reciprocal rank is ``mrr_sum / evaluated`` when evaluated > 0.
    """
    r_tasks = retrieval_eval_task_ids(registry)
    tmap = task_map(registry)
    default_tid = default_task_id(registry)

    hits = 0
    evaluated = 0
    mrr_sum = 0.0
    per_task: dict[str, dict[str, int]] = {}

    for row in examples:
        tid = row.get("task_id")
        if not tid or (isinstance(tid, str) and not str(tid).strip()):
            tid = default_tid
        else:
            tid = str(tid).strip()
        if tid not in r_tasks:
            continue
        if tmap.get(tid, {}).get("status") == "planned":
            continue

        utterance = str(row.get("utterance") or "")
        gold = {str(x) for x in (row.get("gold_chunk_ids") or [])}
        if not gold:
            continue

        evaluated += 1
        top = [cid for cid, _ in index.search(utterance, k)]
        top_set = set(top)
        hit = bool(gold & top_set)
        if hit:
            hits += 1
        rank = _first_gold_rank(top, gold)
        if rank is not None:
            mrr_sum += 1.0 / rank
        bucket = per_task.setdefault(tid, {"evaluated": 0, "hits": 0})
        bucket["evaluated"] += 1
        if hit:
            bucket["hits"] += 1

    return hits, evaluated, per_task, mrr_sum


def retrieval_eval_json_payload(
    *,
    baseline: str,
    k: int,
    n_benchmark_lines: int,
    hits: int,
    evaluated: int,
    per_task: dict[str, dict[str, int]],
    mrr_sum: float = 0.0,
    extra: dict[str, Any] | None = None,
) -> dict[str, object]:
    recall = hits / evaluated if evaluated else 0.0
    mrr = mrr_sum / evaluated if evaluated else 0.0
    out: dict[str, object] = {
        "metric": "recall_at_k_any_gold",
        "baseline": baseline,
        "k": k,
        "n_benchmark_lines": n_benchmark_lines,
        "n_evaluated": evaluated,
        "hits": hits,
        "value": recall,
        "mrr": mrr,
        "by_task": {t: {"n": v["evaluated"], "hits": v["hits"]} for t, v in sorted(per_task.items())},
    }
    if extra:
        out.update(extra)
    return out


def run_retrieval_eval_from_paths(
    index: ChunkSearchIndex,
    *,
    benchmark_path: Path,
    registry_path: Path,
    k: int,
    baseline: str,
    extra: dict[str, Any] | None = None,
) -> dict[str, object]:
    registry = load_registry(registry_path)
    examples = load_benchmark_examples(benchmark_path)
    hits, evaluated, per_task, mrr_sum = eval_retrieval_recall_at_k(index, examples, registry, k)
    return retrieval_eval_json_payload(
        baseline=baseline,
        k=k,
        n_benchmark_lines=len(examples),
        hits=hits,
        evaluated=evaluated,
        per_task=per_task,
        mrr_sum=mrr_sum,
        extra=extra,
    )
