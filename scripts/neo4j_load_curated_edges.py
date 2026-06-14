#!/usr/bin/env python3
"""Load curated edge JSONL into Neo4j (ontology-validated; Phase 3 Steps 7 + 9).

Each row: MATCH endpoints, MERGE (a)-[r:REL]->(b) SET r += metadata.
If either endpoint is missing, no relationship is created (count as miss with --warn-miss).

Lex override edges (OVERRIDES, MODIFIES, SUPERSEDES): see knowledge_graph/lex_override_paths_v1.json.
Use --strict-lex-overrides to require source_note + review_status on those rel types.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

_SCRIPTS = Path(__file__).resolve().parent
_REPO = _SCRIPTS.parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

import kg_curated_edges_lib as kce
import kg_ontology_lib as kol
import kg_override_edges_lib as kov

try:
    from neo4j import GraphDatabase
except ImportError:
    print("Install neo4j driver: pip install -r knowledge_graph/requirements-neo4j.txt", file=sys.stderr)
    raise SystemExit(2) from None

def _allowed_node_labels(ontology: dict[str, Any]) -> frozenset[str]:
    return frozenset(
        str(n["label"])
        for n in ontology.get("node_labels", [])
        if isinstance(n, dict) and n.get("label")
    )


def _apply_edge_tx(tx: Any, row: dict[str, Any], ontology: dict[str, Any]) -> str:
    """Return 'merged', 'missing_endpoint', or 'error'."""
    allowed = _allowed_node_labels(ontology)
    rel_type = str(row["rel_type"])
    fl = str(row["from_label"])
    tl = str(row["to_label"])
    if fl not in allowed or tl not in allowed:
        raise ValueError(f"unsupported label: {fl} -> {tl}")

    fk = str(row["from_key"])
    tk = str(row["to_key"])
    fid = str(row["from_id"])
    tid = str(row["to_id"])

    allowed = kce.allowed_edge_property_keys(ontology)
    eprops = kce.edge_properties_for_neo4j(row, allowed)

    q = f"""
    MATCH (a:{fl} {{{fk}: $fid}})
    MATCH (b:{tl} {{{tk}: $tid}})
    MERGE (a)-[r:{rel_type}]->(b)
    SET r += $eprops
    RETURN 1 AS ok
    """
    result = tx.run(q, fid=fid, tid=tid, eprops=eprops)
    rec = result.single()
    result.consume()
    return "merged" if rec is not None else "missing_endpoint"


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--edges-jsonl", type=Path, required=True)
    p.add_argument(
        "--ontology",
        type=Path,
        default=_REPO / "knowledge_graph" / "ontology_v1.json",
    )
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--warn-miss", action="store_true")
    p.add_argument(
        "--strict-lex-overrides",
        action="store_true",
        help="For OVERRIDES/MODIFIES/SUPERSEDES rows, require source_note and review_status",
    )
    p.add_argument("--limit", type=int, default=None)
    args = p.parse_args()

    if not args.edges_jsonl.is_file():
        print(f"not found: {args.edges_jsonl}", file=sys.stderr)
        return 2

    ontology = kol.load_ontology(args.ontology)
    oerr = kol.validate_ontology(ontology, path=args.ontology)
    if oerr:
        for e in oerr:
            print(e, file=sys.stderr)
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
    miss = 0
    n = 0
    try:
        with args.edges_jsonl.open(encoding="utf-8") as f:
            for line_no, line in enumerate(f, start=1):
                line = line.strip()
                if not line:
                    continue
                row = json.loads(line)
                errs = kce.validate_edge_row(row, ontology, line_no=line_no)
                errs.extend(
                    kov.validate_lex_override_row(
                        row, strict=args.strict_lex_overrides, line_no=line_no
                    )
                )
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
                        # Default arg binds current ``row`` per iteration (closure-safe).
                        status = session.execute_write(
                            lambda tx, r=row: _apply_edge_tx(tx, r, ontology)
                        )
                    if status == "missing_endpoint":
                        miss += 1
                        if args.warn_miss:
                            print(
                                f"line {line_no}: missing endpoint(s) for "
                                f"{row['from_label']}({row['from_id']!r}) -> "
                                f"{row['to_label']}({row['to_id']!r})",
                                file=sys.stderr,
                            )
                    ok += 1

                n += 1
                if args.limit is not None and n >= args.limit:
                    break
    finally:
        if driver is not None:
            driver.close()

    mode = "dry-run" if args.dry_run else "loaded"
    print(f"{mode}: {ok} edge row(s) processed OK schema, {bad} invalid, {miss} missing endpoint(s)")
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
