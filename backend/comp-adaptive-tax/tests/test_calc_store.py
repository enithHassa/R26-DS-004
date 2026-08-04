"""Unit tests for Phase 4 calculation JSON store."""

from __future__ import annotations

import uuid
from decimal import Decimal
from pathlib import Path

import pytest

from adaptive_tax_app.config import AdaptiveTaxSettings, get_adaptive_tax_settings
from adaptive_tax_app.schemas.calculate import (
    CalculateTaxRequestV1,
    CalculateTaxResponseV1,
    CalculationTraceStep,
    RuleSourceRef,
)
from adaptive_tax_app.services.calc_store import load, save


def _minimal_response() -> CalculateTaxResponseV1:
    return CalculateTaxResponseV1(
        final_tax_lkr="48000",
        calculation_trace=[
            CalculationTraceStep(
                step_id="sum_assessable",
                description="Sum assessable",
                formula="sum(...)",
                inputs={"employment_income": "1800000"},
                output="1800000",
            )
        ],
        rules_applied=["sum_assessable", "final_tax"],
        rule_source_refs=[
            RuleSourceRef(id="ird-ira-2017-base", kind="source_doc"),
        ],
    )


@pytest.fixture()
def store_settings(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> AdaptiveTaxSettings:
    monkeypatch.setenv("COMP_ADAPTIVE_TAX_CALC_STORE_DIR", str(tmp_path / "calcs"))
    get_adaptive_tax_settings.cache_clear()
    settings = AdaptiveTaxSettings()
    yield settings
    get_adaptive_tax_settings.cache_clear()


def test_save_and_load_round_trip(store_settings: AdaptiveTaxSettings) -> None:
    request = CalculateTaxRequestV1(
        employment_income=Decimal("1800000"),
        param_set="current",
    )
    calc_id = save(request, _minimal_response(), settings=store_settings)
    assert uuid.UUID(calc_id)

    path = store_settings.calc_store_dir / f"{calc_id}.json"
    assert path.is_file()

    loaded = load(calc_id, settings=store_settings)
    assert loaded is not None
    assert loaded.calc_id == calc_id
    assert loaded.param_set_effective == "current"
    assert loaded.request.employment_income == Decimal("1800000")
    assert loaded.response.final_tax_lkr == "48000"
    assert loaded.response.calc_id == calc_id
    assert loaded.amendment_context is None


def test_save_with_amendment_context(store_settings: AdaptiveTaxSettings) -> None:
    request = CalculateTaxRequestV1(param_set="pre_amend_2025")
    ctx = {"rule_source_id": "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"}
    calc_id = save(
        request,
        _minimal_response(),
        settings=store_settings,
        amendment_context=ctx,
    )
    loaded = load(calc_id, settings=store_settings)
    assert loaded is not None
    assert loaded.amendment_context == ctx
    assert loaded.param_set_effective == "pre_amend_2025"


def test_load_missing_returns_none(store_settings: AdaptiveTaxSettings) -> None:
    missing = str(uuid.uuid4())
    assert load(missing, settings=store_settings) is None


def test_load_invalid_calc_id_returns_none(store_settings: AdaptiveTaxSettings) -> None:
    assert load("../etc/passwd", settings=store_settings) is None
    assert load("not-a-uuid", settings=store_settings) is None


def test_save_rejects_invalid_explicit_calc_id(
    store_settings: AdaptiveTaxSettings,
) -> None:
    with pytest.raises(ValueError, match="invalid calc_id"):
        save(
            CalculateTaxRequestV1(),
            _minimal_response(),
            settings=store_settings,
            calc_id="bad",
        )
