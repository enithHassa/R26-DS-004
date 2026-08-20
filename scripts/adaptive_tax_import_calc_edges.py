#!/usr/bin/env python3
"""Phase 5.10 — build calculation_edges_full.jsonl from approved harvests + seed.

Calculator-first: this is **breadth** for the dissertation appendix, not a Coverage
gate. Executable curated edges keep ``rule_source_id``; bulk MENTIONS are
non-executable and must not change Coverage.

Sources (merged, deduped)::

  1. models/adaptive-tax/ontology/mvp_calc_edges_seed.jsonl
  2. models/adaptive-tax/fixtures/*_harvest_v1.json relationship_hints
  3. Optional corpus MENTIONS (TextChunk -> Concept) until --min-edges

Every emitted edge carries ``rule_source_id`` (bootstrap / harvest / bulk marker).

Example::

  .\\.venv-backend\\Scripts\\python.exe scripts/adaptive_tax_import_calc_edges.py
  .\\.venv-backend\\Scripts\\python.exe scripts/adaptive_tax_import_calc_edges.py --load-neo4j
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

_SCRIPTS = Path(__file__).resolve().parent
_REPO = _SCRIPTS.parent
_ONTO = _REPO / "models" / "adaptive-tax" / "ontology"
_FIXTURES = _REPO / "models" / "adaptive-tax" / "fixtures"
_SEED = _ONTO / "mvp_calc_edges_seed.jsonl"
_OUT = _ONTO / "calculation_edges_full.jsonl"
_BOOTSTRAP = _FIXTURES / "provenance_bootstrap_v1.json"
_CONCEPTS = _ONTO / "concepts_mvp.json"
_CORPUS = _REPO / "data" / "processed" / "adaptive-tax" / "corpus_v1.jsonl"

_BULK_RULE_SOURCE = "bootstrap:bulk_graph_breadth"

# Rel types that can drive / annotate the calculator (not Coverage).
_EXECUTABLE_REL_TYPES = frozenset(
    {
        "DEFINES",
        "COVERS_RELIEF",
        "APPLIES_TO",
        "CONTRIBUTES_TO",
        "DEDUCTED_FROM",
        "LIMITED_BY",
        "GOVERNED_BY",
        "SUPPORTED_BY",
        "CALCULATED_USING",
    }
)


def _edge_key(row: dict[str, Any]) -> tuple[str, ...]:
    return (
        str(row.get("rel_type") or ""),
        str(row.get("from_label") or ""),
        str(row.get("from_id") or ""),
        str(row.get("to_label") or ""),
        str(row.get("to_id") or ""),
    )


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        row = json.loads(line)
        if isinstance(row, dict):
            rows.append(row)
    return rows


def _bootstrap_by_concept() -> dict[str, str]:
    """Map concept_id / alias → bootstrap rule id."""
    doc = json.loads(_BOOTSTRAP.read_text(encoding="utf-8"))
    out: dict[str, str] = {}
    for rule in doc.get("rules") or []:
        rid = str(rule.get("id") or "")
        if not rid:
            continue
        cid = str(rule.get("concept_id") or "")
        if cid:
            out.setdefault(cid, rid)
        for alias in rule.get("aliases") or []:
            out.setdefault(str(alias), rid)
        for hid in rule.get("handler_ids") or []:
            out.setdefault(str(hid), rid)
    return out


def _ensure_rule_source(
    row: dict[str, Any],
    *,
    by_concept: dict[str, str],
    default: str,
) -> dict[str, Any]:
    out = dict(row)
    if out.get("rule_source_id"):
        return out
    # Prefer concept endpoints for lookup.
    for key in ("from_id", "to_id"):
        cid = str(out.get(key) or "")
        if cid in by_concept:
            out["rule_source_id"] = by_concept[cid]
            return out
    out["rule_source_id"] = default
    return out


def _hint_to_edges(
    hint: dict[str, Any],
    *,
    rule_source_id: str,
    source_note: str,
) -> list[dict[str, Any]]:
    """Normalize harvest relationship_hints into curated edge rows."""
    rel = str(
        hint.get("rel_type") or hint.get("type") or ""
    ).strip().upper()
    if not rel:
        return []

    edges: list[dict[str, Any]] = []
    from_concept = str(
        hint.get("from_concept_id") or hint.get("from_concept") or ""
    ).strip()
    to_concept = str(
        hint.get("to_concept_id") or hint.get("to_concept") or ""
    ).strip()
    from_section = str(
        hint.get("from_section_uid") or hint.get("from_section") or ""
    ).strip()
    to_section = str(
        hint.get("to_section_uid") or hint.get("to_section") or ""
    ).strip()

    base = {
        "confidence": float(hint.get("confidence") or 0.9),
        "review_status": "approved_harvest",
        "source_note": (source_note or "harvest relationship_hint")[:240],
        "rule_source_id": rule_source_id,
        "executable": rel in _EXECUTABLE_REL_TYPES,
    }

    if rel in {"CONTRIBUTES_TO", "DEDUCTED_FROM", "LIMITED_BY"} and from_concept and to_concept:
        edges.append(
            {
                **base,
                "rel_type": rel,
                "from_label": "Concept",
                "from_key": "concept_id",
                "from_id": from_concept,
                "to_label": "Concept",
                "to_key": "concept_id",
                "to_id": to_concept,
            }
        )
    elif rel == "GOVERNED_BY" and from_concept and to_section:
        edges.append(
            {
                **base,
                "rel_type": "GOVERNED_BY",
                "from_label": "Concept",
                "from_key": "concept_id",
                "from_id": from_concept,
                "to_label": "Section",
                "to_key": "section_uid",
                "to_id": to_section,
            }
        )
    elif rel == "DEFINES" and from_section and to_concept:
        edges.append(
            {
                **base,
                "rel_type": "DEFINES",
                "from_label": "Section",
                "from_key": "section_uid",
                "from_id": from_section,
                "to_label": "Concept",
                "to_key": "concept_id",
                "to_id": to_concept,
            }
        )
    elif rel == "SUPPORTED_BY" and from_concept and to_section:
        edges.append(
            {
                **base,
                "rel_type": "SUPPORTED_BY",
                "from_label": "Concept",
                "from_key": "concept_id",
                "from_id": from_concept,
                "to_label": "Section",
                "to_key": "section_uid",
                "to_id": to_section,
            }
        )
    elif rel == "CALCULATED_USING" and from_concept and (to_concept or to_section):
        if to_section:
            edges.append(
                {
                    **base,
                    "rel_type": "CALCULATED_USING",
                    "from_label": "Concept",
                    "from_key": "concept_id",
                    "from_id": from_concept,
                    "to_label": "Section",
                    "to_key": "section_uid",
                    "to_id": to_section,
                }
            )
        elif to_concept:
            edges.append(
                {
                    **base,
                    "rel_type": "CALCULATED_USING",
                    "from_label": "Concept",
                    "from_key": "concept_id",
                    "from_id": from_concept,
                    "to_label": "Concept",
                    "to_key": "concept_id",
                    "to_id": to_concept,
                }
            )
    return edges


def _harvest_rule_source_id(rule: dict[str, Any], by_concept: dict[str, str]) -> str:
    cid = str(rule.get("concept_id") or "")
    handler = str(rule.get("engine_handler") or "")
    if cid and cid in by_concept:
        return by_concept[cid]
    if handler and handler in by_concept:
        return by_concept[handler]
    if cid:
        return f"bootstrap:{cid}"
    return _BULK_RULE_SOURCE


def edges_from_harvests(*, by_concept: dict[str, str]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for path in sorted(_FIXTURES.glob("*_harvest_v1.json")):
        doc = json.loads(path.read_text(encoding="utf-8"))
        for rule in doc.get("rules") or []:
            if not isinstance(rule, dict):
                continue
            rid = _harvest_rule_source_id(rule, by_concept)
            note = str(rule.get("source_quote") or path.name)[:240]
            for hint in rule.get("relationship_hints") or []:
                if isinstance(hint, dict):
                    out.extend(
                        _hint_to_edges(hint, rule_source_id=rid, source_note=note)
                    )
            # Always emit GOVERNED_BY / DEFINES when section_uid is known.
            section_key = str(doc.get("section_key") or rule.get("section") or "")
            cid = str(rule.get("concept_id") or "")
            source_doc = str(
                doc.get("source_doc_id")
                or (doc.get("source_doc_ids") or ["ird-ira-2017-base"])[0]
            )
            if cid and section_key and section_key not in {"first_schedule", "personal_relief", "donations", "investment"}:
                sec_uid = f"{source_doc}::sec::section_{section_key}"
                out.extend(
                    _hint_to_edges(
                        {
                            "rel_type": "GOVERNED_BY",
                            "from_concept_id": cid,
                            "to_section_uid": sec_uid,
                        },
                        rule_source_id=rid,
                        source_note=note,
                    )
                )
                out.extend(
                    _hint_to_edges(
                        {
                            "rel_type": "DEFINES",
                            "from_section_uid": sec_uid,
                            "to_concept_id": cid,
                        },
                        rule_source_id=rid,
                        source_note=note,
                    )
                )
            elif cid and section_key == "first_schedule":
                sec_uid = f"{source_doc}::sec::first_schedule"
                out.extend(
                    _hint_to_edges(
                        {
                            "rel_type": "GOVERNED_BY",
                            "from_concept_id": cid,
                            "to_section_uid": sec_uid,
                        },
                        rule_source_id=rid,
                        source_note=note,
                    )
                )
    return out


def edges_from_mentions(
    *,
    by_concept: dict[str, str],
    corpus_path: Path,
    limit: int,
) -> list[dict[str, Any]]:
    if limit <= 0 or not corpus_path.is_file():
        return []
    if str(_SCRIPTS) not in sys.path:
        sys.path.insert(0, str(_SCRIPTS))
    import kg_edges_heuristic_lib as heu

    concepts = heu.load_concepts_json(_CONCEPTS)
    out: list[dict[str, Any]] = []
    with corpus_path.open(encoding="utf-8") as fh:
        for line in fh:
            if len(out) >= limit:
                break
            line = line.strip()
            if not line:
                continue
            chunk = json.loads(line)
            # Prefer Act / amendment chunks; skip Master PDF if tagged.
            doc_id = str(chunk.get("source_doc_id") or "")
            if "calc-ontology" in doc_id or "master" in doc_id.lower():
                continue
            for edge in heu.suggest_mentions_edges(chunk, concepts, base_confidence=0.45):
                cid = str(edge.get("to_id") or "")
                rid = by_concept.get(cid, _BULK_RULE_SOURCE)
                edge = {
                    **edge,
                    "rule_source_id": rid,
                    "review_status": "bulk_mentions",
                    "executable": False,
                    "source_note": (
                        f"Phase 5.10 bulk MENTIONS from {doc_id or 'corpus'} "
                        "(non-executable; does not affect Coverage)"
                    )[:240],
                }
                out.append(edge)
                if len(out) >= limit:
                    break
    return out


def build_edges(
    *,
    min_edges: int,
    with_mentions: bool,
    corpus_path: Path,
) -> list[dict[str, Any]]:
    by_concept = _bootstrap_by_concept()
    merged: dict[tuple[str, ...], dict[str, Any]] = {}

    def _add(row: dict[str, Any]) -> None:
        ensured = _ensure_rule_source(
            row, by_concept=by_concept, default=_BULK_RULE_SOURCE
        )
        # Mark executable curated rows.
        rel = str(ensured.get("rel_type") or "")
        if "executable" not in ensured:
            ensured["executable"] = rel in _EXECUTABLE_REL_TYPES and rel != "MENTIONS"
        key = _edge_key(ensured)
        if not all(key):
            return
        # Prefer higher-confidence / act_verified over bulk when colliding.
        prev = merged.get(key)
        if prev is None:
            merged[key] = ensured
            return
        prev_conf = float(prev.get("confidence") or 0)
        new_conf = float(ensured.get("confidence") or 0)
        prev_status = str(prev.get("review_status") or "")
        new_status = str(ensured.get("review_status") or "")
        prefer_new = new_conf > prev_conf or (
            "bulk" in prev_status and "bulk" not in new_status
        )
        if prefer_new:
            merged[key] = ensured

    for row in _load_jsonl(_SEED):
        _add({**row, "review_status": row.get("review_status") or "manual_seed"})

    for row in edges_from_harvests(by_concept=by_concept):
        _add(row)

    rows = list(merged.values())
    if with_mentions and len(rows) < min_edges:
        need = min_edges - len(rows)
        # Generate extra Mentions with headroom for dedupe.
        for row in edges_from_mentions(
            by_concept=by_concept,
            corpus_path=corpus_path,
            limit=max(need * 3, need + 50),
        ):
            _add(row)
            if len(merged) >= min_edges:
                break
        rows = list(merged.values())

    # Stable order: executable curated first, then bulk.
    def _sort_key(r: dict[str, Any]) -> tuple[Any, ...]:
        exe = 0 if r.get("executable") else 1
        return (exe, str(r.get("rel_type")), str(r.get("from_id")), str(r.get("to_id")))

    rows.sort(key=_sort_key)
    return rows


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    """Write curated edge rows; drop non-ontology keys (e.g. executable)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        for row in rows:
            clean = {k: v for k, v in row.items() if k != "executable"}
            fh.write(json.dumps(clean, ensure_ascii=False) + "\n")


