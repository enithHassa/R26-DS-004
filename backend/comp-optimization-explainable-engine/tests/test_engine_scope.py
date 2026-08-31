"""engine_scope inference and promote reject of non-individual entities."""

from __future__ import annotations

from sqlalchemy.orm import Session

import pytest

from db.year_views import OeEnginePromotedEntity
from oe_engine_app.schemas.extract import ExtractRun, RateBandEntity, ReliefEntity
from oe_engine_app.services.engine_scope import infer_engine_scope, is_promotable_scope
from oe_engine_app.services.extract import extract_window
from oe_engine_app.services.extract_llm import (
    Pass1ActPayload,
    Pass1Eligibility,
    Pass1RateBand,
    Pass1Relief,
)
from oe_engine_app.services.fixtures import seed_act_document
from oe_engine_app.services.terminus import promote_act_run
from oe_engine_app.services.windows import DocText, FocusWindow
from tests.test_extract_dry import QUOTE, _FakeLLM, _tiny_doc


def test_individual_applies_to() -> None:
    assert (
        infer_engine_scope(applies_to="resident or non-resident individual")
        == "individual"
    )


def test_trust_fund_applies_to_is_other() -> None:
    assert (
        infer_engine_scope(
            applies_to="Employees' Trust Fund, an approved provident or pension fund"
        )
        == "other"
    )


def test_trust_applies_to_is_other() -> None:
    assert infer_engine_scope(applies_to="a trust") == "other"


def test_company_applies_to_is_other() -> None:
    assert infer_engine_scope(applies_to="a company") == "other"


def test_ngo_applies_to_is_other() -> None:
    assert infer_engine_scope(applies_to="a non-governmental organization") == "other"
    assert (
        infer_engine_scope(compare_group_id="ngo_income_tax_rate") == "other"
    )


def test_trustee_in_personal_relief_stays_individual() -> None:
    assert (
        infer_engine_scope(
            compare_group_id="personal_relief",
            eligibility_text=(
                "an individual except that an individual who is a trustee, "
                "receiver, executor or liquidator shall not be entitled"
            ),
        )
        == "individual"
    )


def test_donation_to_institution_by_individual_stays_individual() -> None:
    assert (
        infer_engine_scope(
            display_name="Approved charity donation by individual",
            eligibility_text=(
                "in the case of an individual, one-third of the taxable income "
                "of the individual or Rupees seventy five thousand, whichever is less"
            ),
        )
        == "individual"
    )


def test_refund_does_not_count_as_fund() -> None:
    assert infer_engine_scope(eligibility_text="tax refund of personal relief") == "individual"


def test_terminal_benefit_gratuity_text_stays_individual() -> None:
    assert (
        infer_engine_scope(
            compare_group_id="terminal_benefit_tax_rate",
            eligibility_text="retiring gratuity paid under the Act",
        )
        == "individual"
    )


def test_extract_sets_scope_on_rate_band() -> None:
    stream = "FIRST SCHEDULE\nTax rates for a resident individual.\n"
    tables = "Taxable Income | Tax Payable\nNot Exceeding Rs. 600,000 | 4%"
    doc = DocText(
        source_doc_id="oee-act-fixture",
        title="Fixture Act",
        tier="act",
        stream=stream,
        tables_blob=tables,
        page_spans=[(1, 0, len(stream))],
        tables_by_page={1: tables},
    )
    window = FocusWindow(
        window_id="first_schedule",
        heading="First Schedule",
        start=0,
        end=len(stream),
        stream_slice=stream,
        tables_slice=tables,
        page_start=1,
        page_end=1,
    )
    payload = Pass1ActPayload(
        reliefs=[],
        rate_bands=[
            Pass1RateBand(
                band_index=1,
                band_label="Taxable Income",
                lower="0",
                upper="600000",
                rate_percent="4",
                applies_to="Employees' Trust Fund",
                section_ref="First Schedule",
                act_name="Fixture Act",
                effective_from="2023-04-01",
                quote="Not Exceeding Rs. 600,000 | 4%",
                compare_group_id="trust_fund_tax_rate",
            )
        ],
    )
    entities = extract_window(doc=doc, window=window, llm=_FakeLLM(payload), dry_run=False)
    parsed = RateBandEntity.model_validate(entities[0])
    assert parsed.engine_scope == "other"
    assert is_promotable_scope(entities[0]) is False


def test_extract_sets_individual_on_personal_relief() -> None:
    doc, window = _tiny_doc()
    payload = Pass1ActPayload(
        reliefs=[
            Pass1Relief(
                compare_group_id="personal_relief",
                display_name="Personal relief",
                paragraph_ref="2(a)",
                section_ref="Fifth Schedule",
                act_name="Fixture Act",
                cap_amount="1200000",
                unit="lkr",
                quote=QUOTE,
                eligibility=Pass1Eligibility(
                    text="Available to a resident individual",
                    quote=QUOTE,
                ),
                required_evidence=[],
                filing_line="",
                stacking="",
                effective_from="",
                effective_to="",
            )
        ],
        rate_bands=[],
    )
    entities = extract_window(doc=doc, window=window, llm=_FakeLLM(payload), dry_run=False)
    parsed = ReliefEntity.model_validate(entities[0])
    assert parsed.engine_scope == "individual"


def test_promote_rejects_other_scope_even_when_included(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        "oe_engine_app.services.terminus.archive_previous_and_diff",
        lambda _payload: None,
    )
    seed_act_document(db_session, source_doc_id="oee-test-scope-a")
    run = ExtractRun(
        extraction_run_id="scope-t1",
        source_doc_id="oee-test-scope-a",
        tier="act",
        terminus="review_then_promote",
        model="gpt-4o",
        entities=[
            {
                "entity_kind": "rate_band",
                "entry_id": "etf-1",
                "compare_group_id": "trust_fund_tax_rate",
                "applies_to": "Employees' Trust Fund",
                "rate_percent": "14",
                "band_index": 1,
                "included": True,
                "engine_scope": "other",
            },
            {
                "entity_kind": "relief",
                "entry_id": "personal-1",
                "compare_group_id": "personal_relief",
                "display_name": "Personal relief",
                "eligibility": {"text": "Resident individual personal relief"},
                "cap_amount": "1800000",
                "included": True,
                "engine_scope": "individual",
            },
        ],
    )
    result = promote_act_run(db_session, run)
    db_session.commit()
    rows = db_session.query(OeEnginePromotedEntity).all()
    assert result["excluded_other_scope"] == 1
    assert result["entity_count"] == 1
    assert [row.entry_id for row in rows] == ["personal-1"]


def test_stored_individual_tag_cannot_override_fund_inference(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        "oe_engine_app.services.terminus.archive_previous_and_diff",
        lambda _payload: None,
    )
    seed_act_document(db_session, source_doc_id="oee-test-scope-b")
    run = ExtractRun(
        extraction_run_id="scope-t2",
        source_doc_id="oee-test-scope-b",
        tier="act",
        terminus="review_then_promote",
        model="gpt-4o",
        entities=[
            {
                "entity_kind": "rate_band",
                "entry_id": "etf-lied",
                "compare_group_id": "first_schedule_rates",
                "applies_to": "Employees' Trust Fund",
                "rate_percent": "14",
                "band_index": 1,
                "included": True,
                "engine_scope": "individual",
            }
        ],
    )
    result = promote_act_run(db_session, run)
    db_session.commit()
    assert result["entity_count"] == 0
    assert result["excluded_other_scope"] == 1
    assert db_session.query(OeEnginePromotedEntity).count() == 0
