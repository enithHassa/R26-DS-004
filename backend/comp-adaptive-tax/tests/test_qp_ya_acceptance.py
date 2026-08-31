"""Phase 6.3 viva acceptance — YA-aware QP catalog, Why?/explain, Sec 52(4) CF."""

from __future__ import annotations

from decimal import Decimal

from fastapi.testclient import TestClient

from adaptive_tax_app.main import create_app
from adaptive_tax_app.schemas.calculate import CalculateTaxRequestV1, FilingLineV1
from adaptive_tax_app.services.filing_catalog import (
    clear_filing_catalog_cache,
    get_filing_catalog_for_year,
)
from adaptive_tax_app.services.provenance import clear_provenance_cache
from adaptive_tax_app.services.request_normalize import normalize_request
from adaptive_tax_app.services.rule_engine import calculate, default_file_kg


def setup_function() -> None:
    clear_filing_catalog_cache()
    clear_provenance_cache()


def _qp_ids(year: str) -> set[str]:
    catalog = get_filing_catalog_for_year(year)  # type: ignore[arg-type]
    qp = next(c for c in catalog.cards if c.card_id == "qualifying_payments")
    return {f.component_id for f in qp.fields}


def test_catalog_ya_2024_25_film_gov_no_bf_no_solar() -> None:
    ids = _qp_ids("2024_25")
    assert "qp_film_production" in ids
    assert "qp_cinema_construction" in ids
    assert "qp_government_sri_lanka" in ids
    assert "qp_local_authority" in ids
    assert "qp_government_fund" in ids
    assert "qp_brought_forward" not in ids
    assert not any("solar" in i for i in ids)


def test_catalog_ya_2025_26_bf_and_sec52_4_metadata_only_on_eligible() -> None:
    catalog = get_filing_catalog_for_year("2025_26")
    qp = next(c for c in catalog.cards if c.card_id == "qualifying_payments")
    by_id = {f.component_id: f for f in qp.fields}
    assert "qp_brought_forward" in by_id
    assert "qp_film_production" in by_id
    assert not any("solar" in i for i in by_id)
    assert by_id["qp_government_sri_lanka"].sec52_4_carry_forward is True
    assert by_id["qp_government_fund"].sec52_4_carry_forward is True
    assert by_id["qp_local_authority"].sec52_4_carry_forward is False
    assert by_id["qp_other_listed_funds"].sec52_4_carry_forward is False
    assert by_id["qp_samurdhi_shop"].sec52_4_carry_forward is False
    assert by_id["qp_government_sri_lanka"].display_name == (
        "Donation to Government of Sri Lanka"
    )
    assert by_id["qp_government_fund"].display_name == (
        "Donation to Government-established Fund"
    )


def test_normalize_ignores_bf_line_on_2024_25() -> None:
    req = CalculateTaxRequestV1(
        assessment_year="2024_25",
        resident_status="resident",
        employment_income=Decimal("3000000"),
        filing_lines=[
            FilingLineV1(component_id="qp_government_sri_lanka", amount=Decimal("100000")),
            FilingLineV1(component_id="qp_brought_forward", amount=Decimal("500000")),
        ],
    )
    result = normalize_request(req)
    assert result.request.qualifying_payment_brought_forward == Decimal("0")
    assert any("ya_inactive" in w or "not_active" in w for w in result.warnings) or (
        result.request.qualifying_payments == Decimal("100000")
    )


def test_calculate_2024_25_sec52_4_not_applicable_and_trace_ya() -> None:
    result = calculate(
        CalculateTaxRequestV1(
            assessment_year="2024_25",
            resident_status="resident",
            employment_income="3000000",
            filing_lines=[
                FilingLineV1(component_id="qp_government_sri_lanka", amount="2000000"),
            ],
        ),
        kg=default_file_kg(),
    )
    assert result.qualifying_payment_carry_forward_out is None
    assert result.qualifying_payment_summary is not None
    assert result.qualifying_payment_summary.sec52_4_applicable is False
    gov = next(
        c
        for c in result.qualifying_payment_categories
        if c.component_id == "qp_government_sri_lanka"
    )
    assert gov.sec52_4_eligible is False
    assert gov.carry_forward_amount == "0"
    assert gov.deducted_this_year == "2000000"
    assert gov.undeducted_amount == "0"
    ya_steps = [s for s in result.calculation_trace if s.step_id.startswith("qp_category:")]
    assert ya_steps
    assert all(s.inputs.get("assessment_year") == "2024_25" for s in ya_steps)


def test_allocation_invariant_cf_equals_sum_eligible_only() -> None:
    """When income covers all allowables, Sec 52(4) CF is zero (no aggregate pool)."""
    result = calculate(
        CalculateTaxRequestV1(
            assessment_year="2025_26",
            resident_status="resident",
            employment_income="5000000",
            filing_lines=[
                FilingLineV1(component_id="qp_government_sri_lanka", amount="2000000"),
                FilingLineV1(component_id="qp_samurdhi_shop", amount="500000"),
            ],
        ),
        kg=default_file_kg(),
    )
    by_id = {c.component_id: c for c in result.qualifying_payment_categories}
    cf = Decimal(result.qualifying_payment_carry_forward_out or "0")
    assert cf == Decimal("0")
    assert by_id["qp_samurdhi_shop"].carry_forward_amount == "0"
    ded = next(s for s in result.calculation_trace if s.step_id == "deduct_qualifying_payment")
    assert ded.inputs.get("allowed") == "2500000"


