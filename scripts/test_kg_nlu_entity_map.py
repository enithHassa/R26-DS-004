"""Tests for Phase 3 Step 11 NLU entity → graph map."""

from __future__ import annotations

import importlib.util
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
_MAP = _REPO / "knowledge_graph" / "nlu_entity_graph_map_v1.json"
_ROOT = Path(__file__).resolve().parent

_spec = importlib.util.spec_from_file_location("kg_nlu_entity_map_lib", _ROOT / "kg_nlu_entity_map_lib.py")
_mod = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
_spec.loader.exec_module(_mod)


def test_default_map_validates() -> None:
    doc = _mod.load_entity_map(_MAP)
    errs = _mod.validate_entity_map(doc, map_path=_MAP)
    assert not errs, errs


def test_entity_row_lookup() -> None:
    doc = _mod.load_entity_map(_MAP)
    row = _mod.entity_row_for_type(doc, "relief_type")
    assert row is not None
    assert row["target_node_label"] == "Relief"


def test_validate_catches_bad_target_label() -> None:
    doc = _mod.load_entity_map(_MAP)
    bad = dict(doc)
    rows = list(doc["entity_types"])
    rows[0] = {**rows[0], "target_node_label": "NotInOntology"}
    bad["entity_types"] = rows
    errs = _mod.validate_entity_map(bad)
    assert errs and any("not in ontology" in e for e in errs)
