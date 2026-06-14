"""Tests for Phase 3 Step 4 chunk → graph ETL bundles."""

from __future__ import annotations

import importlib.util
from pathlib import Path

_ROOT = Path(__file__).resolve().parent

_spec_ic = importlib.util.spec_from_file_location("ird_corpus_lib", _ROOT / "ird_corpus_lib.py")
_mod_ic = importlib.util.module_from_spec(_spec_ic)
assert _spec_ic.loader is not None
_spec_ic.loader.exec_module(_mod_ic)

_spec_kg = importlib.util.spec_from_file_location("kg_etl_lib", _ROOT / "kg_etl_lib.py")
_mod_kg = importlib.util.module_from_spec(_spec_kg)
assert _spec_kg.loader is not None
_spec_kg.loader.exec_module(_mod_kg)


def _sample_doc_meta() -> dict:
    return {
        "tier": "A",
        "instrument_type": "act",
        "doc_type": "statute",
        "publication_date": "",
        "effective_start_date": "2018-04-01",
        "effective_end_date": "",
        "version_label": "v1",
        "source_url": "https://example.invalid",
        "title": "IRA 2017",
        "authority_weight": "1.0",
        "is_draft": False,
        "language": "en",
    }


def test_section_uid_slug() -> None:
    assert _mod_kg.make_section_uid("doc", "Section 45") == "doc::sec::section_45"
    assert _mod_kg.make_section_uid("doc", None) is None
    assert _mod_kg.make_section_uid("doc", "   ") is None


def test_bundle_includes_lex_specialis_on_law_instrument() -> None:
    raw = _mod_ic.build_text_chunk_record(
        source_doc_id="ira2017",
        page=1,
        chunk_index=0,
        page_char_start=0,
        page_char_end=4,
        text="x",
        doc_meta=_sample_doc_meta(),
    )
    bundle = _mod_kg.etl_bundle_from_chunk_row(raw, include_text=False)
    assert bundle["etl_bundle_version"] == "1.1.0"
    li = next(n for n in bundle["nodes"] if "LawInstrument" in n["labels"])
    assert li["properties"].get("authority_class") == "statute"
    assert li["properties"].get("specificity_rank") == 85
    tc = next(n for n in bundle["nodes"] if "TextChunk" in n["labels"])
    assert tc["properties"].get("authority_class") == "statute"


def test_bundle_without_section_uses_lawinstrument_has_chunk() -> None:
    raw = _mod_ic.build_text_chunk_record(
        source_doc_id="ira2017",
        page=1,
        chunk_index=0,
        page_char_start=0,
        page_char_end=8,
        text="no section numbers in this window",
        doc_meta=_sample_doc_meta(),
    )
    bundle = _mod_kg.etl_bundle_from_chunk_row(raw, include_text=False)
    labels = {tuple(n["labels"]) for n in bundle["nodes"]}
    assert ("TextChunk",) in labels
    assert ("LawInstrument",) in labels
    assert sum(1 for n in bundle["nodes"] if "Section" in n["labels"]) == 0
    assert len(bundle["relationships"]) == 1
    assert bundle["relationships"][0]["type"] == "HAS_CHUNK"
    assert bundle["relationships"][0]["from"]["label"] == "LawInstrument"


def test_bundle_with_section_adds_part_of_and_section_has_chunk() -> None:
    raw = _mod_ic.build_text_chunk_record(
        source_doc_id="ira2017",
        page=1,
        chunk_index=0,
        page_char_start=0,
        page_char_end=30,
        text="Under Section 12 resident means …",
        doc_meta=_sample_doc_meta(),
    )
    bundle = _mod_kg.etl_bundle_from_chunk_row(raw, include_text=False)
    assert any("Section" in n["labels"] for n in bundle["nodes"])
    types = [r["type"] for r in bundle["relationships"]]
    assert "PART_OF" in types
    assert "HAS_CHUNK" in types
    has_chunk = [r for r in bundle["relationships"] if r["type"] == "HAS_CHUNK"][0]
    assert has_chunk["from"]["label"] == "Section"


def test_assert_bundle_has_text_chunk() -> None:
    raw = _mod_ic.build_text_chunk_record(
        source_doc_id="ira2017",
        page=1,
        chunk_index=0,
        page_char_start=0,
        page_char_end=4,
        text="x",
        doc_meta=_sample_doc_meta(),
    )
    bundle = _mod_kg.etl_bundle_from_chunk_row(raw)
    _mod_kg.assert_bundle_has_text_chunk(bundle)
