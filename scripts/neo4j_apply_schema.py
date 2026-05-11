#!/usr/bin/env python3
"""Apply knowledge_graph/neo4j/*.cypher constraints and indexes (Neo4j 5+).

Requires: pip install -r knowledge_graph/requirements-neo4j.txt
Env: NEO4J_URI (default neo4j://127.0.0.1:7687), NEO4J_USER, NEO4J_PASSWORD
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parent
_REPO = _SCRIPTS.parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from neo4j_cypher_split import statements_from_cypher

try:
    from neo4j import GraphDatabase
except ImportError:
    print("Install neo4j driver: pip install -r knowledge_graph/requirements-neo4j.txt", file=sys.stderr)
    raise SystemExit(2) from None


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--schema-dir",
        type=Path,
        default=_REPO / "knowledge_graph" / "neo4j",
        help="Directory containing 00_ / 01_ / 02_ cypher schema files",
    )
    p.add_argument(
        "--constraints-only",
        action="store_true",
        help="Run only 00_constraints.cypher",
    )
    args = p.parse_args()

    uri = os.environ.get("NEO4J_URI", "neo4j://127.0.0.1:7687")
    user = os.environ.get("NEO4J_USER", "neo4j")
    password = os.environ.get("NEO4J_PASSWORD", "")
    if not password:
        print("NEO4J_PASSWORD is not set", file=sys.stderr)
        return 2

    files = [args.schema_dir / "00_constraints.cypher"]
    if not args.constraints_only:
        files.append(args.schema_dir / "01_range_indexes.cypher")
        files.append(args.schema_dir / "02_lex_indexes.cypher")
        files.append(args.schema_dir / "03_consolidated_view_indexes.cypher")

    for fp in files:
        if not fp.is_file():
            print(f"missing: {fp}", file=sys.stderr)
            return 2

    driver = GraphDatabase.driver(uri, auth=(user, password))
    try:
        for fp in files:
            stmts = statements_from_cypher(fp.read_text(encoding="utf-8"))
            with driver.session() as session:
                for stmt in stmts:
                    session.run(stmt)
            print(f"applied {len(stmts)} statement(s) from {fp.name}")
    finally:
        driver.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
