#!/usr/bin/env python3
"""MERGE Adaptive Tax MVP calc ontology nodes into Neo4j (Concept / Relief / RateBand / Section stubs).

Reads:
  models/adaptive-tax/ontology/concepts_mvp.json
  models/adaptive-tax/ontology/relief_caps.json
  models/adaptive-tax/ontology/rate_bands_2024_25.json

Also MERGEs Section stubs + PART_OF LawInstrument so curated edges have endpoints
(corpus ETL may not have created section_52 / first_schedule).

Env: NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD (same as neo4j_apply_schema.py).
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
_ONTO = _REPO / "models" / "adaptive-tax" / "ontology"

try:
    from neo4j import GraphDatabase
except ImportError:
    print("Install neo4j driver: pip install -r knowledge_graph/requirements-neo4j.txt", file=sys.stderr)
    raise SystemExit(2) from None


def _load_json(path: Path) -> dict[str, Any]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise SystemExit(f"expected JSON object: {path}")
    return raw


def _flatten(props: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for k, v in props.items():
        if v is None:
            continue
        if isinstance(v, (str, int, float, bool)):
            out[k] = v
        elif isinstance(v, list) and all(isinstance(x, str) for x in v):
            out[k] = v
        else:
            out[k] = json.dumps(v, ensure_ascii=False)
    return out


def _merge_concept(tx: Any, row: dict[str, Any]) -> None:
    cid = str(row["concept_id"])
    props = _flatten(
        {
            "concept_id": cid,
            "display_name": row.get("display_name") or cid,
            "aliases": row.get("aliases") or [],
            "review_status": "manual_seed",
        }
    )
    tx.run(
        """
        MERGE (n:Concept {concept_id: $concept_id})
        SET n += $props
        """,
        concept_id=cid,
        props=props,
    )


def _merge_relief(tx: Any, row: dict[str, Any]) -> None:
    rid = str(row["relief_id"])
    props = _flatten(
        {
            "relief_id": rid,
            "display_name": row.get("display_name") or rid,
            "statutory_label": row.get("statutory_label") or "",
            "concept_id": row.get("concept_id") or "",
            "section_ref": row.get("section_ref") or "",
            "section_uid": row.get("section_uid") or "",
            "cap_amount": row.get("cap_amount"),
            "cap_pct_of_assessable": row.get("cap_pct_of_assessable"),
            "currency": row.get("currency") or "LKR",
            "effective_start_date": row.get("effective_start_date") or "",
            "effective_end_date": row.get("effective_end_date") or "",
            "source_doc_id": row.get("source_doc_id") or "",
            "review_status": row.get("review_status") or "manual_seed",
        }
    )
    tx.run(
        """
        MERGE (n:Relief {relief_id: $relief_id})
        SET n += $props
        """,
        relief_id=rid,
        props=props,
    )


def _merge_rate_band(tx: Any, row: dict[str, Any]) -> None:
    bid = str(row["rate_band_id"])
    props = _flatten(
        {
            "rate_band_id": bid,
            "band_label": row.get("band_label") or bid,
            "band_index": row.get("band_index"),
            "lower": row.get("lower"),
            "upper": row.get("upper"),
            "rate": row.get("rate"),
            "currency": row.get("currency") or "LKR",
            "effective_start_date": row.get("effective_start_date") or "",
            "effective_end_date": row.get("effective_end_date") or "",
            "source_doc_id": row.get("source_doc_id") or "",
            "review_status": row.get("review_status") or "manual_seed",
        }
    )
    tx.run(
        """
        MERGE (n:RateBand {rate_band_id: $rate_band_id})
        SET n += $props
        """,
        rate_band_id=bid,
        props=props,
    )


def _merge_section_stub(tx: Any, row: dict[str, Any]) -> None:
    uid = str(row["section_uid"])
    sid = str(row.get("source_doc_id") or "ird-ira-2017-base")
    props = _flatten(
        {
            "section_uid": uid,
            "section_label": row.get("section_label") or "",
            "source_doc_id": sid,
            "review_status": row.get("review_status") or "manual_seed",
        }
    )
    tx.run(
        """
        MERGE (n:Section {section_uid: $section_uid})
        SET n += $props
        WITH n
        MATCH (l:LawInstrument {source_doc_id: $source_doc_id})
        MERGE (n)-[:PART_OF]->(l)
        """,
        section_uid=uid,
        source_doc_id=sid,
        props=props,
    )


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--concepts-json", type=Path, default=_ONTO / "concepts_mvp.json")
    p.add_argument("--reliefs-json", type=Path, default=_ONTO / "relief_caps.json")
    p.add_argument("--rate-bands-json", type=Path, default=_ONTO / "rate_bands_2024_25.json")
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()

    for path in (args.concepts_json, args.reliefs_json, args.rate_bands_json):
        if not path.is_file():
            print(f"not found: {path}", file=sys.stderr)
            return 2

    concepts_doc = _load_json(args.concepts_json)
    reliefs_doc = _load_json(args.reliefs_json)
    bands_doc = _load_json(args.rate_bands_json)

    concepts = list(concepts_doc.get("concepts") or [])
    sections = list(concepts_doc.get("sections") or [])
    reliefs = list(reliefs_doc.get("reliefs") or [])
    bands = list(bands_doc.get("bands") or [])

    print(
        f"will MERGE concepts={len(concepts)} sections={len(sections)} "
        f"reliefs={len(reliefs)} rate_bands={len(bands)}"
    )
    if args.dry_run:
        return 0

    uri = os.environ.get("NEO4J_URI", "neo4j://127.0.0.1:7687")
    user = os.environ.get("NEO4J_USER", "neo4j")
    password = os.environ.get("NEO4J_PASSWORD", "")
    if not password:
        print("NEO4J_PASSWORD is not set", file=sys.stderr)
        return 2

    driver = GraphDatabase.driver(uri, auth=(user, password))
    try:
        with driver.session() as session:
            for row in concepts:
                session.execute_write(_merge_concept, row)
            for row in sections:
                session.execute_write(_merge_section_stub, row)
            for row in reliefs:
                session.execute_write(_merge_relief, row)
            for row in bands:
                session.execute_write(_merge_rate_band, row)
    finally:
        driver.close()

    print("calc ontology nodes MERGED OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