def test_no_fictional_aggregate_cap_room_becomes_carry_forward() -> None:
    """CF must not arise from removed aggregate-cap headroom."""
    result = calculate(
        CalculateTaxRequestV1(
            assessment_year="2025_26",
            resident_status="resident",
            employment_income="3000000",
            filing_lines=[
                FilingLineV1(component_id="qp_government_sri_lanka", amount="1000000"),
            ],
        ),
        kg=default_file_kg(),
    )
    assert result.qualifying_payment_carry_forward_out in (None, "0")
    gov = next(
        c
        for c in result.qualifying_payment_categories
        if c.component_id == "qp_government_sri_lanka"
    )
    assert gov.undeducted_amount == "0"
    assert gov.carry_forward_amount == "0"
    assert result.qualifying_payment_summary is not None
    assert result.qualifying_payment_summary.section_52_cap is None
    assert result.qualifying_payment_summary.unused_after_sec52 is None


def test_explain_1b_v_statutory_scope_and_ya_switch() -> None:
    client = TestClient(create_app())
    ya24 = client.get(
        "/api/v1/filing-catalog/qp_government_fund/explain",
        params={"assessment_year": "2024_25"},
    )
    assert ya24.status_code == 200
    b24 = ya24.json()
    assert b24["assessment_year"] == "2024_25"
    assert b24["sec52_4_status"] == "Not applicable for this assessment year"
    assert "1(b)(v)" in (b24.get("statutory_scope") or "")
    assert "fund established by the Government of Sri Lanka" in (
        b24.get("statutory_scope") or ""
    )

    ya25 = client.get(
        "/api/v1/filing-catalog/qp_government_fund/explain",
        params={"assessment_year": "2025_26"},
    )
    assert ya25.status_code == 200
    b25 = ya25.json()
    assert b25["assessment_year"] == "2025_26"
    assert b25["sec52_4_status"] == "Eligible under Sec 52(4)"
    assert "IR Act No. 11 of 2026" in (b25.get("source_label") or "")
    assert "1(b)(v)" in (b25.get("statutory_scope") or "")
    assert "vi" in (b25.get("statutory_scope") or "").lower()
    quote = b25.get("source_quote") or ""
    assert quote  # Act evidence present

    other = client.get(
        "/api/v1/filing-catalog/qp_other_listed_funds/explain",
        params={"assessment_year": "2025_26"},
    )
    assert other.status_code == 200
    assert other.json()["sec52_4_status"] == "Not eligible under Sec 52(4)"

    catalog24 = client.get(
        "/api/v1/filing-catalog",
        params={"assessment_year": "2024_25"},
    ).json()
    catalog25 = client.get(
        "/api/v1/filing-catalog",
        params={"assessment_year": "2025_26"},
    ).json()
    qp24 = next(c for c in catalog24["cards"] if c["card_id"] == "qualifying_payments")
    qp25 = next(c for c in catalog25["cards"] if c["card_id"] == "qualifying_payments")
    ids24 = {f["component_id"] for f in qp24["fields"]}
    ids25 = {f["component_id"] for f in qp25["fields"]}
    assert "qp_brought_forward" not in ids24
    assert "qp_brought_forward" in ids25
    assert not any("solar" in i for i in ids24 | ids25)
    # Human labels on the wire (UI primary chrome).
    gov = next(f for f in qp25["fields"] if f["component_id"] == "qp_government_sri_lanka")
    assert gov["display_name"] == "Donation to Government of Sri Lanka"


def test_calculate_api_allocation_fields_and_summary_status() -> None:
    client = TestClient(create_app())
    resp = client.post(
        "/api/v1/calculate",
        json={
            "assessment_year": "2025_26",
            "resident_status": "resident",
            "employment_income": "5000000",
            "filing_lines": [
                {"component_id": "qp_government_sri_lanka", "amount": "2000000"},
                {"component_id": "qp_samurdhi_shop", "amount": "500000"},
            ],
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["qualifying_payment_summary"]["sec52_4_applicable"] is True
    cats = {c["component_id"]: c for c in body["qualifying_payment_categories"]}
    for key in (
        "claimed_amount",
        "allowable_amount",
        "deducted_this_year",
        "undeducted_amount",
        "sec52_4_eligible",
        "carry_forward_amount",
    ):
        assert key in cats["qp_government_sri_lanka"]
    cf = Decimal(body["qualifying_payment_carry_forward_out"] or "0")
    assert cf == sum(Decimal(c["carry_forward_amount"] or "0") for c in body["qualifying_payment_categories"])

    resp24 = client.post(
        "/api/v1/calculate",
        json={
            "assessment_year": "2024_25",
            "resident_status": "resident",
            "employment_income": "3000000",
            "filing_lines": [
                {"component_id": "qp_government_sri_lanka", "amount": "600000"},
            ],
        },
    )
    assert resp24.status_code == 200
    b24 = resp24.json()
    assert b24["qualifying_payment_summary"]["sec52_4_applicable"] is False
    assert b24["qualifying_payment_carry_forward_out"] is None
