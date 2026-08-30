"""Schema wire-format tests for CalculateTaxRequestV1 / response DTOs."""

from __future__ import annotations

from decimal import Decimal

import pytest
from pydantic import ValidationError

from adaptive_tax_app.schemas.calculate import (
    CalculateTaxRequestV1,
    CalculateTaxResponseV1,
    CalculationTraceStep,
    RuleSourceRef,
)


def test_request_accepts_string_money_and_keeps_decimal() -> None:
    req = CalculateTaxRequestV1.model_validate(
        {
            "assessment_year": "2024_25",
            "resident_status": "resident",
            "employment_income": "1800000",
            "business_income": "0",
            "qualifying_payments": "250000",
            "donations": "10000.50",
            "other_reliefs": {"custom_relief": "5"},
            "param_set": "pre_amend_2025",
        }
    )
    assert req.employment_income == Decimal("1800000")
    assert req.donations == Decimal("10000.50")
    assert req.other_reliefs["custom_relief"] == Decimal("5")
    assert req.param_set == "pre_amend_2025"


def test_request_json_dump_uses_string_money() -> None:
    req = CalculateTaxRequestV1(
        employment_income=Decimal("1800000"),
        donations=Decimal("10000.5"),
        other_reliefs={"x": Decimal("3")},
    )
    payload = req.model_dump(mode="json")
    assert payload["employment_income"] == "1800000"
    assert payload["donations"] == "10000.5"
    assert payload["other_reliefs"]["x"] == "3"
    assert isinstance(payload["business_income"], str)


def test_request_accepts_filing_lines() -> None:
    req = CalculateTaxRequestV1.model_validate(
        {
            "employment_income": "0",
            "filing_lines": [
                {"component_id": "emp_salary", "amount": "1000000"},
                {
                    "component_id": "emp_medical_benefits",
                    "amount": "10000",
                    "treatment": "exempt",
                },
            ],
        }
    )
    assert len(req.filing_lines) == 2
    assert req.filing_lines[0].amount == Decimal("1000000")
    assert req.filing_lines[1].treatment == "exempt"
    payload = req.model_dump(mode="json")
    assert payload["filing_lines"][0]["amount"] == "1000000"


def test_request_rejects_negative_money() -> None:
    with pytest.raises(ValidationError):
        CalculateTaxRequestV1.model_validate({"employment_income": "-1"})


def test_response_trace_fields_are_strings() -> None:
    resp = CalculateTaxResponseV1(
        final_tax_lkr="48000",
        calc_id="11111111-2222-4333-8444-555555555555",
        calculation_trace=[
            CalculationTraceStep(
                step_id="sum_assessable",
                description="Sum assessable",
                formula="sum(...)",
                inputs={"employment_income": "1800000"},
                output="1800000",
                concept_ids=["assessable_income"],
                section_uids=["ird-ira-2017-base::sec::section_5"],
                rule_source_ids=["ird-ira-2017-base"],
            )
        ],
        rules_applied=["sum_assessable", "final_tax"],
        rule_source_refs=[
            RuleSourceRef(id="ird-ira-2017-base", kind="source_doc", concept_id="assessable_income")
        ],
    )
    dumped = resp.model_dump(mode="json")
    assert dumped["final_tax_lkr"] == "48000"
    assert dumped["unresolved_claims"] == []
    assert dumped["calc_id"] == "11111111-2222-4333-8444-555555555555"
    step = dumped["calculation_trace"][0]
    assert step["inputs"]["employment_income"] == "1800000"
    assert step["output"] == "1800000"
    assert step["rule_source_ids"] == ["ird-ira-2017-base"]
