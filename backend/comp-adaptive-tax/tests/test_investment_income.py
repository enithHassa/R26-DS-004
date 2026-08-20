"""Phase 5.7 — investment income Sec 7 path + Sec 7(3)(a) exclusion."""

from __future__ import annotations

from decimal import Decimal

from adaptive_tax_app.config import AdaptiveTaxSettings
from adaptive_tax_app.schemas.calculate import CalculateTaxRequestV1
from adaptive_tax_app.services.kg_client import FileOntologyKgClient
from adaptive_tax_app.services.provenance import clear_provenance_cache
from adaptive_tax_app.services.rule_engine import calculate, default_file_kg


def _calc(**kwargs):
    return calculate(
        CalculateTaxRequestV1.model_validate(kwargs),
        kg=default_file_kg(),
    )


def test_kg_investment_governed_by_section_7() -> None:
    kg = FileOntologyKgClient()
    hit = kg.resolve_applicable_concepts(
        income_types=["investment_income"],
        claimed_deductions=[],
    )
    assert "investment_income" in hit.income_concept_ids
    sections = hit.income_section_uids.get("investment_income") or ()
    assert any("section_7" in u for u in sections)


def test_ex15_investment_base_same_tax_as_ex01() -> None:
    clear_provenance_cache()
    result = _calc(
        assessment_year="2024_25",
        resident_status="resident",
        investment_income="1800000",
        investment_final_withholding="0",
    )
    assert result.final_tax_lkr == "42000"
    assert "exclude_investment_final_withholding" not in result.rules_applied
    step = next(s for s in result.calculation_trace if s.step_id == "sum_assessable")
    assert step.inputs["investment_income"] == "1800000"
    assert "bootstrap:investment_income" in step.rule_source_ids
    assert any("section_7" in u for u in step.section_uids)


def test_sec7_final_wht_exclusion_reduces_assessable_and_tax() -> None:
    clear_provenance_cache()
    result = _calc(
        assessment_year="2024_25",
        resident_status="resident",
        investment_income="1800000",
        investment_final_withholding="200000",
    )
    steps = {s.step_id: s for s in result.calculation_trace}
    assert result.final_tax_lkr == "24000"
    assert steps["exclude_investment_final_withholding"].output == "1600000"
    assert steps["sum_assessable"].output == "1600000"
    assert "bootstrap:exclude_investment_final_wht" in {
        r.id for r in result.rule_source_refs
    }
    assert any(
        "section_7" in u for u in steps["exclude_investment_final_withholding"].section_uids
    )


def test_investment_exclusion_ignored_without_bootstrap_in_legacy(
    monkeypatch, tmp_path
) -> None:
    """Without Act quote, claimed FWH must not invent an exclusion (sum as today)."""
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
            investment_income=Decimal("1800000"),
            investment_final_withholding=Decimal("200000"),
        ),
        kg=default_file_kg(),
        settings=settings,
    )
    assert "exclude_investment_final_withholding" not in result.rules_applied
    assert result.final_tax_lkr == "42000"
    prov.clear_provenance_cache()
