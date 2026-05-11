"""Tests for Phase 3 Step 7 curated edges + heuristics (no Neo4j)."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
_ONTOLOGY_PATH = _REPO / "knowledge_graph" / "ontology_v1.json"
_ROOT = Path(__file__).resolve().parent


def _load(name: str, fname: str):
    spec = importlib.util.spec_from_file_location(name, _ROOT / fname)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


_kol = _load("kg_ontology_lib", "kg_ontology_lib.py")
_kce = _load("kg_curated_edges_lib", "kg_curated_edges_lib.py")
_heu = _load("kg_edges_heuristic_lib", "kg_edges_heuristic_lib.py")


def test_ontology_helpers() -> None:
    ont = _kol.load_ontology(_ONTOLOGY_PATH)
    assert _kol.node_id_property(ont, "TextChunk") == "chunk_id"
    assert _kol.relationship_spec(ont, "MENTIONS") is not None
    assert _kol.relationship_spec(ont, "Nope") is None


def test_validate_edge_row_good_mentions() -> None:
    ont = _kol.load_ontology(_ONTOLOGY_PATH)
    row = {
        "rel_type": "MENTIONS",
        "from_label": "TextChunk",
        "from_key": "chunk_id",
        "from_id": "d::p0001::c0000",
        "to_label": "Concept",
        "to_key": "concept_id",
        "to_id": "c1",
        "confidence": 0.5,
        "review_status": "manual",
    }
    assert not _kce.validate_edge_row(row, ont)


def test_validate_rejects_wrong_from_key() -> None:
    ont = _kol.load_ontology(_ONTOLOGY_PATH)
    row = {
        "rel_type": "MENTIONS",
        "from_label": "TextChunk",
        "from_key": "wrong",
        "from_id": "x",
        "to_label": "Concept",
        "to_key": "concept_id",
        "to_id": "c1",
    }
    errs = _kce.validate_edge_row(row, ont)
    assert errs and any("from_key" in e for e in errs)


def test_validate_rejects_unknown_metadata_key() -> None:
    ont = _kol.load_ontology(_ONTOLOGY_PATH)
    row = {
        "rel_type": "MENTIONS",
        "from_label": "TextChunk",
        "from_key": "chunk_id",
        "from_id": "x",
        "to_label": "Concept",
        "to_key": "concept_id",
        "to_id": "c1",
        "extra_foo": "nope",
    }
    errs = _kce.validate_edge_row(row, ont)
    assert errs and any("extra_foo" in e or "unknown" in e for e in errs)


def test_heuristic_mentions() -> None:
    concepts = [{"concept_id": "relief_personal", "aliases": ["personal relief"]}]
    chunk = {"chunk_id": "t1", "text": "Discuss personal relief for individuals."}
    edges = _heu.suggest_mentions_edges(chunk, concepts)
    assert len(edges) == 1
    assert edges[0]["rel_type"] == "MENTIONS"
    assert edges[0]["to_id"] == "relief_personal"
    assert edges[0]["review_status"] == "auto_alias_match"


def test_load_concepts_json(tmp_path: Path) -> None:
    p = tmp_path / "c.json"
    p.write_text(json.dumps({"concepts": [{"concept_id": "a", "aliases": ["x"]}]}), encoding="utf-8")
    c = _heu.load_concepts_json(p)
    assert len(c) == 1
