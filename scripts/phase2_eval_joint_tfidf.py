#!/usr/bin/env python3
"""Joint eval (Phase 2 Step 3): intent match ∧ any gold_chunk in top-k (TF-IDF intent + TF-IDF retrieval)."""

from __future__ import annotations

import argparse
import json
import random
import sys
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parent
_REPO_ROOT = _SCRIPTS.parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

sys.path.insert(0, str(_REPO_ROOT / "backend" / "comp-language-model"))

from phase2_intent_tfidf import TfidfIntentCentroidClassifier  # noqa: E402
from phase2_task_registry import (  # noqa: E402
    default_task_id,
    gold_intent_for_row,
    intent_eval_task_ids,
    joint_eval_task_ids,
    load_registry,
    task_map,
)
from app.services.tfidf_chunk_index import TfidfChunkIndex  # noqa: E402
from phase2_retrieval_eval_core import ChunkSearchIndex  # noqa: E402


def _load_benchmark_rows(path: Path) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))
    return rows


def _intent_training_pool(
    rows: list[dict[str, object]], registry: dict[str, object]
) -> list[dict[str, object]]:
    want = intent_eval_task_ids(registry)
    tmap = task_map(registry)
    out: list[dict[str, object]] = []
    for row in rows:
        tid = row.get("task_id")
        if not tid or (isinstance(tid, str) and not str(tid).strip()):
            tid = default_task_id(registry)
        else:
            tid = str(tid).strip()
        if tid not in want:
            continue
        if tmap.get(tid, {}).get("status") == "planned":
            continue
        if gold_intent_for_row(row, registry) is None:
            continue
        out.append(row)
    return out


def _joint_rows(
    rows: list[dict[str, object]], registry: dict[str, object]
) -> list[dict[str, object]]:
    want = joint_eval_task_ids(registry)
    tmap = task_map(registry)
    out: list[dict[str, object]] = []
    for row in rows:
        tid = row.get("task_id")
        if not tid or (isinstance(tid, str) and not str(tid).strip()):
            continue
        tid = str(tid).strip()
        if tid not in want:
            continue
        if tmap.get(tid, {}).get("status") == "planned":
            continue
        gold = row.get("gold_chunk_ids") or []
        if not isinstance(gold, list) or len(gold) < 1:
            continue
        if gold_intent_for_row(row, registry) is None:
            continue
        out.append(row)
    return out


def _example_id(row: dict[str, object]) -> str:
    return str(row.get("example_id", ""))


def _eval_joint_loocv(
    pool: list[dict[str, object]],
    joint_rows: list[dict[str, object]],
    registry: dict[str, object],
    index: ChunkSearchIndex,
    k: int,
) -> tuple[list[dict[str, str | bool]], int, int, int, int]:
    """Returns details, joint_hits, n, intent_hits, retrieval_hits."""
    details: list[dict[str, str | bool]] = []
    joint_hits = 0
    intent_hits = 0
    retrieval_hits = 0
    n = len(joint_rows)

    for jrow in joint_rows:
        eid = _example_id(jrow)
        train = [r for r in pool if _example_id(r) != eid]
        if not train:
            raise ValueError(f"no training rows left for LOOCV (example_id={eid})")

        utt_train = [str(r.get("utterance") or "") for r in train]
        y_train = [gold_intent_for_row(r, registry) or "" for r in train]
        clf = TfidfIntentCentroidClassifier()
        clf.fit(utt_train, y_train)

        utt = str(jrow.get("utterance") or "")
        gold_i = gold_intent_for_row(jrow, registry) or ""
        pred = clf.predict([utt])[0]
        intent_ok = pred == gold_i
        if intent_ok:
            intent_hits += 1

        gold_chunks = {str(x) for x in (jrow.get("gold_chunk_ids") or [])}
        top_ids = [cid for cid, _ in index.search(utt, k)]
        ret_ok = bool(gold_chunks & set(top_ids))
        if ret_ok:
            retrieval_hits += 1

        joint_ok = intent_ok and ret_ok
        if joint_ok:
            joint_hits += 1

        details.append(
            {
                "example_id": eid,
                "gold_intent": gold_i,
                "pred_intent": pred,
                "intent_match": intent_ok,
                "retrieval_match": ret_ok,
                "joint_match": joint_ok,
            }
        )

    return details, joint_hits, n, intent_hits, retrieval_hits


