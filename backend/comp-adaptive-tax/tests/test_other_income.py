"""Phase 6.5 — other income Sec 8 path + residual catalog + Sec 8(2)(a) exclusion."""

from __future__ import annotations

from decimal import Decimal

from adaptive_tax_app.config import AdaptiveTaxSettings
from adaptive_tax_app.schemas.calculate import CalculateTaxRequestV1, FilingLineV1
from adaptive_tax_app.services.filing_catalog import (
    clear_filing_catalog_cache,
    get_filing_catalog_for_year,
)
from adaptive_tax_app.services.kg_client import FileOntologyKgClient
from adaptive_tax_app.services.provenance import clear_provenance_cache
from adaptive_tax_app.services.request_normalize import normalize_request
from adaptive_tax_app.services.rule_engine import calculate, default_file_kg


def setup_function() -> None:
    clear_filing_catalog_cache()
    clear_provenance_cache()


def _calc(**kwargs):
    return calculate(
        CalculateTaxRequestV1.model_validate(kwargs),
        kg=default_file_kg(),
    )


def test_kg_other_income_governed_by_section_8() -> None:
    kg = FileOntologyKgClient()
    hit = kg.resolve_applicable_concepts(
        income_types=["other_income"],
        claimed_deductions=[],
    )
    assert "other_income" in hit.income_concept_ids
    sections = hit.income_section_uids.get("other_income") or ()
    assert any("section_8" in u for u in sections)


def test_other_income_scalar_same_tax_as_ex01() -> None:
    result = _calc(
        assessment_year="2024_25",
        resident_status="resident",
        other_income="1800000",
        other_final_withholding="0",
    )
    assert result.final_tax_lkr == "42000"
    assert "exclude_other_final_withholding" not in result.rules_applied
    step = next(s for s in result.calculation_trace if s.step_id == "sum_assessable")
    assert step.inputs["other_income"] == "1800000"
    assert "bootstrap:other_income" in step.rule_source_ids
    assert any("section_8" in u for u in step.section_uids)


def test_sec8_final_wht_exclusion_reduces_assessable_and_tax() -> None:
    result = _calc(
        assessment_year="2024_25",
        resident_status="resident",
        other_income="1800000",
        other_final_withholding="200000",
    )
    steps = {s.step_id: s for s in result.calculation_trace}
    assert result.final_tax_lkr == "24000"
    assert steps["exclude_other_final_withholding"].output == "1600000"
    assert steps["sum_assessable"].output == "1600000"
    assert "bootstrap:exclude_other_final_wht" in {
        r.id for r in result.rule_source_refs
    }
    assert any(
        "section_8" in u for u in steps["exclude_other_final_withholding"].section_uids
    )


def test_other_exclusion_ignored_without_bootstrap_in_legacy(
    monkeypatch, tmp_path
) -> None:
    empty = tmp_path / "empty_bootstrap.json"
    empty.write_text(
        '{"spec_version":"1.0.0","status":"approved","rules":[]}',
        encoding="utf-8",
    )
    from adaptive_tax_app.services import provenance as prov

    monkeypatch.setattr(prov, "bootstrap_path", lambda: empty)
    prov.clear_provenance_cache()
    settings = AdaptiveTaxSettings(COMP_ADAPTIVE_TAX_PROVENANCE_MODE="legacy")
    result = calculate(
        CalculateTaxRequestV1(
            assessment_year="2024_25",
            resident_status="resident",
            other_income=Decimal("1800000"),
            other_final_withholding=Decimal("200000"),
        ),
        kg=default_file_kg(),
        settings=settings,
    )
    assert "exclude_other_final_withholding" not in result.rules_applied
    assert result.final_tax_lkr == "42000"
    prov.clear_provenance_cache()


def test_catalog_other_income_fields_medium_confidence() -> None:
    catalog = get_filing_catalog_for_year("2024_25")
    other = next(c for c in catalog.cards if c.card_id == "other_income")
    ids = {f.component_id for f in other.fields}
    assert {"oth_residual", "oth_custom", "oth_final_withholding"} <= ids
    residual = next(f for f in other.fields if f.component_id == "oth_residual")
    custom = next(f for f in other.fields if f.component_id == "oth_custom")
    assert residual.legal_confidence == "medium"
    assert residual.confidence_basis == "interpretive"
    assert "residual" in (residual.confidence_reason or "").lower()
    assert custom.legal_confidence == "medium"
    assert custom.input_kind == "custom_list"
    fwh = next(f for f in other.fields if f.component_id == "oth_final_withholding")
    assert fwh.legal_confidence == "high"
    assert fwh.default_treatment == "final_withholding"


def test_normalize_other_income_custom_and_residual() -> None:
    result = normalize_request(
        CalculateTaxRequestV1(
            assessment_year="2024_25",
            resident_status="resident",
            other_income=Decimal("9999999"),
            filing_lines=[
                FilingLineV1(component_id="oth_residual", amount="1000000"),
                FilingLineV1(
                    component_id="oth_custom",
                    amount="800000",
                    label_override="Freelance residual receipts",
                ),
                FilingLineV1(component_id="oth_final_withholding", amount="50000"),
            ],
        )
    )
    assert result.used_filing_lines
    assert result.request.other_income == Decimal("1800000")
    assert result.request.other_final_withholding == Decimal("50000")
    assert result.head_subtotals["other_include"] == Decimal("1800000")
    labels = {row.display_name for row in result.component_trace}
    assert "Freelance residual receipts" in labels


def test_other_catalog_path_matches_ex25() -> None:
    result = calculate(
        CalculateTaxRequestV1(
            assessment_year="2024_25",
            resident_status="resident",
            filing_lines=[
                FilingLineV1(component_id="oth_residual", amount="1000000"),
                FilingLineV1(
                    component_id="oth_custom",
                    amount="800000",
                    label_override="Freelance residual receipts",
                ),
            ],
        ),
        kg=default_file_kg(),
    )
    assert "aggregate_other_income_components" in result.rules_applied
    assert result.final_tax_lkr == "42000"
    step = next(
        s for s in result.calculation_trace if s.step_id == "sum_assessable"
    )
    assert step.inputs["other_income"] == "1800000"
    assert any(c.component_id == "oth_custom" for c in result.component_trace)
