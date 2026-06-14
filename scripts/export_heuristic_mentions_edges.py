#!/usr/bin/env python3
"""Emit MENTIONS edge JSONL from corpus_v1 + concept aliases (Phase 3 Step 7 automation).

Output rows are valid input for neo4j_load_curated_edges.py after Concept nodes exist.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

import ird_corpus_lib as icl
import kg_edges_heuristic_lib as heu


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--corpus-jsonl", type=Path, required=True)
    p.add_argument("--concepts-json", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--confidence", type=float, default=0.4)
    p.add_argument("--limit-chunks", type=int, default=None)
    args = p.parse_args()

    if not args.corpus_jsonl.is_file():
        print(f"not found: {args.corpus_jsonl}", file=sys.stderr)
        return 2
    if not args.concepts_json.is_file():
        print(f"not found: {args.concepts_json}", file=sys.stderr)
        return 2

    concepts = heu.load_concepts_json(args.concepts_json)
    n_chunks = 0
    n_edges = 0
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.corpus_jsonl.open(encoding="utf-8") as fin, args.out.open("w", encoding="utf-8") as fout:
        for line in fin:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            errs = icl.validate_kg_chunk_metadata(row, line_no=n_chunks + 1)
            if errs:
                for e in errs:
                    print(e, file=sys.stderr)
                return 1
            for edge in heu.suggest_mentions_edges(row, concepts, base_confidence=args.confidence):
                fout.write(json.dumps(edge, ensure_ascii=False) + "\n")
                n_edges += 1
            n_chunks += 1
            if args.limit_chunks is not None and n_chunks >= args.limit_chunks:
                break

    print(f"wrote {n_edges} MENTIONS row(s) from {n_chunks} chunk(s) -> {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
