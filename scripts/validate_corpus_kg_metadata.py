#!/usr/bin/env python3
"""Validate corpus_v1 JSONL rows for Phase 3 KG loading (metadata normalization contract)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_SCRIPTS_DIR = Path(__file__).resolve().parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

import ird_corpus_lib as icl


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--corpus-jsonl", type=Path, required=True, help="corpus_v1.jsonl")
    p.add_argument(
        "--strict-doc-meta",
        action="store_true",
        help="Require non-empty tier and instrument_type on every row (production corpus).",
    )
    p.add_argument(
        "--max-errors",
        type=int,
        default=50,
        help="Stop printing after this many errors (default 50).",
    )
    args = p.parse_args()

    if not args.corpus_jsonl.is_file():
        print(f"corpus not found: {args.corpus_jsonl}", file=sys.stderr)
        return 2

    n = 0
    err_count = 0
    with args.corpus_jsonl.open(encoding="utf-8") as f:
        for line_no, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            n += 1
            row = json.loads(line)
            errs = icl.validate_kg_chunk_metadata(
                row, line_no=line_no, strict_doc_meta=args.strict_doc_meta
            )
            if errs:
                for e in errs:
                    if err_count < args.max_errors:
                        print(e, file=sys.stderr)
                    err_count += 1

    if err_count:
        print(
            f"kg metadata: {n} rows, {err_count} error(s)"
            + (f" (showing first {args.max_errors})" if err_count > args.max_errors else ""),
            file=sys.stderr,
        )
        return 1
    print(f"kg metadata: {n} rows, OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
