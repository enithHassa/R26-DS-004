#!/usr/bin/env python3
"""Phase 2 Step 6: summarize evaluation/phase2_runs.jsonl into a leaderboard (quality, latency, cost)."""

from __future__ import annotations

import argparse
import csv
import io
import json
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
_DEFAULT_INPUT = _REPO_ROOT / "evaluation" / "phase2_runs.jsonl"


def _num(v: object) -> float:
    if v is None:
        return float("-inf")
    if isinstance(v, (int, float)):
        return float(v)
    try:
        return float(v)
    except (TypeError, ValueError):
        return float("-inf")


def _load_runs(path: Path) -> list[dict[str, object]]:
    if not path.is_file():
        return []
    rows: list[dict[str, object]] = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return rows


def _row_view(rec: dict[str, object]) -> dict[str, object]:
    m = rec.get("metrics") if isinstance(rec.get("metrics"), dict) else {}
    rt = rec.get("runtime") if isinstance(rec.get("runtime"), dict) else {}
    cost = rec.get("cost") if isinstance(rec.get("cost"), dict) else {}
    ds = rec.get("dataset") if isinstance(rec.get("dataset"), dict) else {}
    err = rec.get("phase2_errors")
    has_err = bool(err) if isinstance(err, dict) else bool(err)
    return {
        "run_id": rec.get("run_id", ""),
        "model_version": rec.get("model_version", ""),
        "retrieval_r_at_k": m.get("phase2_retrieval_recall_at_k_any_gold"),
        "retrieval_mrr": m.get("phase2_retrieval_mrr_at_k"),
        "retrieval_n": m.get("phase2_retrieval_n_evaluated"),
        "intent_acc": m.get("phase2_intent_accuracy"),
        "intent_macro_f1": m.get("phase2_intent_macro_f1"),
        "joint_success": m.get("phase2_joint_success_rate"),
        "joint_n": m.get("phase2_joint_n"),
        "duration_s": rt.get("duration_seconds"),
        "cost_usd": cost.get("estimated_total"),
        "benchmark": ds.get("name", ""),
        "top_k": ds.get("retrieval_top_k"),
        "has_errors": has_err,
        "notes": (rec.get("notes") or "")[:80],
    }


def _latency_sort_key(rec: dict[str, object]) -> float:
    """Lower duration first (better); missing last."""
    rt = rec.get("runtime")
    if not isinstance(rt, dict):
        return float("inf")
    v = rt.get("duration_seconds")
    if v is None:
        return float("inf")
    try:
        return float(v)
    except (TypeError, ValueError):
        return float("inf")


def _sort_key(rec: dict[str, object], primary: str) -> tuple[float, ...]:
    m = rec.get("metrics") if isinstance(rec.get("metrics"), dict) else {}
    joint = _num(m.get("phase2_joint_success_rate"))
    retr = _num(m.get("phase2_retrieval_recall_at_k_any_gold"))
    intent_f1 = _num(m.get("phase2_intent_macro_f1"))

    if primary == "retrieval":
        return (retr, joint, intent_f1)
    if primary == "intent":
        return (intent_f1, joint, retr)
    # default: joint first (end-to-end), then retrieval, then intent F1
    return (joint, retr, intent_f1)


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--input", type=Path, default=_DEFAULT_INPUT, help="phase2_runs.jsonl path")
    p.add_argument(
        "--format",
        choices=("markdown", "json", "csv"),
        default="markdown",
    )
    p.add_argument(
        "--sort",
        choices=("joint", "retrieval", "intent", "latency"),
        default="joint",
        help="Primary sort key (descending except latency ascending by duration)",
    )
    p.add_argument(
        "--include-errors",
        action="store_true",
        help="Include runs that recorded phase2_errors (default: skip them)",
    )
    args = p.parse_args()

    runs = _load_runs(args.input)
    if not runs:
        print(f"No runs loaded from {args.input} (missing or empty).", file=sys.stderr)
        if args.format == "json":
            print(json.dumps({"runs": [], "message": "empty"}, indent=2))
        return 0

    filtered: list[dict[str, object]] = []
    for r in runs:
        if not args.include_errors and r.get("phase2_errors"):
            continue
        filtered.append(r)

    if args.sort == "latency":
        filtered.sort(key=_latency_sort_key)
    else:
        filtered.sort(key=lambda r: _sort_key(r, args.sort), reverse=True)

    views = [_row_view(r) for r in filtered]

    if args.format == "json":
        print(json.dumps({"sort": args.sort, "count": len(views), "leaderboard": views}, indent=2))
        return 0

    if args.format == "csv":
        buf = io.StringIO()
        if views:
            w = csv.DictWriter(buf, fieldnames=list(views[0].keys()))
            w.writeheader()
            w.writerows(views)
        sys.stdout.write(buf.getvalue())
        return 0

    # markdown
    cols = [
        "model_version",
        "retrieval_r_at_k",
        "retrieval_mrr",
        "retrieval_n",
        "intent_acc",
        "intent_macro_f1",
        "joint_success",
        "joint_n",
        "duration_s",
        "cost_usd",
        "has_errors",
        "run_id",
    ]
    headers = "| " + " | ".join(cols) + " |"
    sep = "| " + " | ".join("---" for _ in cols) + " |"
    lines = [headers, sep]
    for v in views:
        cells = []
        for c in cols:
            val = v.get(c)
            if val is None:
                cells.append("")
            elif isinstance(val, float):
                cells.append(f"{val:.4f}")
            elif isinstance(val, bool):
                cells.append(str(val).lower())
            else:
                cells.append(str(val))
        lines.append("| " + " | ".join(cells) + " |")
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