def _eval_joint_fixed_train(
    train_pool: list[dict[str, object]],
    joint_rows: list[dict[str, object]],
    registry: dict[str, object],
    index: ChunkSearchIndex,
    k: int,
) -> tuple[list[dict[str, str | bool]], int, int, int, int]:
    """Fit intent once on train_pool; score only joint_rows from eval split (Step 10)."""
    if not train_pool:
        raise ValueError("empty train_pool")

    utt_train = [str(r.get("utterance") or "") for r in train_pool]
    y_train = [gold_intent_for_row(r, registry) or "" for r in train_pool]
    clf = TfidfIntentCentroidClassifier()
    clf.fit(utt_train, y_train)

    details: list[dict[str, str | bool]] = []
    joint_hits = 0
    intent_hits = 0
    retrieval_hits = 0
    n = len(joint_rows)

    for jrow in joint_rows:
        utt = str(jrow.get("utterance") or "")
        gold_i = gold_intent_for_row(jrow, registry) or ""
        pred = clf.predict([utt])[0]
        intent_ok = pred == gold_i
        if intent_ok:
            intent_hits += 1

        gold_chunks = {str(x) for x in (jrow.get("gold_chunk_ids") or [])}
        top_ids = [cid for cid, _ in index.search(utt, k)]
        ret_ok = bool(gold_chunks & set(top_ids))
        if ret_ok:
            retrieval_hits += 1

        joint_ok = intent_ok and ret_ok
        if joint_ok:
            joint_hits += 1

        details.append(
            {
                "example_id": _example_id(jrow),
                "gold_intent": gold_i,
                "pred_intent": pred,
                "intent_match": intent_ok,
                "retrieval_match": ret_ok,
                "joint_match": joint_ok,
            }
        )

    return details, joint_hits, n, intent_hits, retrieval_hits


def _eval_joint_holdout(
    pool: list[dict[str, object]],
    joint_rows: list[dict[str, object]],
    registry: dict[str, object],
    index: ChunkSearchIndex,
    k: int,
    *,
    test_fraction: float,
    seed: int,
) -> tuple[list[dict[str, str | bool]], int, int, int, int]:
    rng = random.Random(seed)
    pool_ids = [_example_id(r) for r in pool]
    idx = list(range(len(pool_ids)))
    rng.shuffle(idx)
    n_test = max(1, int(round(len(pool_ids) * test_fraction)))
    test_id_set = {pool_ids[i] for i in idx[:n_test]}
    train = [r for r in pool if _example_id(r) not in test_id_set]
    if not train:
        raise ValueError("holdout produced empty train pool")

    test_joint = [r for r in joint_rows if _example_id(r) in test_id_set]
    if not test_joint:
        raise ValueError("holdout test split has no joint_nlu_retrieval rows; adjust data or --test-fraction")

    utt_train = [str(r.get("utterance") or "") for r in train]
    y_train = [gold_intent_for_row(r, registry) or "" for r in train]
    clf = TfidfIntentCentroidClassifier()
    clf.fit(utt_train, y_train)

    details: list[dict[str, str | bool]] = []
    joint_hits = 0
    intent_hits = 0
    retrieval_hits = 0
    n = len(test_joint)

    for jrow in test_joint:
        utt = str(jrow.get("utterance") or "")
        gold_i = gold_intent_for_row(jrow, registry) or ""
        pred = clf.predict([utt])[0]
        intent_ok = pred == gold_i
        if intent_ok:
            intent_hits += 1

        gold_chunks = {str(x) for x in (jrow.get("gold_chunk_ids") or [])}
        top_ids = [cid for cid, _ in index.search(utt, k)]
        ret_ok = bool(gold_chunks & set(top_ids))
        if ret_ok:
            retrieval_hits += 1

        joint_ok = intent_ok and ret_ok
        if joint_ok:
            joint_hits += 1

        details.append(
            {
                "example_id": _example_id(jrow),
                "gold_intent": gold_i,
                "pred_intent": pred,
                "intent_match": intent_ok,
                "retrieval_match": ret_ok,
                "joint_match": joint_ok,
            }
        )

    return details, joint_hits, n, intent_hits, retrieval_hits


