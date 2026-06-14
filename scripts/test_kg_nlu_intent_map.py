"""Tests for Phase 3 Step 12 NLU intent → graph entry map."""

from __future__ import annotations

import importlib.util
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
_MAP = _REPO / "knowledge_graph" / "nlu_intent_graph_map_v1.json"
_ROOT = Path(__file__).resolve().parent

_spec = importlib.util.spec_from_file_location("kg_nlu_intent_map_lib", _ROOT / "kg_nlu_intent_map_lib.py")
_mod = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
_spec.loader.exec_module(_mod)


def test_default_map_validates() -> None:
    doc = _mod.load_intent_map(_MAP)
    errs = _mod.validate_intent_map(doc, map_path=_MAP)
    assert not errs, errs


def test_intent_lookup_and_default() -> None:
    doc = _mod.load_intent_map(_MAP)
    assert _mod.intent_row_for_intent(doc, "personal_relief") is not None
    assert _mod.intent_row_for_intent(doc, "nonexistent_intent") == _mod.intent_row_for_intent(
        doc, "_default"
    )


def test_validate_template_params() -> None:
    doc = _mod.load_intent_map(_MAP)
    bad = dict(doc)
    rows = list(doc["intents"])
    pr = next(r for r in rows if r["nlu_intent"] == "personal_relief")
    rows[rows.index(pr)] = {
        **pr,
        "entry": {
            **pr["entry"],
            "cypher_template": "MATCH (n:Relief {relief_id: $relief_id, extra: $x}) RETURN n",
        },
    }
    bad["intents"] = rows
    errs = _mod.validate_intent_map(bad)
    assert errs and any("$x" in e or "omit" in e for e in errs)
