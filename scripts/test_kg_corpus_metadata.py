"""Tests for Phase 3 Step 3 KG chunk metadata normalization."""

from __future__ import annotations

import importlib.util
from pathlib import Path

_ROOT = Path(__file__).resolve().parent
_REPO = _ROOT.parent

_spec = importlib.util.spec_from_file_location("ird_corpus_lib", _ROOT / "ird_corpus_lib.py")
_mod = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
_spec.loader.exec_module(_mod)


def test_normalize_adds_effective_from_and_section_label() -> None:
    doc_meta = {
        "tier": "A",
        "instrument_type": "act",
        "doc_type": "statute",
        "publication_date": "",
        "effective_start_date": "2018-04-01",
        "effective_end_date": "",
        "version_label": "",
        "source_url": "",
        "title": "",
        "authority_weight": "1.0",
        "is_draft": False,
        "language": "en",
    }
    raw = _mod.build_text_chunk_record(
        source_doc_id="ira2017",
        page=1,
        chunk_index=0,
        page_char_start=0,
        page_char_end=10,
        text="Section 45 defines resident.",
        doc_meta=doc_meta,
    )
    assert "effective_from" not in raw
    norm = _mod.normalize_chunk_for_kg(raw)
    assert norm["effective_from"] == "2018-04-01"
    assert norm["section_label"] == "Section 45"


def test_normalize_section_label_from_breadcrumb() -> None:
    doc_meta = _mod.normalize_doc_meta({"tier": "A", "instrument_type": "act"})
    raw = _mod.build_text_chunk_record(
        source_doc_id="x",
        page=1,
        chunk_index=0,
        page_char_start=0,
        page_char_end=5,
        text="no section keyword here",
        doc_meta=doc_meta,
        pdf_outline_breadcrumb=["Part II", "Employment"],
    )
    norm = _mod.normalize_chunk_for_kg(raw)
    assert norm["section_label"] == "Employment"


def test_validate_strict_requires_tier() -> None:
    row = {"chunk_id": "a::p0001::c0000", "source_doc_id": "a"}
    assert not _mod.validate_kg_chunk_metadata(row, strict_doc_meta=False)
    errs = _mod.validate_kg_chunk_metadata(row, strict_doc_meta=True)
    assert errs and any("tier" in e for e in errs)
