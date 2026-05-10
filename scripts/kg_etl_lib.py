"""Phase 3 Step 4 — build idempotent MERGE bundles: corpus chunk row → graph nodes/edges (pilot).

See knowledge_graph/etl_chunk_to_graph_v1.json for the contract.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Any

_SCRIPTS = Path(__file__).resolve().parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

import ird_corpus_lib as icl  # noqa: E402
import kg_lex_specialis_lib as lex  # noqa: E402

_SLUG_RE = re.compile(r"[^a-zA-Z0-9]+")

ETL_BUNDLE_VERSION = "1.1.0"

# Neo4j load order (Phase 3 Step 6): instruments → sections → chunks → edges.
_NODE_LOAD_ORDER: dict[str, int] = {
    "LawInstrument": 0,
    "Section": 1,
    "TextChunk": 2,
}


def bundle_nodes_merge_order(nodes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Sort pilot bundle nodes for safe MERGE (ontology Step 6)."""

    def _rank(n: dict[str, Any]) -> int:
        labels = n.get("labels") or []
        primary = labels[0] if labels else ""
        return _NODE_LOAD_ORDER.get(primary, 99)

    return sorted(nodes, key=_rank)


def make_section_uid(source_doc_id: str, section_label: str | None) -> str | None:
    """Stable Section key: ``{source_doc_id}::sec::{slug}`` or None if no label."""
    if not source_doc_id or not str(source_doc_id).strip():
        return None
    if section_label is None or not str(section_label).strip():
        return None
    slug = _SLUG_RE.sub("_", section_label.strip()).strip("_").lower()
    if not slug:
        return None
    return f"{source_doc_id.strip()}::sec::{slug}"


def _law_instrument_props(norm: dict[str, Any]) -> dict[str, Any]:
    base: dict[str, Any] = {
        "source_doc_id": norm.get("source_doc_id"),
        "title": norm.get("title") or "",
        "instrument_type": norm.get("instrument_type") or "",
        "doc_type": norm.get("doc_type") or "",
        "tier": norm.get("tier") or "",
        "authority_weight": norm.get("authority_weight") or "",
        "is_draft": bool(norm.get("is_draft", False)),
        "publication_date": norm.get("publication_date") or "",
        "effective_start_date": norm.get("effective_start_date") or "",
        "effective_end_date": norm.get("effective_end_date") or "",
        "version_label": norm.get("version_label") or "",
        "source_url": norm.get("source_url") or "",
        "language": norm.get("language") or "en",
    }
    base.update(lex.lex_fields_for(norm, role="LawInstrument"))
    return base


def _text_chunk_props(norm: dict[str, Any], *, include_text: bool, text_max_chars: int | None) -> dict[str, Any]:
    text = norm.get("text")
    if include_text and isinstance(text, str) and text_max_chars is not None and len(text) > text_max_chars:
        text = text[:text_max_chars]
    props: dict[str, Any] = {
        "chunk_id": norm.get("chunk_id"),
        "source_doc_id": norm.get("source_doc_id"),
        "corpus_version": norm.get("corpus_version") or icl.CORPUS_VERSION,
        "content_kind": norm.get("content_kind") or "text",
        "page": norm.get("page"),
        "chunk_index": norm.get("chunk_index"),
        "tier": norm.get("tier") or "",
        "instrument_type": norm.get("instrument_type") or "",
        "layout_hint": norm.get("layout_hint"),
        "effective_from": norm.get("effective_from"),
        "section_label": norm.get("section_label"),
    }
    if include_text:
        props["text"] = text if isinstance(text, str) else ""
    props.update(lex.lex_fields_for(norm, role="TextChunk"))
    return props


