#!/usr/bin/env python3
"""Phase 3 Step 6 — load corpus_v1 JSONL into Neo4j in safe node order.

Per row: MERGE LawInstrument → Section (if any) → TextChunk → PART_OF / HAS_CHUNK.
Requires: pip install -r knowledge_graph/requirements-neo4j.txt
Env: NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD (same as neo4j_apply_schema.py)
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

import ird_corpus_lib as icl
import kg_etl_lib as kel

try:
    from neo4j import GraphDatabase
except ImportError:
    print("Install neo4j driver: pip install -r knowledge_graph/requirements-neo4j.txt", file=sys.stderr)
    raise SystemExit(2) from None

_ALLOWED_REL_TYPES = frozenset({"PART_OF", "HAS_CHUNK"})
_ALLOWED_NODE_LABELS = frozenset({"LawInstrument", "Section", "TextChunk"})


def _flatten_props(props: dict[str, Any]) -> dict[str, Any]:
    """Omit None so we do not rely on Neo4j null semantics for optional fields."""
    return {k: v for k, v in props.items() if v is not None}


def _merge_law_instrument(tx: Any, spec: dict[str, Any]) -> None:
    p = _flatten_props(spec["properties"])
    sid = p.get("source_doc_id")
    if not sid:
        raise ValueError("LawInstrument missing source_doc_id")
    tx.run(
        """
        MERGE (n:LawInstrument {source_doc_id: $source_doc_id})
        SET n += $props
        """,
        source_doc_id=sid,
        props=p,
    )


def _merge_section(tx: Any, spec: dict[str, Any]) -> None:
    p = _flatten_props(spec["properties"])
    uid = p.get("section_uid")
    if not uid:
        raise ValueError("Section missing section_uid")
    tx.run(
        """
        MERGE (n:Section {section_uid: $section_uid})
        SET n += $props
        """,
        section_uid=uid,
        props=p,
    )


def _merge_text_chunk(tx: Any, spec: dict[str, Any]) -> None:
    p = _flatten_props(spec["properties"])
    cid = p.get("chunk_id")
    if not cid:
        raise ValueError("TextChunk missing chunk_id")
    tx.run(
        """
        MERGE (n:TextChunk {chunk_id: $chunk_id})
        SET n += $props
        """,
        chunk_id=cid,
        props=p,
    )


def _merge_relationship(tx: Any, rel: dict[str, Any]) -> None:
    rtype = rel["type"]
    if rtype not in _ALLOWED_REL_TYPES:
        raise ValueError(f"unsupported relationship type for pilot load: {rtype}")
    fa = rel["from"]
    ta = rel["to"]
    fp, fv = fa["id_property"], fa["id_value"]
    tp, tv = ta["id_property"], ta["id_value"]
    fl = fa["label"]
    tl = ta["label"]
    if fl not in _ALLOWED_NODE_LABELS or tl not in _ALLOWED_NODE_LABELS:
        raise ValueError(f"unsupported relationship endpoint labels: {fl} -> {tl}")

    q = f"""
    MATCH (a:{fl} {{{fp}: $from_id}})
    MATCH (b:{tl} {{{tp}: $to_id}})
    MERGE (a)-[r:{rtype}]->(b)
    """
    tx.run(q, from_id=fv, to_id=tv)


def apply_bundle_tx(tx: Any, bundle: dict[str, Any]) -> None:
    """Merge one Step 4 bundle inside a Neo4j transaction."""
    for node in kel.bundle_nodes_merge_order(bundle["nodes"]):
        labels = node.get("labels") or []
        primary = labels[0] if labels else ""
        if primary == "LawInstrument":
            _merge_law_instrument(tx, node)
        elif primary == "Section":
            _merge_section(tx, node)
        elif primary == "TextChunk":
            _merge_text_chunk(tx, node)
        else:
            raise ValueError(f"unsupported node label in pilot bundle: {primary}")

    for rel in bundle["relationships"]:
        _merge_relationship(tx, rel)


def load_jsonl(
    path: Path,
    *,
    driver: Any,
    strict_doc_meta: bool,
    include_text: bool,
    text_max_chars: int | None,
    limit: int | None,
    dry_run: bool,
) -> tuple[int, int]:
    """Returns (rows_ok, rows_skipped_errors)."""
    ok = 0
    bad = 0
    n = 0
    with path.open(encoding="utf-8") as f:
        for line_no, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            errs = icl.validate_kg_chunk_metadata(
                row, line_no=line_no, strict_doc_meta=strict_doc_meta
            )
            if errs:
                bad += 1
                for e in errs:
                    print(e, file=sys.stderr)
                continue
            try:
                bundle = kel.etl_bundle_from_chunk_row(
                    row,
                    include_text=include_text,
                    text_max_chars=text_max_chars,
                )
            except ValueError as e:
                bad += 1
                print(f"line {line_no}: {e}", file=sys.stderr)
                continue

            if dry_run:
                ok += 1
            else:
                with driver.session() as session:
                    session.execute_write(apply_bundle_tx, bundle)
                ok += 1

            n += 1
            if limit is not None and n >= limit:
                break
    return ok, bad


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--corpus-jsonl", type=Path, required=True)
    p.add_argument("--strict-doc-meta", action="store_true")
    p.add_argument("--no-text", action="store_true", help="Omit TextChunk.text property")
    p.add_argument("--text-max-chars", type=int, default=None)
    p.add_argument("--limit", type=int, default=None, help="Max non-empty JSONL rows to process")
    p.add_argument("--dry-run", action="store_true", help="Validate + build bundles only; no Neo4j writes")
    args = p.parse_args()

    if not args.corpus_jsonl.is_file():
        print(f"not found: {args.corpus_jsonl}", file=sys.stderr)
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

    try:
        ok, bad = load_jsonl(
            args.corpus_jsonl,
            driver=driver,
            strict_doc_meta=args.strict_doc_meta,
            include_text=not args.no_text,
            text_max_chars=args.text_max_chars,
            limit=args.limit,
            dry_run=args.dry_run,
        )
        mode = "dry-run" if args.dry_run else "loaded"
        print(f"{mode}: {ok} row(s) OK, {bad} row(s) skipped/errors")
        return 1 if bad else 0
    finally:
        if driver is not None:
            driver.close()


if __name__ == "__main__":
    raise SystemExit(main())
