"""Phase 5.0b provenance gate — strict vs legacy behaviour."""

from __future__ import annotations

import os
from decimal import Decimal

import pytest

from adaptive_tax_app.config import get_adaptive_tax_settings
from adaptive_tax_app.schemas.calculate import CalculateTaxRequestV1
from adaptive_tax_app.services.engine_handlers import (
    HANDLER_CAP_QP,
    HANDLER_DEDUCT_QP,
    HANDLER_PERSONAL_RELIEF,
    gate,
)
from adaptive_tax_app.services.param_store import clear_param_store_cache
from adaptive_tax_app.services.provenance import (
    ProvenanceError,
    clear_provenance_cache,
    resolve_rule_sources,
)
from adaptive_tax_app.services.rule_engine import calculate, default_file_kg


@pytest.fixture(autouse=True)
def _reset_caches(monkeypatch: pytest.MonkeyPatch) -> None:
    clear_provenance_cache()
    clear_param_store_cache()
    get_adaptive_tax_settings.cache_clear()
    yield
    clear_provenance_cache()
    clear_param_store_cache()
    get_adaptive_tax_settings.cache_clear()


def test_deprecated_sec52_cap_handler_not_required() -> None:
    """Aggregate QP cap handler removed (Path B); deduct handler remains."""
    ya24 = resolve_rule_sources(HANDLER_DEDUCT_QP, "2024_25")
    assert ya24.ok
    cap = resolve_rule_sources(HANDLER_CAP_QP, "2024_25")
    assert not cap.ok or cap.records == []


def test_legacy_mode_marks_steps_and_completes_calc(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("COMP_ADAPTIVE_TAX_PROVENANCE_MODE", "legacy")
    get_adaptive_tax_settings.cache_clear()
    result = calculate(
        CalculateTaxRequestV1(
            assessment_year="2024_25",
            employment_income=Decimal("1800000"),
        ),
        kg=default_file_kg(),
    )
    assert result.final_tax_lkr == "42000"
    assert result.provenance_complete is True
    assert any(s.provenance in {"approved", "legacy_seed"} for s in result.calculation_trace)
    # Enriched refs carry Act quotes.
    quoted = [r for r in result.rule_source_refs if r.source_quote]
    assert quoted
    assert all(r.section for r in quoted)


def test_strict_mode_goldens_pass_with_bootstrap(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("COMP_ADAPTIVE_TAX_PROVENANCE_MODE", "strict")
    get_adaptive_tax_settings.cache_clear()
    result = calculate(
        CalculateTaxRequestV1(
            assessment_year="2025_26",
            employment_income=Decimal("3000000"),
            qualifying_payments=Decimal("2500000"),
        ),
        kg=default_file_kg(),
    )
    assert result.final_tax_lkr == "0"
    assert result.provenance_complete is True
    qp_steps = [s for s in result.calculation_trace if "qualifying" in s.step_id]
    assert qp_steps
    assert all(s.rule_source_ids for s in qp_steps)
    assert all(s.provenance == "approved" for s in qp_steps)


def test_strict_mode_blocks_unknown_handler(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("COMP_ADAPTIVE_TAX_PROVENANCE_MODE", "strict")
    get_adaptive_tax_settings.cache_clear()
    with pytest.raises(ProvenanceError, match="Strict provenance"):
        gate("cap_absolute:unknown_relief_never_seeded", "2024_25")


def test_personal_relief_gate_resolves(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("COMP_ADAPTIVE_TAX_PROVENANCE_MODE", "strict")
    get_adaptive_tax_settings.cache_clear()
    g = gate(HANDLER_PERSONAL_RELIEF, "2024_25")
    assert g.resolution.ok
    assert g.resolution.records[0].section == "First Schedule"


def test_dual_ya_strict_adaptivity(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("COMP_ADAPTIVE_TAX_PROVENANCE_MODE", "strict")
    get_adaptive_tax_settings.cache_clear()
    shared = {
        "resident_status": "resident",
        "employment_income": Decimal("3000000"),
        "qualifying_payments": Decimal("1500000"),
        "param_set": "current",
    }
    kg = default_file_kg()
    t24 = calculate(
        CalculateTaxRequestV1(assessment_year="2024_25", **shared),
        kg=kg,
    )
    t25 = calculate(
        CalculateTaxRequestV1(assessment_year="2025_26", **shared),
        kg=kg,
    )
    assert t24.final_tax_lkr == "18000"
    assert t25.final_tax_lkr == "0"
    assert t24.provenance_complete and t25.provenance_complete
