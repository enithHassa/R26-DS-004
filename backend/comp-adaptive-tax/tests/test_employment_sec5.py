"""Phase 5.1 — employment income Sec 5 path + Sec 5(3)(a) exclusion."""

from __future__ import annotations

from decimal import Decimal

from adaptive_tax_app.config import AdaptiveTaxSettings
from adaptive_tax_app.schemas.calculate import CalculateTaxRequestV1
from adaptive_tax_app.services.rule_engine import calculate, default_file_kg


def _calc(**kwargs):
    return calculate(
        CalculateTaxRequestV1.model_validate(kwargs),
        kg=default_file_kg(),
    )


def test_ex01_baseline_unchanged_without_exclusion() -> None:
    result = _calc(
        assessment_year="2024_25",
        resident_status="resident",
        employment_income="1800000",
        employment_final_withholding="0",
    )
    assert result.final_tax_lkr == "42000"
    assert "exclude_employment_final_withholding" not in result.rules_applied
    assert result.rules_applied[0] == "sum_assessable"
    assert any("section_5" in u for u in result.calculation_trace[0].section_uids)


def test_sec5_final_wht_exclusion_reduces_assessable_and_tax() -> None:
    result = _calc(
        assessment_year="2024_25",
        resident_status="resident",
        employment_income="1800000",
        employment_final_withholding="200000",
    )
    steps = {s.step_id: s for s in result.calculation_trace}
    assert result.final_tax_lkr == "24000"
    assert steps["exclude_employment_final_withholding"].output == "1600000"
    assert steps["sum_assessable"].output == "1600000"
    assert steps["sum_assessable"].inputs["employment_income"] == "1600000"
    assert "bootstrap:exclude_if_final_wht" in {
        r.id for r in result.rule_source_refs
    }


def test_unknown_other_relief_concepts_ignored() -> None:
    result = _calc(
        assessment_year="2024_25",
        resident_status="resident",
        employment_income="1800000",
        other_reliefs={"not_a_real_concept": "500000"},
    )
    assert result.final_tax_lkr == "42000"
    assert all(
        "not_a_real_concept" not in s.concept_ids
        for s in result.calculation_trace
        if not s.step_id.startswith("unresolved_")
    )


def test_exclusion_ignored_in_legacy_when_bootstrap_disabled(
    monkeypatch, tmp_path
) -> None:
    """Without Act quote, claimed FWH must not silently invent an exclusion."""
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
            employment_income=Decimal("1800000"),
            employment_final_withholding=Decimal("200000"),
        ),
        kg=default_file_kg(),
        settings=settings,
    )
    # No approved quote → exclusion skipped; tax matches gross employment path.
    assert "exclude_employment_final_withholding" not in result.rules_applied
    # Without employment bootstrap either, sum may still run in legacy.
    assert result.final_tax_lkr == "42000"
    prov.clear_provenance_cache()
