"""Unit tests for taxpayer grounding helpers (no DB required)."""

from __future__ import annotations

from app.services.taxpayer_data import (
    TaxpayerFacts,
    extract_name_hint,
    format_taxpayer_block,
    looks_taxpayer_specific,
    name_matches,
    resolve_taxpayer,
)


def test_looks_taxpayer_specific():
    assert looks_taxpayer_specific("How much tax do I pay on my salary?")
    assert looks_taxpayer_specific("What is my taxable income?")
    assert not looks_taxpayer_specific("What is the APIT rate for 2024/25?")


def test_extract_name_hint():
    assert extract_name_hint("Show tax for John Silva") == "John Silva"
    assert extract_name_hint("What about Perera's tax liability?") == "Perera"
    assert extract_name_hint("what is my taxable income") is None


def test_name_matches():
    assert name_matches("Silva", "John Silva")
    assert name_matches("john silva", "Silva, John")
    assert not name_matches("Perera", "John Silva")


def test_resolve_taxpayer_requires_profile_id():
    res = resolve_taxpayer(caller_profile_id=None, name_hint=None)
    assert res.status == "forbidden"

    res = resolve_taxpayer(caller_profile_id="not-a-uuid", name_hint=None)
    assert res.status == "forbidden"


def test_format_taxpayer_block_uses_only_supplied_figures():
    facts = TaxpayerFacts(
        profile_id="00000000-0000-0000-0000-000000000000",
        full_name="Test Taxpayer",
        tax_year="2024_25",
        profile={
            "full_name": "Test Taxpayer",
            "tax_year": "2024_25",
            "gross_monthly_income": 450000.0,
            "epf_balance": 1200000.0,
        },
        fields_used=["financial_profiles"],
    )
    block = format_taxpayer_block(facts)
    assert "Test Taxpayer" in block
    assert "450000" in block
    assert "not on file rather than estimating" in block


def test_format_taxpayer_block_renders_system_context_sections():
    facts = TaxpayerFacts(
        profile_id="00000000-0000-0000-0000-000000000000",
        full_name="Test Taxpayer",
        profile={"full_name": "Test Taxpayer"},
        transactions=[
            {
                "semantic_category": "employment_income",
                "taxability_status": "taxable",
                "gross_amount_lkr": 300000.0,
                "taxable_amount_lkr": 300000.0,
                "tax_rule_code": "APIT-1",
                "certainty_tier": "high",
                "class_source": "model",
                "analysis_payload": {"reasoning": "Monthly salary credit from employer."},
            }
        ],
        recommendations=[
            {
                "strategy_name": "EPF top-up",
                "category": "retirement",
                "legal_reference": "s.52",
                "rank": 1,
                "estimated_annual_savings": 48000.0,
                "adoption_probability": 0.7,
                "confidence": 0.8,
                "explanation_json": {"rationale": "High marginal rate, stable income."},
                "accepted": None,
            }
        ],
        behavioural=[{"question_key": "risk_tolerance", "answer_value": "medium"}],
        fields_used=["classified_extracted_transactions", "recommendations"],
    )
    block = format_taxpayer_block(facts)
    assert "CLASSIFIED TRANSACTIONS" in block
    assert "Monthly salary credit" in block
    assert "PERSONALIZED RECOMMENDATIONS" in block
    assert "EPF top-up" in block
    assert "High marginal rate" in block
    assert "BEHAVIOURAL / RISK PROFILE ANSWERS" in block
