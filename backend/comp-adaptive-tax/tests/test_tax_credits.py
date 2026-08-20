"""Phase 5.8 — APIT / tax credits → tax_payable (gross final_tax unchanged)."""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path

from adaptive_tax_app.config import AdaptiveTaxSettings
from adaptive_tax_app.schemas.calculate import CalculateTaxRequestV1
from adaptive_tax_app.services.provenance import clear_provenance_cache
from adaptive_tax_app.services.rule_engine import calculate, default_file_kg

_REPO = Path(__file__).resolve().parents[3]
_EDGES = _REPO / "models" / "adaptive-tax" / "ontology" / "mvp_calc_edges_seed.jsonl"


def _calc(**kwargs):
    return calculate(
        CalculateTaxRequestV1.model_validate(kwargs),
        kg=default_file_kg(),
    )


def test_kg_tax_credit_governed_by_section_89() -> None:
    rows = [
        json.loads(line)
        for line in _EDGES.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    governed = [
        e
        for e in rows
        if e.get("rel_type") == "GOVERNED_BY"
        and e.get("from_id") in {"tax_credit", "apit_already_paid"}
    ]
    assert governed
    assert any("section_89" in (e.get("to_id") or "") for e in governed)


def test_ex17_apit_credit_reduces_payable_keeps_gross() -> None:
    clear_provenance_cache()
    result = _calc(
        assessment_year="2024_25",
        resident_status="resident",
        employment_income="1800000",
        apit_already_paid="20000",
    )
    assert result.final_tax_lkr == "42000"
    assert result.tax_payable_lkr == "22000"
    assert result.tax_credits_applied_lkr == "20000"
    assert "apply_tax_credit" in result.rules_applied
    step = next(s for s in result.calculation_trace if s.step_id == "apply_tax_credit")
    assert step.output == "22000"
    assert "bootstrap:tax_credit" in step.rule_source_ids
    assert any("section_89" in u for u in step.section_uids)


def test_no_credit_claim_payable_equals_gross() -> None:
    clear_provenance_cache()
    result = _calc(
        assessment_year="2024_25",
        resident_status="resident",
        employment_income="1800000",
        apit_already_paid="0",
    )
    assert result.final_tax_lkr == "42000"
    assert result.tax_payable_lkr == "42000"
    assert result.tax_credits_applied_lkr == "0"
    assert "apply_tax_credit" not in result.rules_applied


def test_credit_overpayment_floors_payable_at_zero() -> None:
    clear_provenance_cache()
    result = _calc(
        assessment_year="2024_25",
        resident_status="resident",
        employment_income="1800000",
        apit_already_paid="100000",
    )
    assert result.final_tax_lkr == "42000"
    assert result.tax_payable_lkr == "0"
    assert result.tax_credits_applied_lkr == "42000"


def test_credit_ignored_without_bootstrap_in_legacy(monkeypatch, tmp_path) -> None:
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
            apit_already_paid=Decimal("20000"),
        ),
        kg=default_file_kg(),
        settings=settings,
    )
    assert "apply_tax_credit" not in result.rules_applied
    assert result.final_tax_lkr == "42000"
    assert result.tax_payable_lkr == "42000"
    assert result.tax_credits_applied_lkr == "0"
    prov.clear_provenance_cache()
