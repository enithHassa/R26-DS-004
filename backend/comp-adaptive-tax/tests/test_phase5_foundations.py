"""Phase 5.0 foundations — dual YA, section harvest focus, coverage metric."""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import ValidationError

from adaptive_tax_app.schemas.calculate import CalculateTaxRequestV1
from adaptive_tax_app.schemas.extracted_rule import ExtractedRule
from adaptive_tax_app.services.evidence import filter_explain_chunks
from adaptive_tax_app.schemas.evidence import EvidenceChunk
from adaptive_tax_app.services.param_store import load_tax_param_pack, relief_cap_filename
from adaptive_tax_app.services.pdf_extract import focus_section_text
from adaptive_tax_app.services.rule_engine import calculate, default_file_kg
from backend.shared.config.settings import PROJECT_ROOT


def test_request_accepts_assessment_year_2025_26() -> None:
    req = CalculateTaxRequestV1.model_validate(
        {
            "assessment_year": "2025_26",
            "employment_income": "1800000",
            "param_set": "current",
        }
    )
    assert req.assessment_year == "2025_26"


def test_request_rejects_unknown_assessment_year() -> None:
    with pytest.raises(ValidationError):
        CalculateTaxRequestV1.model_validate({"assessment_year": "2026_27"})


def test_relief_cap_filename_by_year() -> None:
    assert relief_cap_filename("2024_25", "current") == "relief_caps_2024_25.json"
    assert relief_cap_filename("2025_26", "current") == "relief_caps_2025_26.json"
    assert relief_cap_filename("2024_25", "pre_amend_2025") == (
        "relief_caps_pre_amend_2025.json"
    )


def test_dual_ya_same_inputs_different_sec52_tax() -> None:
    shared = {
        "resident_status": "resident",
        "employment_income": "3000000",
        "qualifying_payments": "1500000",
        "param_set": "current",
    }
    kg = default_file_kg()
    t24 = calculate(
        CalculateTaxRequestV1.model_validate({**shared, "assessment_year": "2024_25"}),
        kg=kg,
    )
    t25 = calculate(
        CalculateTaxRequestV1.model_validate({**shared, "assessment_year": "2025_26"}),
        kg=kg,
    )
    assert t24.final_tax_lkr == "18000"
    assert t25.final_tax_lkr == "0"
    assert t24.final_tax_lkr != t25.final_tax_lkr


def test_focus_section_text_finds_section_52() -> None:
    text = (
        "PART II\n\n"
        "Section 51\nSomething else.\n\n"
        "Section 52\n"
        "A qualifying payment shall not exceed one million two hundred thousand rupees.\n\n"
        "Section 53\nNext section.\n"
    )
    focused = focus_section_text(text, "52", search_patterns=["Section 52"])
    assert focused.harvest_mode == "section"
    assert "qualifying payment" in focused.focused_text.lower()
    assert "Section 53" not in focused.focused_text


def test_extracted_rule_accepts_phase5_fields() -> None:
    rule = ExtractedRule.model_validate(
        {
            "section": "52",
            "rule_type": "limit",
            "concept_id": "qualifying_payment_cap",
            "maximum": 1_800_000,
            "source_quote": "A qualifying payment shall not exceed one million eight hundred thousand rupees in the aggregate.",
            "executable": True,
            "engine_handler": "cap_absolute",
            "assessment_years": ["2025_26"],
            "applies_to_taxpayer": "resident_individual",
            "relationship_hints": [
                {
                    "from_concept": "qualifying_payment",
                    "rel_type": "LIMITED_BY",
                    "to_concept": "qualifying_payment_cap",
                }
            ],
        }
    )
    assert rule.executable is True
    assert rule.engine_handler == "cap_absolute"
    assert rule.assessment_years == ["2025_26"]
    assert len(rule.relationship_hints) == 1


def test_filter_explain_chunks_drops_master_pdf() -> None:
    chunks = [
        EvidenceChunk(
            chunk_id="a",
            text="Section 52 from Act",
            section_ref="Section 52",
            source_doc_id="ird-ira-2017-base",
            page=1,
            score=0.9,
        ),
        EvidenceChunk(
            chunk_id="b",
            text="Master ontology notes",
            section_ref="Section 52",
            source_doc_id="ird-calc-ontology-v5",
            page=1,
            score=0.8,
        ),
    ]
    kept = filter_explain_chunks(chunks)
    assert len(kept) == 1
    assert kept[0].chunk_id == "a"


def test_coverage_scorer_reports_full_phase5_areas() -> None:
    import importlib.util

    scorer_path = (
        PROJECT_ROOT
        / "evaluation"
        / "adaptive-tax"
        / "coverage"
        / "score_coverage.py"
    )
    spec = importlib.util.spec_from_file_location("score_coverage", scorer_path)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    path = PROJECT_ROOT / "models" / "adaptive-tax" / "harvest" / "coverage_checklist_v1.json"
    doc = json.loads(path.read_text(encoding="utf-8"))
    result = mod.score_coverage(doc)
    assert result["n_planned"] == 9
    assert result["n_covered"] == 9
    assert result["coverage"] == 1.0
    assert "employment_income" in result["covered_area_ids"]
    assert "first_schedule_rates" in result["covered_area_ids"]
    assert "personal_relief" in result["covered_area_ids"]
    assert "sec52_qualifying_payments" in result["covered_area_ids"]
    assert "donations" in result["covered_area_ids"]
    assert "business_income" in result["covered_area_ids"]
    assert "investment_income" in result["covered_area_ids"]
    assert "other_income" in result["covered_area_ids"]
    assert "tax_credits" in result["covered_area_ids"]
    assert result["pending_area_ids"] == []


def test_param_rows_expose_optional_rule_source_id() -> None:
    pack = load_tax_param_pack(assessment_year="2025_26", param_set="current")
    assert pack.relief_for_concept("qualifying_payment_cap") is None
    pr = pack.relief_for_concept("personal_relief")
    assert pr is not None
    assert pr.cap_amount == Decimal("1800000")
    assert pr.rule_source_id == "bootstrap:personal_relief_2025_26"
    assert pack.relief_for_concept("donation_cap").rule_source_id == (
        "bootstrap:donation_cap_2025_26"
    )
    assert pack.rate_bands[0].rule_source_id is not None  # Phase 5.2 Act bootstrap
