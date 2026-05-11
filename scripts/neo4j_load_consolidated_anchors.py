#!/usr/bin/env python3
"""Phase 3 Step 10 — MERGE :ConsolidatedViewPassage nodes from JSONL (optional workflow).

Each line: anchor_id, source_doc_id, consolidated_as_of, optional section_label_snapshot, chunk_id, review_status.
Load VIEW_* trace edges separately via neo4j_load_curated_edges.py.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

_SCRIPTS = Path(__file__).resolve().parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

import kg_consolidated_view_lib as kcv

try:
    from neo4j import GraphDatabase
except ImportError:
    print("Install neo4j driver: pip install -r knowledge_graph/requirements-neo4j.txt", file=sys.stderr)
    raise SystemExit(2) from None


def _merge_anchor_tx(tx: Any, row: dict[str, Any]) -> None:
    props = kcv.props_for_neo4j(row)
    aid = props.get("anchor_id")
    if not aid:
        raise ValueError("anchor_id missing")
    tx.run(
        """
        MERGE (n:ConsolidatedViewPassage {anchor_id: $anchor_id})
        SET n += $props
        """,
        anchor_id=aid,
        props=props,
    )


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--anchors-jsonl", type=Path, required=True)
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--limit", type=int, default=None)
    args = p.parse_args()

    if not args.anchors_jsonl.is_file():
        print(f"not found: {args.anchors_jsonl}", file=sys.stderr)
        return 2

    uri = os.environ.get("NEO4J_URI", "neo4j://127.0.0.1:7687")
    user = os.environ.get("NEO4J_USER", "neo4j")
    password = os.environ.get("NEO4J_PASSWORD", "")

    driver = None
    if not args.dry_run:
        if not password:
            print("NEO4J_PASSWORD is not set (or use --dry-run)", file=sys.stderr)
            return 2
        driver = GraphDatabase.driver(uri, auth=(user, password))

    ok = 0
    bad = 0
    n = 0
    try:
        with args.anchors_jsonl.open(encoding="utf-8") as f:
            for line_no, line in enumerate(f, start=1):
                line = line.strip()
                if not line:
                    continue
                row = json.loads(line)
                errs = kcv.validate_anchor_row(row, line_no=line_no)
                if errs:
                    bad += 1
                    for e in errs:
                        print(e, file=sys.stderr)
                    continue
                if args.dry_run:
                    ok += 1
                else:
                    assert driver is not None
                    with driver.session() as session:
                        session.execute_write(lambda tx, r=row: _merge_anchor_tx(tx, r))
                    ok += 1
                n += 1
                if args.limit is not None and n >= args.limit:
                    break
    finally:
        if driver is not None:
            driver.close()

    mode = "dry-run" if args.dry_run else "loaded"
    print(f"{mode}: {ok} anchor row(s) OK, {bad} invalid")
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
