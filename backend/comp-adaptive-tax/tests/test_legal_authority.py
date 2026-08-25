"""Tests for legal-document authority / YA precedence helpers."""

from __future__ import annotations

from adaptive_tax_app.services.legal_authority import (
    TIER_AMENDMENT_OR_CONSOLIDATED,
    TIER_BASE_ACT,
    TIER_EXACT_PARAGRAPH,
    TIER_WRONG_YA,
    doc_ya_status,
    legal_precedence_tier,
    load_doc_authority_table,
    normalize_assessment_year,
)


def setup_function() -> None:
    load_doc_authority_table.cache_clear()


def test_normalize_assessment_year() -> None:
    assert normalize_assessment_year("2025/26") == "2025_26"
    assert normalize_assessment_year("2024-25") == "2024_25"
    assert normalize_assessment_year("2025_26") == "2025_26"


def test_doc_ya_status_from_manifest() -> None:
    assert doc_ya_status("ird-ira-2017-base", "2024_25") == "match"
    assert doc_ya_status("ird-amend-2025-02", "2025_26") == "match"
    assert doc_ya_status("ird-amend-2025-02", "2024_25") == "mismatch"
    assert doc_ya_status("ird-guide-ira", "2025_26") == "blocked"
    assert doc_ya_status("ird-amend-2023-04", "2025_26") == "unknown"


def test_precedence_tiers_order() -> None:
    exact = legal_precedence_tier(
        source_doc_id="ird-amend-2025-02",
        instrument_type="amendment_act",
        assessment_year="2025_26",
        section_matched=True,
        paragraph_ref_wanted="52(4)",
        paragraph_ref_chunk="52(4)",
        text="Section 52(4) carry forward",
    )
    amend = legal_precedence_tier(
        source_doc_id="ird-amend-2025-02",
        instrument_type="amendment_act",
        assessment_year="2025_26",
        section_matched=True,
        text="Section 52",
    )
    base = legal_precedence_tier(
        source_doc_id="ird-ira-2017-base",
        instrument_type="base_act",
        assessment_year="2025_26",
        section_matched=True,
        text="Section 52",
    )
    wrong = legal_precedence_tier(
        source_doc_id="ird-amend-2025-02",
        instrument_type="amendment_act",
        assessment_year="2024_25",
        section_matched=True,
        text="Section 52",
    )
    assert exact == TIER_EXACT_PARAGRAPH
    assert amend == TIER_AMENDMENT_OR_CONSOLIDATED
    assert base == TIER_BASE_ACT
    assert wrong == TIER_WRONG_YA
    assert exact < amend < base < wrong
