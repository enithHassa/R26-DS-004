#!/usr/bin/env python3
"""Phase 3 Step 13 — build NPZ + node_embeddings_meta.json keyed by graph node id (TextChunk.chunk_id).

Uses DenseChunkIndex encoding (sentence-transformers). Install:
  pip install -r backend/requirements-retrieval-dense.txt

PYTHONPATH must include backend/comp-language-model for `app` imports.
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
_LM = _REPO / "backend" / "comp-language-model"
if str(_LM) not in sys.path:
    sys.path.insert(0, str(_LM))

from app.services.dense_chunk_index import DenseChunkIndex

_SCRIPTS = Path(__file__).resolve().parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

import kg_node_embeddings_lib as kne


def _default_run_id() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--corpus-jsonl", type=Path, required=True)
    p.add_argument("--out-dir", type=Path, required=True)
    p.add_argument(
        "--embedding-model-id",
        default="sentence-transformers/all-MiniLM-L6-v2",
        help="Passed to SentenceTransformer / DenseChunkIndex",
    )
    p.add_argument(
        "--embedding-run-id",
        default=None,
        help="Directory name segment; default UTC timestamp",
    )
    p.add_argument("--dry-run", action="store_true", help="Write pending meta + row_count only")
    p.add_argument("--batch-size", type=int, default=64)
    p.add_argument("--device", type=str, default=None)
    args = p.parse_args()

    if not args.corpus_jsonl.is_file():
        print(f"not found: {args.corpus_jsonl}", file=sys.stderr)
        return 2

    run_id = args.embedding_run_id or _default_run_id()
    root = args.out_dir / run_id
    model_slug = args.embedding_model_id.replace("/", "__")

    if args.dry_run:
        n = 0
        with args.corpus_jsonl.open(encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    n += 1
        meta = {
            "schema_version": "1",
            "phase": "3a-step13",
            "neo4j_label": "TextChunk",
            "id_property": "chunk_id",
            "embedding_model_id": args.embedding_model_id,
            "embedding_run_id": run_id,
            "corpus_version": "corpus_v1",
            "vector_storage": {
                "format": "pending",
                "filename": f"textchunk__{model_slug}.npz",
                "array_key": "embeddings",
                "ids_key": "chunk_ids",
                "dtype": "float32",
                "normalized": True,
            },
            "row_count": n,
        }
        kne.write_pending_meta(root, meta)
        print(f"dry-run: wrote pending meta for {n} chunk(s) -> {root / 'node_embeddings_meta.json'}")
        return 0

    try:
        index = DenseChunkIndex.from_jsonl(
            args.corpus_jsonl,
            model_name=args.embedding_model_id,
            batch_size=args.batch_size,
            device=args.device,
        )
    except ImportError as e:
        print(str(e), file=sys.stderr)
        return 2

    dim = int(index.embeddings.shape[1])
    meta = {
        "schema_version": "1",
        "phase": "3a-step13",
        "neo4j_label": "TextChunk",
        "id_property": "chunk_id",
        "embedding_model_id": args.embedding_model_id,
        "embedding_run_id": run_id,
        "corpus_version": "corpus_v1",
        "vector_storage": {
            "format": "npz_compressed",
            "filename": f"textchunk__{model_slug}.npz",
            "array_key": "embeddings",
            "ids_key": "chunk_ids",
            "dimensions": dim,
            "dtype": "float32",
            "normalized": True,
        },
        "row_count": index.size,
    }
    kne.write_bundle(
        root,
        meta=meta,
        chunk_ids=index.chunk_ids,
        embeddings=index.embeddings,
    )
    print(f"wrote bundle: {root} ({index.size} vectors, dim={dim})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
