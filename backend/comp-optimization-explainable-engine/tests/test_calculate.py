"""Fixture calculator: 2025/26 personal 1.8M, solar min(claim, cap), WHT → payable."""

from __future__ import annotations

from sqlalchemy.orm import Session

from oe_engine_app.services.fixtures import load_extract_fixture, seed_act_document
from oe_engine_app.services.terminus import promote_act_run

TYPICAL_INCOME = {
    "employment": 1_800_000,
    "business": 0,
    "investment": 2_000_000,
    "other": 0,
    "interest": 2_000_000,
    "rents": 0,
}


def _promote_2025(db_session: Session) -> None:
    seed_act_document(db_session, source_doc_id="oee-fixture-act-2025", title="Fixture 2025")
    run = load_extract_fixture("act_extract_2025.json")
    promote_act_run(db_session, run)
    db_session.commit()


def _personal(lines: list[dict]) -> dict:
    matches = [e for e in lines if e.get("compare_group_id") == "personal_relief"]
    assert matches, "personal_relief missing"
    return matches[0]


def test_years_after_promote(client, db_session: Session) -> None:
    _promote_2025(db_session)
    response = client.get("/years")
    assert response.status_code == 200
    payload = response.json()
    assert "2025_26" in payload["assessment_years"]
    assert "2026_27" not in payload["assessment_years"]
    assert payload["year_count"] >= 1


def test_calculate_2025_26_personal_1_8m_and_slabs(client, db_session: Session) -> None:
    _promote_2025(db_session)
    response = client.post(
        "/calculate",
        json={"assessment_year": "2025_26", "income": TYPICAL_INCOME, "claims": []},
    )
    assert response.status_code == 200
    body = response.json()
    personal = _personal(body["relief_lines"])
    assert personal["applied"] == 1_800_000
    assert personal["cap"] == 1_800_000
    assert body["gross_income"] == 3_800_000
    assert body["taxable_income"] == 2_000_000
    assert body["tax_payable"] == 270_000
    assert body["slab_lines"]
    assert body["slab_lines"][0]["rate_percent"] == 6.0
    assert body["balance_payable"] == 270_000
    assert body["wht_credit"] == 0


def test_calculate_solar_min_claim_cap(client, db_session: Session) -> None:
    _promote_2025(db_session)
    listed = client.get("/reliefs/2025_26").json()["entries"]
    solar = next(e for e in listed if e["compare_group_id"] == "solar_panel_relief")
    response = client.post(
        "/calculate",
        json={
            "assessment_year": "2025_26",
            "income": TYPICAL_INCOME,
            "claims": [
                {
                    "entry_id": solar["entry_id"],
                    "amount": 900_000,
                    "affirmed": True,
                    "skipped": False,
                }
            ],
        },
    )
    assert response.status_code == 200
    line = next(
        e
        for e in response.json()["relief_lines"]
        if e["compare_group_id"] == "solar_panel_relief"
    )
    assert line["binder"] == "min(claim, cap)"
    assert line["applied"] == 600_000


def test_wht_credit_to_balance_payable(client, db_session: Session) -> None:
    _promote_2025(db_session)
    response = client.post(
        "/calculate",
        json={
            "assessment_year": "2025_26",
            "income": TYPICAL_INCOME,
            "claims": [],
            "wht_already_paid": 100_000,
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["tax_payable"] == 270_000
    assert body["wht_credit"] == 100_000
    assert body["apit_credit"] == 0
    assert body["balance_payable"] == 170_000
    assert body["slab_lines"][0]["source_doc_id"] == "oee-fixture-act-2025"


def test_apit_credit_to_balance_payable(client, db_session: Session) -> None:
    _promote_2025(db_session)
    response = client.post(
        "/calculate",
        json={
            "assessment_year": "2025_26",
            "income": TYPICAL_INCOME,
            "claims": [],
            "apit_already_paid": 80_000,
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["tax_payable"] == 270_000
    assert body["apit_already_paid"] == 80_000
    assert body["apit_credit"] == 80_000
    assert body["wht_credit"] == 0
    assert body["balance_payable"] == 190_000


def test_apit_then_wht_credits_and_refund(client, db_session: Session) -> None:
    _promote_2025(db_session)
    response = client.post(
        "/calculate",
        json={
            "assessment_year": "2025_26",
            "income": {**TYPICAL_INCOME, "apit_already_paid": 200_000},
            "claims": [],
            "wht_already_paid": 100_000,
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["tax_payable"] == 270_000
    assert body["apit_credit"] == 200_000
    assert body["wht_credit"] == 70_000
    assert body["balance_payable"] == 0
    assert body["tax_refund"] == 30_000


def test_explain_includes_trace_and_retrieve(client, db_session: Session) -> None:
    _promote_2025(db_session)
    response = client.post(
        "/explain",
        json={"assessment_year": "2025_26", "income": TYPICAL_INCOME, "claims": []},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["mode"] == "trace_retrieve"
    assert body["slab_lines"]
    assert "hits" in body
