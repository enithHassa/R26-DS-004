#!/usr/bin/env python3
"""Print Phase 3 ETL MERGE bundles for the first N rows of a corpus_v1 JSONL (preview / debugging)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_SCRIPTS_DIR = Path(__file__).resolve().parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

import ird_corpus_lib as icl
import kg_etl_lib as kel


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--corpus-jsonl", type=Path, required=True)
    p.add_argument("--limit", type=int, default=5)
    p.add_argument(
        "--no-text",
        action="store_true",
        help="Omit TextChunk.text in bundle (smaller preview).",
    )
    p.add_argument("--text-max-chars", type=int, default=None)
    args = p.parse_args()

    if not args.corpus_jsonl.is_file():
        print(f"not found: {args.corpus_jsonl}", file=sys.stderr)
        return 2

    n = 0
    with args.corpus_jsonl.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            errs = icl.validate_kg_chunk_metadata(row, line_no=n + 1)
            if errs:
                for e in errs:
                    print(e, file=sys.stderr)
                return 1
            bundle = kel.etl_bundle_from_chunk_row(
                row,
                include_text=not args.no_text,
                text_max_chars=args.text_max_chars,
            )
            print(json.dumps(bundle, ensure_ascii=False, indent=2))
            n += 1
            if n >= args.limit:
                break
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
