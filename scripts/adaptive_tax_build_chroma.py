#!/usr/bin/env python3
"""Build embedded Chroma collection from adaptive-tax corpus_v1.jsonl.

Uses sentence-transformers/all-MiniLM-L6-v2 (local). No Docker / OpenAI required.

Example::

  .\\.venv-backend\\Scripts\\python.exe scripts/adaptive_tax_build_chroma.py --reset
  .\\.venv-backend\\Scripts\\python.exe scripts/adaptive_tax_build_chroma.py --limit 50
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parent
_REPO = _SCRIPTS.parent
_COMP = _REPO / "backend" / "comp-adaptive-tax"

# Allow importing adaptive_tax_app without requiring uvicorn startup.
for p in (_REPO, _COMP):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from adaptive_tax_app.services.chroma_index import (  # noqa: E402
    DEFAULT_COLLECTION,
    DEFAULT_EMBEDDING_MODEL,
    AdaptiveTaxChromaIndex,
)


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--corpus-jsonl",
        type=Path,
        default=_REPO / "data" / "processed" / "adaptive-tax" / "corpus_v1.jsonl",
    )
    p.add_argument(
        "--persist-dir",
        type=Path,
        default=Path(
            os.environ.get("CHROMA_PERSIST_DIR", "data/processed/adaptive-tax/chroma")
        ),
    )
    p.add_argument(
        "--collection",
        type=str,
        default=os.environ.get("CHROMA_COLLECTION", DEFAULT_COLLECTION),
    )
    p.add_argument("--embedding-model", type=str, default=DEFAULT_EMBEDDING_MODEL)
    p.add_argument("--batch-size", type=int, default=64)
    p.add_argument("--limit", type=int, default=None, help="Index only first N chunks (smoke)")
    p.add_argument("--reset", action="store_true", help="Drop and recreate the collection")
    p.add_argument(
        "--smoke-query",
        type=str,
        default="",
        help="Optional query after build (e.g. 'qualifying payment')",
    )
    p.add_argument("--smoke-section", type=str, default="", help="Optional section_ref filter")
    args = p.parse_args()

    corpus = args.corpus_jsonl
    if not corpus.is_file():
        print(f"corpus not found: {corpus}", file=sys.stderr)
        return 2

    persist = args.persist_dir
    if not persist.is_absolute():
        persist = _REPO / persist

    index = AdaptiveTaxChromaIndex(
        persist_dir=persist,
        collection_name=args.collection,
        embedding_model=args.embedding_model,
    )
    print(
        f"indexing {corpus} -> {persist} collection={args.collection} "
        f"reset={args.reset} limit={args.limit}"
    )
    written = index.upsert_from_corpus_jsonl(
        corpus,
        limit=args.limit,
        batch_size=args.batch_size,
        reset=args.reset,
    )
    print(f"upserted {written} chunk(s); collection count={index.count()}")

    if args.smoke_query.strip():
        hits = index.search(
            args.smoke_query,
            section_ref=args.smoke_section or None,
            top_k=5,
        )
        print(f"smoke hits ({len(hits)}):")
        for h in hits:
            preview = (h.text or "").replace("\n", " ")[:120]
            print(
                f"  score={h.score!s} page={h.page} doc={h.source_doc_id} "
                f"section={h.section_ref!r} id={h.chunk_id}"
            )
            print(f"    {preview}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
