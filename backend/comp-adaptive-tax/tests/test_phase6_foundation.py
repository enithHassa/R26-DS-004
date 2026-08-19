"""Phase 6.0–6.3 — filing catalog, normalize, knowledge_versions."""

from __future__ import annotations

from decimal import Decimal

from fastapi.testclient import TestClient

from adaptive_tax_app.main import create_app
from adaptive_tax_app.schemas.calculate import CalculateTaxRequestV1, FilingLineV1
from adaptive_tax_app.schemas.extracted_rule import ExtractedRule, classify_engine_support
from adaptive_tax_app.services.filing_catalog import (
    clear_filing_catalog_cache,
    get_filing_catalog_for_year,
    knowledge_versions_from_catalog,
    list_unsupported_components,
)
from adaptive_tax_app.services.provenance import clear_provenance_cache
from adaptive_tax_app.services.request_normalize import normalize_request
from adaptive_tax_app.services.rule_engine import calculate, default_file_kg


def setup_function() -> None:
    clear_filing_catalog_cache()
    clear_provenance_cache()


def test_filing_catalog_employment_investment_and_qp_for_ya() -> None:
    catalog = get_filing_catalog_for_year("2024_25")
    assert catalog.catalog_version == "v1"
    assert catalog.act_version == "ird-consolidated-2025"
    card_ids = {c.card_id for c in catalog.cards}
    assert {
        "employment",
        "business",
        "investment",
        "other_income",
        "qualifying_payments",
        "tax_credits",
        "statutory_reliefs",
    } <= card_ids
    emp = next(c for c in catalog.cards if c.card_id == "employment")
    biz = next(c for c in catalog.cards if c.card_id == "business")
    inv = next(c for c in catalog.cards if c.card_id == "investment")
    other = next(c for c in catalog.cards if c.card_id == "other_income")
    qp = next(c for c in catalog.cards if c.card_id == "qualifying_payments")
    assert "emp_salary" in {f.component_id for f in emp.fields}
    biz_ids = {f.component_id for f in biz.fields}
    assert {
        "biz_net_profits",
        "biz_gross",
        "biz_deductions",
        "biz_capital_allowances",
    } <= biz_ids
    assert "inv_dividends" in {f.component_id for f in inv.fields}
    other_ids = {f.component_id for f in other.fields}
    assert {"oth_residual", "oth_custom", "oth_final_withholding"} <= other_ids
    residual = next(f for f in other.fields if f.component_id == "oth_residual")
    assert residual.legal_confidence == "medium"
    assert residual.confidence_basis == "interpretive"
    assert "residual" in (residual.confidence_reason or "").lower()
    qp_ids = {f.component_id for f in qp.fields}
    assert "qp_government_sri_lanka" in qp_ids
    assert "qp_local_authority" in qp_ids
    assert "qp_government_fund" in qp_ids
    assert "qp_other_listed_funds" in qp_ids
    assert "qp_approved_charitable" in qp_ids
    assert "qp_samurdhi_shop" in qp_ids
    assert "qp_film_production" in qp_ids
    statutory = next(c for c in catalog.cards if c.card_id == "statutory_reliefs")
    statutory_ids = {f.component_id for f in statutory.fields}
    assert "relief_solar_panel" in statutory_ids
    assert "relief_rent" in statutory_ids
    assert "donations" not in card_ids
    charity = next(f for f in qp.fields if f.component_id == "qp_approved_charitable")
    gov = next(f for f in qp.fields if f.component_id == "qp_government_sri_lanka")
    local = next(f for f in qp.fields if f.component_id == "qp_local_authority")
    uni = next(f for f in qp.fields if f.component_id == "qp_university_hei")
    fund = next(f for f in qp.fields if f.component_id == "qp_government_fund")
    assert charity.ui_group == "donations"
    assert gov.ui_group == "donations"
    assert local.ui_group == "donations"
    assert uni.ui_group == "donations"
    assert fund.ui_group == "donations"
    assert "qp_brought_forward" not in qp_ids
    assert "qp_other_sec52" not in qp_ids
    assert "qp_gov_local_authority" not in qp_ids
    assert not any("solar" in i for i in qp_ids)
    review = next(f for f in qp.fields if f.component_id == "qp_unclassified_review")
    assert review.legal_confidence == "medium"
    gov = next(f for f in qp.fields if f.component_id == "qp_government_sri_lanka")
    assert gov.sec52_4_carry_forward is True
    local = next(f for f in qp.fields if f.component_id == "qp_local_authority")
    assert local.sec52_4_carry_forward is False
    catalog_25 = get_filing_catalog_for_year("2025_26")
    qp25 = next(c for c in catalog_25.cards if c.card_id == "qualifying_payments")
    qp25_ids = {f.component_id for f in qp25.fields}
    assert "qp_brought_forward" in qp25_ids
    assert "qp_film_production" in qp25_ids
    assert not any("solar" in i for i in qp25_ids)


