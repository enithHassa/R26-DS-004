"""Phase 5.6 — business income (5.6a net path + 5.6b gross/deductions/CA)."""

from __future__ import annotations

from decimal import Decimal

from adaptive_tax_app.config import AdaptiveTaxSettings
from adaptive_tax_app.schemas.calculate import CalculateTaxRequestV1
from adaptive_tax_app.services.kg_client import FileOntologyKgClient
from adaptive_tax_app.services.provenance import clear_provenance_cache
from adaptive_tax_app.services.rule_engine import calculate, default_file_kg


def test_kg_business_income_governed_by_section_6() -> None:
    kg = FileOntologyKgClient()
    hit = kg.resolve_applicable_concepts(
        income_types=["business_income"],
        claimed_deductions=[],
    )
    assert "business_income" in hit.income_concept_ids
    sections = hit.income_section_uids.get("business_income") or ()
    assert any("section_6" in u for u in sections)


def test_ex02_business_same_tax_as_ex01_with_sec6_provenance() -> None:
    clear_provenance_cache()
    result = calculate(
        CalculateTaxRequestV1(
            assessment_year="2024_25",
            resident_status="resident",
            business_income=Decimal("1800000"),
        ),
        kg=default_file_kg(),
    )
    assert result.final_tax_lkr == "42000"
    assert "compute_business_net" not in result.rules_applied
    step = next(s for s in result.calculation_trace if s.step_id == "sum_assessable")
    assert step.inputs["business_income"] == "1800000"
    assert "business_income" in step.concept_ids
    assert any("section_6" in u for u in step.section_uids)
    assert "bootstrap:business_income" in step.rule_source_ids
    assert any(
        ref.id == "bootstrap:business_income" and ref.section == "6"
        for ref in result.rule_source_refs
    )


def test_employment_plus_business_heads_both_provenance() -> None:
    clear_provenance_cache()
    result = calculate(
        CalculateTaxRequestV1(
            assessment_year="2024_25",
            resident_status="resident",
            employment_income=Decimal("900000"),
            business_income=Decimal("900000"),
        ),
        kg=default_file_kg(),
    )
    assert result.final_tax_lkr == "42000"
    step = next(s for s in result.calculation_trace if s.step_id == "sum_assessable")
    assert step.inputs["employment_income"] == "900000"
    assert step.inputs["business_income"] == "900000"
    assert "bootstrap:business_income" in step.rule_source_ids
    assert "bootstrap:employment_income" in step.rule_source_ids


def test_business_gross_minus_deductions_matches_ex02_tax() -> None:
    clear_provenance_cache()
    result = calculate(
        CalculateTaxRequestV1(
            assessment_year="2024_25",
            resident_status="resident",
            business_gross=Decimal("2000000"),
            business_deductions=Decimal("200000"),
        ),
        kg=default_file_kg(),
    )
    assert result.final_tax_lkr == "42000"
    assert "compute_business_net" in result.rules_applied
    steps = {s.step_id: s for s in result.calculation_trace}
    assert steps["compute_business_net"].output == "1800000"
    assert steps["compute_business_net"].inputs["allowed_deductions"] == "200000"
    assert steps["sum_assessable"].inputs["business_income"] == "1800000"
    assert any("section_11" in u for u in steps["compute_business_net"].section_uids)
    assert "bootstrap:compute_business_net" in {
        r.id for r in result.rule_source_refs
    }
    assert "bootstrap:business_deductions" in {
        r.id for r in result.rule_source_refs
    }


def test_business_gross_minus_capital_allowances_matches_ex02_tax() -> None:
    clear_provenance_cache()
    result = calculate(
        CalculateTaxRequestV1(
            assessment_year="2024_25",
            resident_status="resident",
            business_gross=Decimal("1900000"),
            capital_allowances=Decimal("100000"),
        ),
        kg=default_file_kg(),
    )
    assert result.final_tax_lkr == "42000"
    steps = {s.step_id: s for s in result.calculation_trace}
    assert steps["compute_business_net"].inputs["allowed_capital_allowances"] == "100000"
    assert any("section_16" in u for u in steps["compute_business_net"].section_uids)
    assert "bootstrap:capital_allowances" in {r.id for r in result.rule_source_refs}


def test_gross_path_ignored_without_bootstrap_in_legacy(
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
            business_income=Decimal("1800000"),
            business_gross=Decimal("2000000"),
            business_deductions=Decimal("200000"),
        ),
        kg=default_file_kg(),
        settings=settings,
    )
    assert "compute_business_net" not in result.rules_applied
    assert result.final_tax_lkr == "42000"
    prov.clear_provenance_cache()


def test_business_catalog_gross_path_matches_ex13() -> None:
    """Phase 6.4 — biz_gross + biz_deductions filing_lines → Sec 6 net path."""
    from adaptive_tax_app.schemas.calculate import FilingLineV1
    from adaptive_tax_app.services.filing_catalog import clear_filing_catalog_cache
    from adaptive_tax_app.services.provenance import clear_provenance_cache

    clear_filing_catalog_cache()
    clear_provenance_cache()
    result = calculate(
        CalculateTaxRequestV1(
            assessment_year="2024_25",
            resident_status="resident",
            filing_lines=[
                FilingLineV1(component_id="biz_gross", amount="2000000"),
                FilingLineV1(component_id="biz_deductions", amount="200000"),
            ],
        ),
        kg=default_file_kg(),
    )
    assert "aggregate_business_components" in result.rules_applied
    assert "compute_business_net" in result.rules_applied
    assert result.final_tax_lkr == "42000"
    net = next(s for s in result.calculation_trace if s.step_id == "compute_business_net")
    assert net.output == "1800000"


def test_business_catalog_net_path() -> None:
    from adaptive_tax_app.schemas.calculate import FilingLineV1
    from adaptive_tax_app.services.filing_catalog import clear_filing_catalog_cache
    from adaptive_tax_app.services.provenance import clear_provenance_cache

    clear_filing_catalog_cache()
    clear_provenance_cache()
    result = calculate(
        CalculateTaxRequestV1(
            assessment_year="2024_25",
            resident_status="resident",
            filing_lines=[
                FilingLineV1(component_id="biz_net_profits", amount="1800000"),
            ],
        ),
        kg=default_file_kg(),
    )
    assert "aggregate_business_components" in result.rules_applied
    assert "compute_business_net" not in result.rules_applied
    assert result.final_tax_lkr == "42000"
    assert any(c.component_id == "biz_net_profits" for c in result.component_trace)
