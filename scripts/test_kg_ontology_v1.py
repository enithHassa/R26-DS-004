"""Tests for Phase 3 ontology JSON (nodes + relationship types)."""

from __future__ import annotations

import importlib.util
from pathlib import Path

_ROOT = Path(__file__).resolve().parent
_REPO = _ROOT.parent
_ONTOLOGY = _REPO / "knowledge_graph" / "ontology_v1.json"

_spec = importlib.util.spec_from_file_location("kg_ontology_lib", _ROOT / "kg_ontology_lib.py")
_mod = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
_spec.loader.exec_module(_mod)


def test_default_ontology_loads() -> None:
    doc = _mod.load_ontology(_ONTOLOGY)
    assert doc["ontology_version"] == "1.2.0"
    assert doc["phase"] == "3a-step10"
    assert len(doc["relationship_types"]) >= 11
    errs = _mod.validate_ontology(doc, path=_ONTOLOGY)
    assert not errs, errs


def test_validate_catches_duplicate_label() -> None:
    doc = _mod.load_ontology(_ONTOLOGY)
    labels = doc["node_labels"]
    twin = dict(labels[0])
    bad = {**doc, "node_labels": [labels[0], twin]}
    errs = _mod.validate_ontology(bad)
    assert any("duplicate" in e for e in errs)


def test_validate_catches_unknown_rel_endpoint() -> None:
    doc = _mod.load_ontology(_ONTOLOGY)
    rels = list(doc["relationship_types"])
    bad_rel = {**rels[0], "from_labels": ["NotALabel"]}
    bad = {**doc, "relationship_types": [bad_rel]}
    errs = _mod.validate_ontology(bad)
    assert any("unknown node label" in e for e in errs)


def test_validate_catches_bad_rel_type_casing() -> None:
    doc = _mod.load_ontology(_ONTOLOGY)
    rels = list(doc["relationship_types"])
    bad_rel = {**rels[0], "type": "part_of"}
    bad = {**doc, "relationship_types": [bad_rel]}
    errs = _mod.validate_ontology(bad)
    assert any("UPPER_SNAKE" in e for e in errs)