def test_unsupported_queue_lists_pending_qp_rows() -> None:
    rows = list_unsupported_components()
    ids = {r.component_id for r in rows}
    assert "qp_bank_merger" in ids
    # Combined film/cinema placeholder retired; typed 1(f) lines are supported.


def test_filing_catalog_api_and_explain() -> None:
    client = TestClient(create_app())
    resp = client.get("/api/v1/filing-catalog", params={"assessment_year": "2025_26"})
    assert resp.status_code == 200
    body = resp.json()
    card_ids = {c["card_id"] for c in body["cards"]}
    assert {"employment", "investment", "qualifying_payments"} <= card_ids

    unsupported = client.get("/api/v1/filing-catalog/unsupported")
    assert unsupported.status_code == 200
    uns = unsupported.json()
    uns_ids = {row["component_id"] for row in uns["items"]}
    assert "qp_bank_merger" in uns_ids

    explain = client.get("/api/v1/filing-catalog/emp_housing_allowance/explain")
    assert explain.status_code == 200
    data = explain.json()
    assert data["treatment"] == "include"
    assert data["section"] == "5"
    assert data["paragraph"] == "2(b)"
    assert data["legal_confidence"] == "high"
    assert data["confidence_basis"] == "direct_section"
    assert data["source_quote"]
    assert data["section_uid"] == "ird-ira-2017-base::sec::section_5"
    assert data["concept_id"] == "emp_housing_allowance"
    assert data["kg_nodes"]
    assert data["act_version_label"]

    inv_explain = client.get("/api/v1/filing-catalog/inv_dividends/explain")
    assert inv_explain.status_code == 200
    assert inv_explain.json()["section"] == "7"

    qp_explain = client.get(
        "/api/v1/filing-catalog/qp_government_fund/explain",
        params={"assessment_year": "2025_26"},
    )
    assert qp_explain.status_code == 200
    qp_body = qp_explain.json()
    assert qp_body["section"] == "52"
    assert qp_body["assessment_year"] == "2025_26"
    assert qp_body["sec52_4_status"] == "Eligible under Sec 52(4)"
    assert "1(b)(v)" in (qp_body.get("statutory_scope") or "")
    assert "any other government-related" in (qp_body.get("statutory_scope") or "").lower() or (
        "Not any other" in (qp_body.get("statutory_scope") or "")
    )

    missing = client.get("/api/v1/filing-catalog/not_a_real_field/explain")
    assert missing.status_code == 404


def test_normalize_employment_lines_win_over_scalar() -> None:
    req = CalculateTaxRequestV1(
        employment_income=Decimal("9999999"),
        filing_lines=[
            FilingLineV1(component_id="emp_salary", amount=Decimal("1000000")),
            FilingLineV1(component_id="emp_bonus", amount=Decimal("200000")),
            FilingLineV1(component_id="emp_medical_benefits", amount=Decimal("50000")),
            FilingLineV1(component_id="emp_final_withholding", amount=Decimal("10000")),
        ],
    )
    result = normalize_request(req)
    assert result.used_filing_lines is True
    assert result.request.employment_income == Decimal("1200000")
    assert result.request.employment_final_withholding == Decimal("10000")
    assert result.head_subtotals["employment_exempt"] == Decimal("50000")


