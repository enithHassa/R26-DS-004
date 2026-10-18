#!/usr/bin/env python3
"""Export TextChunk nodes from Neo4j into corpus_v1 JSONL for Component 4 retrieval.

Reads NEO4J_* from repo-root .env. Use when the KG is populated but
data/processed/ird/corpus_v1.jsonl is missing locally.

  export PYTHONPATH="backend/comp-language-model:${PWD}"
  python scripts/export_neo4j_corpus_jsonl.py --out data/processed/ird/corpus_v1.jsonl
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
_COMP = _REPO / "backend" / "comp-language-model"
for path in (str(_REPO), str(_COMP)):
    if path not in sys.path:
        sys.path.insert(0, path)

try:
    from neo4j import GraphDatabase
except ImportError:
    print("Install neo4j driver: pip install 'neo4j>=5.14.0,<6'", file=sys.stderr)
    raise SystemExit(2) from None

from app.config import get_lm_settings


def export_corpus(out_path: Path) -> int:
    cfg = get_lm_settings()
    if not cfg.NEO4J_PASSWORD:
        print("NEO4J_PASSWORD is not set in .env", file=sys.stderr)
        raise SystemExit(1)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    driver = GraphDatabase.driver(
        cfg.NEO4J_URI,
        auth=(cfg.NEO4J_USER, cfg.NEO4J_PASSWORD),
    )
    count = 0
    with driver.session(database=cfg.NEO4J_DATABASE) as session:
        result = session.run(
            """
            MATCH (t:TextChunk)
            WHERE t.chunk_id IS NOT NULL AND t.text IS NOT NULL
            RETURN t
            ORDER BY t.chunk_id
            """
        )
        with out_path.open("w", encoding="utf-8") as fp:
            for record in result:
                node = dict(record["t"])
                chunk_id = str(node.get("chunk_id") or "").strip()
                text = str(node.get("text") or "").strip()
                if not chunk_id or not text:
                    continue
                row: dict[str, object] = {
                    "chunk_id": chunk_id,
                    "text": text,
                    "corpus_version": node.get("corpus_version") or "corpus_v1",
                }
                for key in (
                    "source_doc_id",
                    "section_label",
                    "tier",
                    "instrument_type",
                    "content_kind",
                    "page",
                    "chunk_index",
                    "authority_class",
                    "effective_from",
                ):
                    val = node.get(key)
                    if val is not None and str(val).strip():
                        row[key] = val
                fp.write(json.dumps(row, ensure_ascii=False) + "\n")
                count += 1
    driver.close()
    return count


def main() -> None:
    parser = argparse.ArgumentParser(description="Export Neo4j TextChunk nodes to corpus JSONL")
    parser.add_argument(
        "--out",
        type=Path,
        default=_REPO / "data" / "processed" / "ird" / "corpus_v1.jsonl",
        help="Output JSONL path",
    )
    args = parser.parse_args()
    n = export_corpus(args.out)
    print(f"Exported {n} chunks -> {args.out}")


if __name__ == "__main__":
    main()