def ensure_bulk_bootstrap() -> None:
    """Add a non-executable bootstrap marker used by bulk MENTIONS."""
    doc = json.loads(_BOOTSTRAP.read_text(encoding="utf-8"))
    rules = list(doc.get("rules") or [])
    if any(str(r.get("id")) == _BULK_RULE_SOURCE for r in rules):
        return
    rules.append(
        {
            "id": _BULK_RULE_SOURCE,
            "handler_ids": [],
            "aliases": ["bulk_graph_breadth", "bulk_mentions"],
            "assessment_years": ["2024_25", "2025_26"],
            "section": "corpus",
            "section_uid": "ird-ira-2017-base::sec::section_2",
            "source_doc_id": "ird-ira-2017-base",
            "concept_id": "assessable_income",
            "kind": "source_doc",
            "executable": False,
            "source_quote": (
                "2. (1) Income tax shall be payable for each year of assessment by – "
                "(a) a person who has taxable income for that year; or (b) a person who "
                "receives a final withholding payment during that year. "
                "(Phase 5.10 bulk graph breadth marker — non-executable.)"
            ),
        }
    )
    doc["rules"] = rules
    _BOOTSTRAP.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def load_neo4j(edges_path: Path) -> int:
    env = os.environ.copy()
    cmd = [
        sys.executable,
        str(_SCRIPTS / "neo4j_load_calc_ontology_nodes.py"),
    ]
    proc = subprocess.run(cmd, cwd=str(_REPO), env=env, check=False)
    if proc.returncode != 0:
        return proc.returncode
    cmd = [
        sys.executable,
        str(_SCRIPTS / "neo4j_load_curated_edges.py"),
        "--edges-jsonl",
        str(edges_path),
        "--warn-miss",
    ]
    return subprocess.run(cmd, cwd=str(_REPO), env=env, check=False).returncode


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--out", type=Path, default=_OUT)
    p.add_argument("--min-edges", type=int, default=300)
    p.add_argument(
        "--with-mentions",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Fill to --min-edges with corpus MENTIONS (non-executable)",
    )
    p.add_argument("--corpus-jsonl", type=Path, default=_CORPUS)
    p.add_argument(
        "--load-neo4j",
        action="store_true",
        help="After write, MERGE ontology nodes + load edges into Neo4j",
    )
    p.add_argument(
        "--ensure-bootstrap",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Ensure bootstrap:bulk_graph_breadth exists",
    )
    args = p.parse_args(argv)

    if args.ensure_bootstrap:
        ensure_bulk_bootstrap()

    rows = build_edges(
        min_edges=args.min_edges,
        with_mentions=args.with_mentions,
        corpus_path=args.corpus_jsonl,
    )
    write_jsonl(args.out, rows)

    n_exec = sum(1 for r in rows if r.get("executable"))
    n_mentions = sum(1 for r in rows if r.get("rel_type") == "MENTIONS")
    missing_rs = sum(1 for r in rows if not r.get("rule_source_id"))
    print(
        f"wrote {len(rows)} edges -> {args.out} "
        f"(executable~={n_exec}, MENTIONS={n_mentions}, missing_rule_source_id={missing_rs})"
    )
    if len(rows) < args.min_edges:
        print(
            f"[FAIL] only {len(rows)} edges; need >= {args.min_edges}. "
            "Check corpus path or lower --min-edges.",
            file=sys.stderr,
        )
        return 1
    if missing_rs:
        print("[FAIL] some edges lack rule_source_id", file=sys.stderr)
        return 1

    if args.load_neo4j:
        code = load_neo4j(args.out)
        if code != 0:
            print(f"[FAIL] Neo4j load exit={code}", file=sys.stderr)
            return code
        print("[ok] Neo4j ontology nodes + curated edges loaded")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