def test_normalize_investment_lines_win_over_scalar() -> None:
    req = CalculateTaxRequestV1(
        investment_income=Decimal("9999999"),
        investment_final_withholding=Decimal("1"),
        filing_lines=[
            FilingLineV1(component_id="inv_dividends", amount=Decimal("1000000")),
            FilingLineV1(component_id="inv_interest", amount=Decimal("800000")),
            FilingLineV1(component_id="inv_final_withholding", amount=Decimal("200000")),
        ],
    )
    result = normalize_request(req)
    assert result.used_filing_lines is True
    assert result.request.investment_income == Decimal("1800000")
    assert result.request.investment_final_withholding == Decimal("200000")


def test_normalize_qp_and_donation_lines() -> None:
    req = CalculateTaxRequestV1(
        qualifying_payments=Decimal("9"),
        donations=Decimal("9"),
        filing_lines=[
            FilingLineV1(component_id="qp_government_sri_lanka", amount=Decimal("500000")),
            FilingLineV1(component_id="qp_other_sec52", amount=Decimal("100000")),
            FilingLineV1(component_id="don_approved_charitable", amount=Decimal("200000")),
            FilingLineV1(component_id="qp_bank_merger", amount=Decimal("999999")),
        ],
    )
    result = normalize_request(req)
    assert result.used_filing_lines is True
    # Legacy Other maps to review-only — does not inflate Sec 52 scalar.
    assert result.request.qualifying_payments == Decimal("700000")
    assert result.request.donations == Decimal("0")
    assert any("legacy_qp_other_mapped_to_unclassified_review" in w for w in result.warnings)
    assert any("legacy_don_approved_charitable_mapped_to_qp_approved_charitable" in w for w in result.warnings)
    assert any("unsupported_ignored:qp_bank_merger" in w for w in result.warnings)
    assert any(r.component_id == "qp_unclassified_review" for r in result.component_trace)


def test_calculate_with_filing_lines_stamps_knowledge_versions() -> None:
    req = CalculateTaxRequestV1(
        assessment_year="2024_25",
        resident_status="resident",
        filing_lines=[FilingLineV1(component_id="emp_salary", amount="1800000")],
        qualifying_payments="0",
        donations="0",
    )
    out = calculate(req, kg=default_file_kg())
    assert out.knowledge_versions is not None
    assert out.knowledge_versions.catalog_version == "v1"
    assert "aggregate_employment_components" in out.rules_applied
    scalar = calculate(
        CalculateTaxRequestV1(employment_income="1800000"),
        kg=default_file_kg(),
    )
    assert out.final_tax_lkr == scalar.final_tax_lkr


def test_calculate_investment_components_match_scalar() -> None:
    out = calculate(
        CalculateTaxRequestV1(
            assessment_year="2024_25",
            resident_status="resident",
            filing_lines=[
                FilingLineV1(component_id="inv_dividends", amount="1000000"),
                FilingLineV1(component_id="inv_interest", amount="800000"),
            ],
        ),
        kg=default_file_kg(),
    )
    assert "aggregate_investment_components" in out.rules_applied
    scalar = calculate(
        CalculateTaxRequestV1(investment_income="1800000"),
        kg=default_file_kg(),
    )
    assert out.final_tax_lkr == scalar.final_tax_lkr


