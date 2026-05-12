"""Tests for Phase 3 Step 8 Lex Specialis metadata."""

from __future__ import annotations

import importlib.util
from pathlib import Path

_ROOT = Path(__file__).resolve().parent
_REPO = Path(__file__).resolve().parents[1]
_LEX = _REPO / "knowledge_graph" / "lex_specialis_v1.json"

_spec = importlib.util.spec_from_file_location("kg_lex_specialis_lib", _ROOT / "kg_lex_specialis_lib.py")
_mod = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
_spec.loader.exec_module(_mod)


def test_infer_tier_a_act_is_statute() -> None:
    norm = {
        "tier": "A",
        "instrument_type": "act",
        "doc_type": "statute",
        "is_draft": False,
        "effective_start_date": "2018-01-01",
        "authority_weight": "1.0",
    }
    assert _mod.infer_authority_class(norm) == "statute"
    f = _mod.lex_fields_for(norm, role="LawInstrument")
    assert f["authority_class"] == "statute"
    assert f["specificity_rank"] == 85
    assert f["authority_weight_numeric"] == 1.0


def test_draft_guide_weak() -> None:
    norm = {
        "tier": "B",
        "instrument_type": "guide",
        "doc_type": "guide",
        "is_draft": True,
        "authority_weight": "",
    }
    assert _mod.infer_authority_class(norm) == "draft_guide"
    f = _mod.lex_fields_for(norm, role="LawInstrument")
    assert f["specificity_rank"] == 28
    assert f["authority_weight_numeric"] == 0.3


def test_section_gets_specificity_bonus() -> None:
    norm = {
        "tier": "A",
        "instrument_type": "act",
        "doc_type": "statute",
        "is_draft": False,
        "effective_start_date": "2020-01-01",
        "authority_weight": "",
    }
    li = _mod.lex_fields_for(norm, role="LawInstrument")
    sec = _mod.lex_fields_for(norm, role="Section")
    assert sec["specificity_rank"] == li["specificity_rank"] + 5


def test_precedence_index() -> None:
    assert _mod.authority_precedence_index("amendment") > _mod.authority_precedence_index("draft_guide")


def test_lex_spec_loads() -> None:
    doc = _mod.load_lex_spec(_LEX)
    assert doc["lex_version"]
    assert "classes" in doc