def _load_retrieval_index(corpus: Path, backend: str, dense_model: str) -> ChunkSearchIndex:
    if backend == "tfidf":
        return TfidfChunkIndex.from_jsonl(corpus)
    if backend == "dense":
        from app.services.dense_chunk_index import DenseChunkIndex  # noqa: PLC0415

        return DenseChunkIndex.from_jsonl(corpus, model_name=dense_model)
    raise ValueError(f"unknown retrieval backend: {backend}")


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--corpus-jsonl", type=Path, required=True)
    p.add_argument(
        "--benchmark",
        type=Path,
        required=True,
        help="Eval split: joint rows scored here. With --intent-train-benchmark, train intent from that file only.",
    )
    p.add_argument(
        "--intent-train-benchmark",
        type=Path,
        default=None,
        help="Train split for intent centroid only (Step 10). Eval joint rows come from --benchmark.",
    )
    p.add_argument("--k", type=int, default=8)
    p.add_argument(
        "--task-registry",
        type=Path,
        default=_REPO_ROOT / "evaluation" / "phase2_task_registry.json",
    )
    p.add_argument("--mode", choices=("loocv", "holdout"), default="loocv")
    p.add_argument("--test-fraction", type=float, default=0.25)
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--per-example", action="store_true")
    p.add_argument(
        "--retrieval-backend",
        choices=("tfidf", "dense"),
        default="tfidf",
        help="Chunk retrieval index for the joint metric (Step 11: dense = sentence-transformers).",
    )
    p.add_argument(
        "--dense-model",
        type=str,
        default="sentence-transformers/all-MiniLM-L6-v2",
        help="Used when --retrieval-backend dense",
    )
    args = p.parse_args()

    if not args.corpus_jsonl.is_file() or not args.benchmark.is_file():
        print("corpus or benchmark not found", file=sys.stderr)
        return 2
    if args.intent_train_benchmark is not None and not args.intent_train_benchmark.is_file():
        print(f"intent-train-benchmark not found: {args.intent_train_benchmark}", file=sys.stderr)
        return 2
    if not args.task_registry.is_file():
        print(f"registry not found: {args.task_registry}", file=sys.stderr)
        return 2

    registry = load_registry(args.task_registry)
    all_rows = _load_benchmark_rows(args.benchmark)
    joint_rows = _joint_rows(all_rows, registry)

    if not joint_rows:
        print("No joint_nlu_retrieval rows with gold intent and gold_chunk_ids.", file=sys.stderr)
        return 1

    try:
        index = _load_retrieval_index(args.corpus_jsonl, args.retrieval_backend, args.dense_model)
    except ImportError as e:
        print(str(e), file=sys.stderr)
        return 2

    if args.intent_train_benchmark is not None:
        train_all = _load_benchmark_rows(args.intent_train_benchmark)
        pool = _intent_training_pool(train_all, registry)
        if not pool:
            print("No intent training rows in intent-train-benchmark.", file=sys.stderr)
            return 1
        details, joint_hits, n, intent_hits, retrieval_hits = _eval_joint_fixed_train(
            pool, joint_rows, registry, index, args.k
        )
        mode_out = "held_out_train_split"
    else:
        pool = _intent_training_pool(all_rows, registry)
        if len(pool) < 2 and args.mode == "loocv":
            print("LOOCV needs at least 2 rows in the intent training pool.", file=sys.stderr)
            return 1
        if args.mode == "holdout" and len(pool) < 2:
            print("Holdout needs at least 2 rows in the intent training pool.", file=sys.stderr)
            return 1

        if args.mode == "loocv":
            details, joint_hits, n, intent_hits, retrieval_hits = _eval_joint_loocv(
                pool, joint_rows, registry, index, args.k
            )
        else:
            details, joint_hits, n, intent_hits, retrieval_hits = _eval_joint_holdout(
                pool,
                joint_rows,
                registry,
                index,
                args.k,
                test_fraction=args.test_fraction,
                seed=args.seed,
            )
        mode_out = args.mode

    if args.retrieval_backend == "dense":
        joint_baseline = "tfidf_centroid_intent_plus_dense_retrieval"
    else:
        joint_baseline = "tfidf_centroid_intent_plus_tfidf_retrieval"

    out: dict[str, object] = {
        "metric": "joint_success",
        "definition": "intent_pred == gold_intent AND any gold_chunk_id in top-k retrieval",
        "baseline": joint_baseline,
        "retrieval_backend": args.retrieval_backend,
        "mode": mode_out,
        "k": args.k,
        "n_joint": n,
        "joint_hits": joint_hits,
        "joint_success_rate": joint_hits / n if n else 0.0,
        "intent_accuracy_on_joint": intent_hits / n if n else 0.0,
        "retrieval_recall_at_k_on_joint": retrieval_hits / n if n else 0.0,
    }
    if args.retrieval_backend == "dense":
        out["dense_model"] = args.dense_model
    if args.per_example:
        out["examples"] = details
    print(json.dumps(out, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