def _section_props(norm: dict[str, Any], section_uid: str) -> dict[str, Any]:
    base: dict[str, Any] = {
        "section_uid": section_uid,
        "source_doc_id": norm.get("source_doc_id"),
        "section_label": norm.get("section_label"),
        "effective_start_date": norm.get("effective_start_date") or "",
        "effective_end_date": norm.get("effective_end_date") or "",
        "heading_text": None,
    }
    base.update(lex.lex_fields_for(norm, role="Section"))
    return base


def _node(labels: list[str], id_property: str, id_value: str, properties: dict[str, Any]) -> dict[str, Any]:
    return {
        "labels": labels,
        "id_property": id_property,
        "id_value": id_value,
        "properties": properties,
    }


def _rel(
    rel_type: str,
    from_label: str,
    from_prop: str,
    from_id: str,
    to_label: str,
    to_prop: str,
    to_id: str,
    properties: dict[str, Any] | None = None,
) -> dict[str, Any]:
    r: dict[str, Any] = {
        "type": rel_type,
        "from": {"label": from_label, "id_property": from_prop, "id_value": from_id},
        "to": {"label": to_label, "id_property": to_prop, "id_value": to_id},
    }
    if properties:
        r["properties"] = properties
    return r


def etl_bundle_from_chunk_row(
    record: dict[str, Any],
    *,
    include_text: bool = True,
    text_max_chars: int | None = None,
) -> dict[str, Any]:
    """Return a serializable MERGE plan for one corpus JSONL object.

    Guarantees:
    - Exactly one ``TextChunk`` node (``chunk_id``).
    - Exactly one ``LawInstrument`` node for ``source_doc_id``.
    - At least one ``HAS_CHUNK`` into the TextChunk (from Section or LawInstrument).
    - When ``section_uid`` can be built, adds ``Section`` + ``PART_OF`` + ``HAS_CHUNK`` from Section;
      otherwise ``HAS_CHUNK`` from LawInstrument only.
    """
    norm = icl.normalize_chunk_for_kg(dict(record))
    chunk_id = norm.get("chunk_id")
    source_doc_id = norm.get("source_doc_id")
    if not chunk_id or not source_doc_id:
        raise ValueError("record must have chunk_id and source_doc_id (normalize + validate before ETL)")

    nodes: list[dict[str, Any]] = []
    rels: list[dict[str, Any]] = []

    li_props = _law_instrument_props(norm)
    nodes.append(_node(["LawInstrument"], "source_doc_id", str(source_doc_id), li_props))

    tc_props = _text_chunk_props(norm, include_text=include_text, text_max_chars=text_max_chars)
    nodes.append(_node(["TextChunk"], "chunk_id", str(chunk_id), tc_props))

    section_uid = make_section_uid(str(source_doc_id), norm.get("section_label"))

    if section_uid:
        nodes.append(_node(["Section"], "section_uid", section_uid, _section_props(norm, section_uid)))
        rels.append(_rel("PART_OF", "Section", "section_uid", section_uid, "LawInstrument", "source_doc_id", str(source_doc_id)))
        rels.append(_rel("HAS_CHUNK", "Section", "section_uid", section_uid, "TextChunk", "chunk_id", str(chunk_id)))
    else:
        rels.append(
            _rel("HAS_CHUNK", "LawInstrument", "source_doc_id", str(source_doc_id), "TextChunk", "chunk_id", str(chunk_id))
        )

    return {
        "etl_bundle_version": ETL_BUNDLE_VERSION,
        "nodes": nodes,
        "relationships": rels,
    }


def assert_bundle_has_text_chunk(bundle: dict[str, Any]) -> None:
    """Debug helper: raise if Proof Map anchor is missing."""
    ids = {n["id_value"] for n in bundle.get("nodes", []) if "TextChunk" in n.get("labels", [])}
    if not ids:
        raise ValueError("bundle has no TextChunk node")
    to_chunks = [r for r in bundle.get("relationships", []) if r["to"]["label"] == "TextChunk"]
    if not to_chunks:
        raise ValueError("bundle has no relationship targeting TextChunk")
