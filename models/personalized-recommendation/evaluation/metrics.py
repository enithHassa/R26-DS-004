"""Ranking and adoption metrics for offline evaluation (Phase 6)."""

from __future__ import annotations

import numpy as np
from sklearn.metrics import average_precision_score, f1_score, ndcg_score, roc_auc_score


def group_by_query(flat: np.ndarray, group_sizes: np.ndarray) -> list[np.ndarray]:
    """Split a flat array into per-query groups."""
    out: list[np.ndarray] = []
    i = 0
    for g in group_sizes:
        out.append(np.asarray(flat[i : i + g], dtype=float))
        i += int(g)
    return out


def ranking_metrics(
    y_true_groups: list[np.ndarray],
    y_score_groups: list[np.ndarray],
    *,
    ks: tuple[int, ...] = (5, 10),
) -> dict[str, float]:
    """Compute NDCG@k, MAP@5, MRR, hit@1, precision@5 across query groups."""
    ndcg: dict[int, list[float]] = {k: [] for k in ks}
    map5: list[float] = []
    mrr: list[float] = []
    hit1: list[float] = []
    p5: list[float] = []

    for y_true, y_score in zip(y_true_groups, y_score_groups):
        y_true = np.asarray(y_true, dtype=float)
        y_score = np.asarray(y_score, dtype=float)
        if y_true.sum() <= 0:
            continue
        order = np.argsort(-y_score)
        rel_sorted = y_true[order]
        for k in ks:
            kk = min(k, len(y_true))
            ndcg[k].append(
                float(ndcg_score(y_true.reshape(1, -1), y_score.reshape(1, -1), k=kk))
            )
        k5 = min(5, len(y_true))
        gains = rel_sorted[:k5]
        denom = np.sum((2.0 ** rel_sorted[:k5] - 1.0) / np.log2(np.arange(2, k5 + 2)))
        if denom > 0:
            map5.append(float(np.sum(gains > 0) / max(1, np.sum(rel_sorted > 0))))
        else:
            map5.append(0.0)
        top_rel = rel_sorted[0] if len(rel_sorted) else 0.0
        mrr.append(1.0 if top_rel > 0 else 0.0)
        hit1.append(1.0 if top_rel > 0 else 0.0)
        p5.append(float(np.mean((rel_sorted[:k5] > 0).astype(float))))

    def mean(xs: list[float]) -> float:
        return float(np.mean(xs)) if xs else 0.0

    out: dict[str, float] = {
        "map@5": mean(map5),
        "mrr": mean(mrr),
        "hit@1": mean(hit1),
        "precision@5": mean(p5),
    }
    for k in ks:
        out[f"ndcg@{k}"] = mean(ndcg[k])
    return out


def adoption_metrics(y_true: np.ndarray, y_prob: np.ndarray) -> dict[str, float]:
    """Multi-label adoption classifier metrics."""
    y_pred = (y_prob >= 0.5).astype(int)
    return {
        "micro_f1": float(f1_score(y_true, y_pred, average="micro", zero_division=0)),
        "macro_f1": float(f1_score(y_true, y_pred, average="macro", zero_division=0)),
        "roc_auc_micro": float(roc_auc_score(y_true, y_prob, average="micro")),
        "map_micro": float(average_precision_score(y_true, y_prob, average="micro")),
    }


__all__ = ["adoption_metrics", "group_by_query", "ranking_metrics"]
