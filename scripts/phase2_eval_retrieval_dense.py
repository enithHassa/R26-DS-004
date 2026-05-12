#!/usr/bin/env python3
"""Dense embedding retrieval eval: recall@k vs gold_chunk_ids (Phase 2 Step 11, sentence-transformers)."""

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

from app.services.dense_chunk_index import DenseChunkIndex  # noqa: E402
from phase2_retrieval_eval_core import run_retrieval_eval_from_paths  # noqa: E402


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--corpus-jsonl", type=Path, required=True)
    p.add_argument("--benchmark", type=Path, required=True)
    p.add_argument("--k", type=int, default=8, help="Top-k for retrieval")
    p.add_argument(
        "--model-name",
        type=str,
        default="sentence-transformers/all-MiniLM-L6-v2",
        help="Sentence-Transformers model id (Hugging Face)",
    )
    p.add_argument(
        "--batch-size",
        type=int,
        default=64,
        help="Encode batch size when indexing the corpus",
    )
    p.add_argument(
        "--task-registry",
        type=Path,
        default=_REPO_ROOT / "evaluation" / "phase2_task_registry.json",
    )
    args = p.parse_args()

    if not args.corpus_jsonl.is_file() or not args.benchmark.is_file():
        print("corpus or benchmark path missing", file=sys.stderr)
        return 2
    if not args.task_registry.is_file():
        print(f"task registry missing: {args.task_registry}", file=sys.stderr)
        return 2

    try:
        index = DenseChunkIndex.from_jsonl(
            args.corpus_jsonl,
            model_name=args.model_name,
            batch_size=args.batch_size,
        )
    except ImportError as e:
        print(str(e), file=sys.stderr)
        return 2

    out = run_retrieval_eval_from_paths(
        index,
        benchmark_path=args.benchmark,
        registry_path=args.task_registry,
        k=args.k,
        baseline="sentence_transformers_dense",
        extra={"model_name": args.model_name},
    )
    print(json.dumps(out, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
