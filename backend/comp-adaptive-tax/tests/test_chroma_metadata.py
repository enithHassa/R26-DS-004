"""Unit tests for Chroma metadata helpers (no embedding / disk I/O)."""

from __future__ import annotations

from adaptive_tax_app.services.chroma_index import (
    CHROMA_BLOCKED_SOURCE_DOC_IDS,
    chunk_metadata_for_chroma,
)


def test_chunk_metadata_includes_phase6_scalars() -> None:
    meta = chunk_metadata_for_chroma(
        {
            "chunk_id": "ird-ira-2017-base::p0010::c0001",
            "source_doc_id": "ird-ira-2017-base",
            "section_ref": "Section 52",
            "paragraph_ref": "52(4)",
            "parent_provision_id": "section:52",
            "chunk_part": 2,
            "chunk_parts": 3,
            "is_operative_provision": True,
            "is_toc": False,
            "is_header_footer": False,
            "is_cross_reference": False,
            "instrument_type": "base_act",
            "page": 42,
            "effective_start_date": "2018-04-01",
            "applicable_assessment_years": ["2024_25", "2025_26"],
            "metadata_source": "deterministic",
            "needs_review": False,
        }
    )
    assert meta["section_ref"] == "Section 52"
    assert meta["section_num"] == "52"
    assert meta["paragraph_ref"] == "52(4)"
    assert meta["parent_provision_id"] == "section:52"
    assert meta["chunk_part"] == 2
    assert meta["chunk_parts"] == 3
    assert meta["is_operative_provision"] is True
    assert meta["is_toc"] is False
    assert meta["instrument_type"] == "base_act"
    assert meta["page"] == 42
    assert meta["effective_start_date"] == "2018-04-01"
    assert meta["applicable_yas"] == "2024_25,2025_26"
    assert meta["metadata_source"] == "deterministic"
    # Chroma-safe: no lists
    assert all(isinstance(v, (str, int, float, bool)) for v in meta.values())


def test_section_num_first_schedule_and_multi_ref() -> None:
    assert (
        chunk_metadata_for_chroma({"section_ref": "First Schedule"})["section_num"]
        == "first_schedule"
    )
    assert (
        chunk_metadata_for_chroma({"section_ref": ["Section 5", "Section 6"]})[
            "section_num"
        ]
        == "5"
    )


def test_guide_and_master_remain_blocked() -> None:
    assert "ird-guide-ira" in CHROMA_BLOCKED_SOURCE_DOC_IDS
    assert "ird-calc-ontology-v5" in CHROMA_BLOCKED_SOURCE_DOC_IDS
