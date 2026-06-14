"""Tests for Phase 3 Step 6 bundle node ordering (no Neo4j)."""

from __future__ import annotations

import importlib.util
from pathlib import Path

_ROOT = Path(__file__).resolve().parent

_spec = importlib.util.spec_from_file_location("kg_etl_lib", _ROOT / "kg_etl_lib.py")
_mod = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
_spec.loader.exec_module(_mod)


def test_bundle_nodes_merge_order_instruments_before_chunks() -> None:
    nodes = [
        {"labels": ["TextChunk"], "id_property": "chunk_id", "id_value": "c1", "properties": {}},
        {"labels": ["LawInstrument"], "id_property": "source_doc_id", "id_value": "d1", "properties": {}},
        {"labels": ["Section"], "id_property": "section_uid", "id_value": "s1", "properties": {}},
    ]
    ordered = _mod.bundle_nodes_merge_order(nodes)
    primaries = [n["labels"][0] for n in ordered]
    assert primaries == ["LawInstrument", "Section", "TextChunk"]
