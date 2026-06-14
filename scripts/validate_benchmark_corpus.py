#!/usr/bin/env python3
"""Ensure benchmark rows are valid for Phase 2 tasks and gold_chunk_ids exist in corpus_v1 JSONL."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_SCRIPTS_DIR = Path(__file__).resolve().parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

_REPO_ROOT = Path(__file__).resolve().parents[1]
_DEFAULT_REGISTRY = _REPO_ROOT / "evaluation" / "phase2_task_registry.json"

from phase2_task_registry import load_registry, validate_example_row


def _load_corpus_ids(path: Path) -> set[str]:
    ids: set[str] = set()
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            obj = json.loads(line)
            cid = obj.get("chunk_id")
            if cid:
                ids.add(str(cid))
    return ids


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--benchmark", type=Path, required=True, help="JSONL benchmark (Phase 2)")
    p.add_argument("--corpus-jsonl", type=Path, required=True, help="corpus_v1.jsonl")
    p.add_argument(
        "--task-registry",
        type=Path,
        default=_DEFAULT_REGISTRY,
        help="Phase 2 task registry JSON (default: evaluation/phase2_task_registry.json)",
    )
    p.add_argument(
        "--skip-task-shape",
        action="store_true",
        help="Only check that gold_chunk_ids exist in corpus (ignore task_id / required fields).",
    )
    args = p.parse_args()

    if not args.benchmark.is_file():
        print(f"benchmark not found: {args.benchmark}", file=sys.stderr)
        return 2
    if not args.corpus_jsonl.is_file():
        print(f"corpus not found: {args.corpus_jsonl}", file=sys.stderr)
        return 2

    task_registry: dict | None = None
    if not args.skip_task_shape:
        if not args.task_registry.is_file():
            print(
                f"task registry not found: {args.task_registry} (use --skip-task-shape to omit)",
                file=sys.stderr,
            )
            return 2
        task_registry = load_registry(args.task_registry)

    corpus_ids = _load_corpus_ids(args.corpus_jsonl)
    shape_errors: list[str] = []
    missing: list[tuple[str, str]] = []
    n = 0
    with args.benchmark.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            n += 1
            row = json.loads(line)
            if task_registry is not None:
                shape_errors.extend(validate_example_row(row, registry=task_registry, line_no=n))
            ex_id = str(row.get("example_id", f"line_{n}"))
            for gid in row.get("gold_chunk_ids") or []:
                g = str(gid)
                if g not in corpus_ids:
                    missing.append((ex_id, g))

    if shape_errors:
        print("Task / schema validation errors:")
        for e in shape_errors[:80]:
            print(f"  {e}")
        if len(shape_errors) > 80:
            print(f"  ... and {len(shape_errors) - 80} more")
        return 1

    if missing:
        print(f"Missing {len(missing)} gold chunk_id(s) (examples × corpus):")
        for ex_id, gid in missing[:50]:
            print(f"  {ex_id}: {gid}")
        if len(missing) > 50:
            print(f"  ... and {len(missing) - 50} more")
        return 1

    extra = ""
    if task_registry is not None:
        extra = "; task shape OK"
    print(f"OK: {n} benchmark row(s); all gold_chunk_ids present in corpus ({len(corpus_ids)} chunks){extra}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