def test_calculate_qp_components_match_scalar() -> None:
    out = calculate(
        CalculateTaxRequestV1(
            assessment_year="2024_25",
            resident_status="resident",
            employment_income="3000000",
            filing_lines=[
                FilingLineV1(component_id="qp_government_sri_lanka", amount="600000"),
            ],
        ),
        kg=default_file_kg(),
    )
    assert "aggregate_qualifying_payment_components" in out.rules_applied
    assert "evaluate_qualifying_payment_categories" in out.rules_applied
    assert out.qualifying_payment_summary is not None
    assert out.qualifying_payment_summary.final_allowable_deduction == "600000"
    assert out.qualifying_payment_summary.sec52_4_applicable is False
    assert out.qualifying_payment_carry_forward_out is None
    scalar = calculate(
        CalculateTaxRequestV1(
            employment_income="3000000",
            qualifying_payments="600000",
        ),
        kg=default_file_kg(),
    )
    assert out.final_tax_lkr == scalar.final_tax_lkr


def test_qp_approved_charitable_category_cap() -> None:
    out = calculate(
        CalculateTaxRequestV1(
            assessment_year="2024_25",
            resident_status="resident",
            employment_income="3000000",
            filing_lines=[
                FilingLineV1(component_id="qp_approved_charitable", amount="500000"),
            ],
        ),
        kg=default_file_kg(),
    )
    cat = next(
        c
        for c in out.qualifying_payment_categories
        if c.component_id == "qp_approved_charitable"
    )
    assert cat.claimed == "500000"
    assert cat.allowable == "75000"
    assert cat.disallowed == "425000"
    assert cat.status == "partially_allowed"
    assert out.qualifying_payment_summary is not None
    assert out.qualifying_payment_summary.total_allowable_before_sec52 == "75000"


def test_qp_unclassified_not_deducted() -> None:
    out = calculate(
        CalculateTaxRequestV1(
            assessment_year="2024_25",
            resident_status="resident",
            employment_income="3000000",
            filing_lines=[
                FilingLineV1(component_id="qp_unclassified_review", amount="400000"),
                FilingLineV1(component_id="qp_samurdhi_shop", amount="100000"),
            ],
        ),
        kg=default_file_kg(),
    )
    review = next(
        c
        for c in out.qualifying_payment_categories
        if c.component_id == "qp_unclassified_review"
    )
    assert review.allowable == "0"
    assert review.status == "needs_review"
    assert out.qualifying_payment_summary is not None
    assert out.qualifying_payment_summary.final_allowable_deduction == "100000"
    assert out.qualifying_payment_summary.total_needs_review == "400000"


def test_qp_film_shared_one_third_pool() -> None:
    # Assessable 3_000_000 → 1/3 = 1_000_000 shared across 1(f) lines.
    out = calculate(
        CalculateTaxRequestV1(
            assessment_year="2024_25",
            resident_status="resident",
            employment_income="3000000",
            filing_lines=[
                FilingLineV1(component_id="qp_film_production", amount="5000000"),
                FilingLineV1(component_id="qp_cinema_upgrading", amount="2000000"),
            ],
        ),
        kg=default_file_kg(),
    )
    by_id = {c.component_id: c for c in out.qualifying_payment_categories}
    assert by_id["qp_film_production"].allowable == "1000000"
    assert by_id["qp_cinema_upgrading"].allowable == "0"
    assert out.qualifying_payment_summary is not None
    assert out.qualifying_payment_summary.total_allowable_before_sec52 == "1000000"


def test_scalar_request_still_works_without_filing_lines() -> None:
    out = calculate(
        CalculateTaxRequestV1(employment_income="1800000"),
        kg=default_file_kg(),
    )
    assert out.knowledge_versions is not None
    assert out.component_trace == []
    assert out.final_tax_lkr


def test_classify_unsupported_engine_handler() -> None:
    rule = ExtractedRule(
        section="99",
        rule_type="definition",
        source_quote="x" * 40,
        executable=True,
        engine_handler="digital_asset_tax_handler",
    )
    stamped = classify_engine_support(rule)
    assert stamped.engine_support == "unsupported"


def test_knowledge_versions_helper() -> None:
    versions = knowledge_versions_from_catalog(
        assessment_year="2025_26", param_set="current"
    )
    assert versions["catalog_version"] == "v1"
    assert "2025_26" in versions["rule_pack_version"]
    assert versions["extraction_version"] == "bootstrap-other-income-catalog-v1"
