#!/usr/bin/env python3
"""Phase 2 Step 9: split a benchmark JSONL into train / dev / test for fair model comparison."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

_VALID = frozenset({"train", "dev", "test"})


def _load_rows(path: Path) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))
    return rows


def _normalize_split(raw: object) -> str | None:
    if not isinstance(raw, str) or not raw.strip():
        return None
    s = raw.strip().lower()
    if s in ("validation", "val"):
        return "dev"
    return s if s in _VALID else None


def assign_explicit(rows: list[dict[str, object]]) -> dict[str, list[dict[str, object]]]:
    buckets: dict[str, list[dict[str, object]]] = {"train": [], "dev": [], "test": []}
    errors: list[str] = []
    for i, row in enumerate(rows, start=1):
        ex = str(row.get("example_id", f"line_{i}"))
        sp = _normalize_split(row.get("split"))
        if sp is None:
            errors.append(f"{ex}: missing or invalid 'split' (use train, dev, test)")
            continue
        out = dict(row)
        out["split"] = sp
        buckets[sp].append(out)
    if errors:
        raise ValueError("\n".join(errors))
    return buckets


def assign_hash(
    rows: list[dict[str, object]],
    *,
    train_frac: float,
    dev_frac: float,
    seed: str,
) -> dict[str, list[dict[str, object]]]:
    if train_frac <= 0 or dev_frac < 0 or train_frac + dev_frac >= 1.0:
        raise ValueError("require train_frac > 0, dev_frac >= 0, train_frac + dev_frac < 1")

    test_frac = 1.0 - train_frac - dev_frac
    if test_frac <= 0:
        raise ValueError("implicit test fraction must be positive")

    buckets: dict[str, list[dict[str, object]]] = {"train": [], "dev": [], "test": []}
    for i, row in enumerate(rows):
        ex = str(row.get("example_id", f"line_{i+1}"))
        h = hashlib.sha256(f"{seed}:{ex}".encode()).digest()
        u = int.from_bytes(h[:8], "big") / (2**64)
        if u < train_frac:
            sp = "train"
        elif u < train_frac + dev_frac:
            sp = "dev"
        else:
            sp = "test"
        out = dict(row)
        out["split"] = sp
        buckets[sp].append(out)
    return buckets


def _write_split(out_dir: Path, name: str, rows: list[dict[str, object]]) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    p = out_dir / f"{name}.jsonl"
    with p.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    return p


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--benchmark", type=Path, required=True, help="Source benchmark JSONL")
    p.add_argument(
        "--out-dir",
        type=Path,
        required=True,
        help="Directory for benchmark_train.jsonl, benchmark_dev.jsonl, benchmark_test.jsonl",
    )
    p.add_argument(
        "--strategy",
        choices=("explicit", "hash"),
        required=True,
        help="explicit: each row must have split=train|dev|test. hash: deterministic split by example_id.",
    )
    p.add_argument("--train-fraction", type=float, default=0.7, help="For hash strategy only")
    p.add_argument("--dev-fraction", type=float, default=0.15, help="For hash strategy only")
    p.add_argument("--seed", type=str, default="phase2_split_v1", help="Salt for hash strategy")
    p.add_argument("--prefix", type=str, default="benchmark", help="Output file prefix")
    args = p.parse_args()

    if not args.benchmark.is_file():
        print(f"not found: {args.benchmark}", file=sys.stderr)
        return 2

    rows = _load_rows(args.benchmark)
    if not rows:
        print("benchmark has no rows", file=sys.stderr)
        return 1

    try:
        if args.strategy == "explicit":
            buckets = assign_explicit(rows)
        else:
            buckets = assign_hash(
                rows,
                train_frac=args.train_fraction,
                dev_frac=args.dev_fraction,
                seed=args.seed,
            )
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    written: list[str] = []
    for split_name in ("train", "dev", "test"):
        subset = buckets.get(split_name, [])
        path = _write_split(args.out_dir, f"{args.prefix}_{split_name}", subset)
        written.append(f"{split_name}={len(subset)} -> {path}")

    print("OK:", "; ".join(written))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
