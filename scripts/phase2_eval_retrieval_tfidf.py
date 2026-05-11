#!/usr/bin/env python3
"""TF-IDF baseline retrieval eval: recall@k vs benchmark gold_chunk_ids (Phase 2 retrieval tasks only)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parent
_REPO_ROOT = _SCRIPTS.parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

sys.path.insert(0, str(_REPO_ROOT / "backend" / "comp-language-model"))

from app.services.tfidf_chunk_index import TfidfChunkIndex  # noqa: E402
from phase2_retrieval_eval_core import run_retrieval_eval_from_paths  # noqa: E402


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--corpus-jsonl", type=Path, required=True)
    p.add_argument("--benchmark", type=Path, required=True)
    p.add_argument("--k", type=int, default=8, help="Top-k for retrieval")
    p.add_argument(
        "--task-registry",
        type=Path,
        default=_REPO_ROOT / "evaluation" / "phase2_task_registry.json",
        help="Registry JSON (for task_id defaults and retrieval task set)",
    )
    args = p.parse_args()

    if not args.corpus_jsonl.is_file() or not args.benchmark.is_file():
        print("corpus or benchmark path missing", file=sys.stderr)
        return 2
    if not args.task_registry.is_file():
        print(f"task registry missing: {args.task_registry}", file=sys.stderr)
        return 2

    index = TfidfChunkIndex.from_jsonl(args.corpus_jsonl)
    out = run_retrieval_eval_from_paths(
        index,
        benchmark_path=args.benchmark,
        registry_path=args.task_registry,
        k=args.k,
        baseline="tfidf_bow",
    )
    print(json.dumps(out, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
