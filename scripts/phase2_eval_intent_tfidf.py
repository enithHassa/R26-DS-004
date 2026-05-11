#!/usr/bin/env python3
"""Evaluate TF-IDF centroid intent baseline on Phase 2 benchmark rows (intent + joint tasks)."""

from __future__ import annotations

import argparse
import json
import random
import sys
from pathlib import Path

from sklearn.metrics import f1_score

_SCRIPTS = Path(__file__).resolve().parent
_REPO_ROOT = _SCRIPTS.parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from phase2_intent_tfidf import TfidfIntentCentroidClassifier  # noqa: E402
from phase2_task_registry import (  # noqa: E402
    default_task_id,
    gold_intent_for_row,
    intent_eval_task_ids,
    load_registry,
    task_map,
)


def _load_benchmark_rows(path: Path) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))
    return rows


def _intent_rows(
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


def _loocv(rows: list[dict[str, object]], registry: dict[str, object]) -> tuple[int, int, list[dict[str, str]]]:
    correct = 0
    details: list[dict[str, str]] = []
    n = len(rows)
    for i in range(n):
        train_idx = [j for j in range(n) if j != i]
        utt_train = [str(rows[j].get("utterance") or "") for j in train_idx]
        y_train = [gold_intent_for_row(rows[j], registry) or "" for j in train_idx]
        gold_i = gold_intent_for_row(rows[i], registry) or ""
        clf = TfidfIntentCentroidClassifier()
        clf.fit(utt_train, y_train)
        pred = clf.predict([str(rows[i].get("utterance") or "")])[0]
        ok = pred == gold_i
        if ok:
            correct += 1
        details.append(
            {
                "example_id": str(rows[i].get("example_id", f"row_{i}")),
                "gold": gold_i,
                "pred": pred,
                "match": str(ok),
            }
        )
    return correct, n, details


def _holdout(
    rows: list[dict[str, object]],
    registry: dict[str, object],
    *,
    test_fraction: float,
    seed: int,
) -> tuple[int, int, list[dict[str, str]]]:
    rng = random.Random(seed)
    idx = list(range(len(rows)))
    rng.shuffle(idx)
    n_test = max(1, int(round(len(rows) * test_fraction)))
    test_idx = set(idx[:n_test])
    train_idx = [j for j in range(len(rows)) if j not in test_idx]

    utt_train = [str(rows[j].get("utterance") or "") for j in train_idx]
    y_train = [gold_intent_for_row(rows[j], registry) or "" for j in train_idx]
    clf = TfidfIntentCentroidClassifier()
    clf.fit(utt_train, y_train)

    correct = 0
    details: list[dict[str, str]] = []
    for i in sorted(test_idx):
        gold_i = gold_intent_for_row(rows[i], registry) or ""
        pred = clf.predict([str(rows[i].get("utterance") or "")])[0]
        ok = pred == gold_i
        if ok:
            correct += 1
        details.append(
            {
                "example_id": str(rows[i].get("example_id", f"row_{i}")),
                "gold": gold_i,
                "pred": pred,
                "match": str(ok),
            }
        )
    return correct, len(test_idx), details


def _held_out_train_eval(
    train_rows: list[dict[str, object]],
    eval_rows: list[dict[str, object]],
    registry: dict[str, object],
) -> tuple[int, int, list[dict[str, str]]]:
    """Fit centroid on train_rows only; score all eval_rows (Phase 2 Step 10)."""
    utt_train = [str(r.get("utterance") or "") for r in train_rows]
    y_train = [gold_intent_for_row(r, registry) or "" for r in train_rows]
    clf = TfidfIntentCentroidClassifier()
    clf.fit(utt_train, y_train)
    correct = 0
    details: list[dict[str, str]] = []
    for i, row in enumerate(eval_rows):
        utt = str(row.get("utterance") or "")
        gold_i = gold_intent_for_row(row, registry) or ""
        pred = clf.predict([utt])[0]
        ok = pred == gold_i
        if ok:
            correct += 1
        details.append(
            {
                "example_id": str(row.get("example_id", f"eval_{i}")),
                "gold": gold_i,
                "pred": pred,
                "match": str(ok),
            }
        )
    return correct, len(eval_rows), details


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--benchmark",
        type=Path,
        required=True,
        help="Eval split (intent + joint rows scored). With --train-benchmark, eval only.",
    )
    p.add_argument(
        "--train-benchmark",
        type=Path,
        default=None,
        help="Train split: fit centroid on these intent/joint rows only (Step 10 held-out eval).",
    )
    p.add_argument(
        "--task-registry",
        type=Path,
        default=_REPO_ROOT / "evaluation" / "phase2_task_registry.json",
    )
    p.add_argument(
        "--mode",
        choices=("loocv", "holdout"),
        default="loocv",
        help="loocv: leave-one-out (default). holdout: random split (needs n>=2).",
    )
    p.add_argument("--test-fraction", type=float, default=0.25)
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--per-example", action="store_true", help="Include pred/gold lines in JSON output")
    args = p.parse_args()

    if not args.benchmark.is_file():
        print(f"benchmark not found: {args.benchmark}", file=sys.stderr)
        return 2
    if args.train_benchmark is not None and not args.train_benchmark.is_file():
        print(f"train-benchmark not found: {args.train_benchmark}", file=sys.stderr)
        return 2
    if not args.task_registry.is_file():
        print(f"registry not found: {args.task_registry}", file=sys.stderr)
        return 2

    registry = load_registry(args.task_registry)

    if args.train_benchmark is not None:
        train_rows = _intent_rows(_load_benchmark_rows(args.train_benchmark), registry)
        eval_rows = _intent_rows(_load_benchmark_rows(args.benchmark), registry)
        if not train_rows:
            print("No intent/joint rows with gold intent in train-benchmark.", file=sys.stderr)
            return 1
        if not eval_rows:
            print("No intent/joint rows with gold intent in eval benchmark.", file=sys.stderr)
            return 1
        hits, n, details = _held_out_train_eval(train_rows, eval_rows, registry)
        mode_out = "held_out_train_split"
    else:
        rows = _intent_rows(_load_benchmark_rows(args.benchmark), registry)
        if not rows:
            print("No intent-classification or joint_nlu_retrieval rows with gold intent.", file=sys.stderr)
            return 1

        if args.mode == "loocv":
            if len(rows) < 2:
                print("LOOCV needs at least 2 intent rows (or use --mode holdout with 1 row: trivial).", file=sys.stderr)
                return 1
            hits, n, details = _loocv(rows, registry)
        else:
            if len(rows) < 2:
                print("Holdout needs at least 2 intent rows.", file=sys.stderr)
                return 1
            hits, n, details = _holdout(rows, registry, test_fraction=args.test_fraction, seed=args.seed)
        mode_out = args.mode

    acc = hits / n if n else 0.0
    golds = [d["gold"] for d in details]
    preds = [d["pred"] for d in details]
    macro_f1 = float(f1_score(golds, preds, average="macro", zero_division=0)) if n else 0.0
    out: dict[str, object] = {
        "baseline": "tfidf_centroid",
        "mode": mode_out,
        "metric": "accuracy",
        "n": n,
        "hits": hits,
        "value": acc,
        "macro_f1": macro_f1,
    }
    if args.per_example:
        out["examples"] = details
    print(json.dumps(out, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
