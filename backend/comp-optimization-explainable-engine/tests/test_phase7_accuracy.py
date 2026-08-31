"""Phase 7: goldens, retrieve quote-match, compare, mismatch, /ready coverage.

Uses Phase 6 extract JSON under models/opt-explain-engine/extracted/ — not fixtures
and not Adaptive Tax approved/rates.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from sqlalchemy.orm import Session

from backend.shared.config.settings import PROJECT_ROOT
from db.models import OeEngineChunk
from oe_engine_app.schemas.extract import ExtractRun
from oe_engine_app.services.embedder import HashEmbedder
from oe_engine_app.services.fixtures import seed_act_document
from oe_engine_app.services.mismatch_queue import list_flags
from oe_engine_app.services.retrieve import hybrid_retrieve
from oe_engine_app.services.terminus import apply_extract_terminus, promote_act_run

EXTRACT_DIR = PROJECT_ROOT / "models" / "opt-explain-engine" / "extracted"

TYPICAL_INCOME = {
    "employment": 1_800_000,
    "business": 0,
    "investment": 2_000_000,
    "other": 0,
    "interest": 2_000_000,
    "rents": 0,
}

EXCEL_2023_24_INCOME = {
    "employment": 2_000_000,
    "business": 0,
    "investment": 0,
    "other": 0,
    "interest": 500_000,
    "rents": 0,
}

PHASE6_COMPARE_ACTS = (
    "oee-act-24-2017",
    "oee-act-10-2021",
    "oee-act-45-2022",
    "oee-act-02-2025",
)

PHASE6_CALC_ACTS = (
    "oee-act-10-2021",
    "oee-act-45-2022",
    "oee-act-02-2025",
)


def _current_json(source_doc_id: str) -> Path:
    path = EXTRACT_DIR / f"{source_doc_id}__current.json"
    if not path.is_file():
        pytest.skip(f"missing Phase 6 extract {path}")
    return path


def load_extracted(source_doc_id: str) -> ExtractRun:
    payload = json.loads(_current_json(source_doc_id).read_text(encoding="utf-8"))
    return ExtractRun.model_validate(payload)


def promote_extracted(session: Session, source_doc_id: str) -> dict:
    seed_act_document(session, source_doc_id=source_doc_id, title=source_doc_id)
    return promote_act_run(session, load_extracted(source_doc_id))


def promote_acts(session: Session, source_doc_ids: tuple[str, ...]) -> None:
    for source_doc_id in source_doc_ids:
        promote_extracted(session, source_doc_id)
    session.commit()


def _personal(lines: list[dict]) -> dict:
    matches = [row for row in lines if row.get("compare_group_id") == "personal_relief"]
    assert matches, "personal_relief missing"
    return matches[0]


def test_calculate_2025_26_personal_1_8m_from_extracted_acts(client, db_session: Session) -> None:
    promote_acts(db_session, PHASE6_CALC_ACTS)
    response = client.post(
        "/calculate",
        json={"assessment_year": "2025_26", "income": TYPICAL_INCOME, "claims": []},
    )
    assert response.status_code == 200
    body = response.json()
    personal = _personal(body["relief_lines"])
    assert personal["applied"] == 1_800_000
    assert personal["cap"] == 1_800_000
    assert personal["source_doc_id"] == "oee-act-02-2025"
    assert body["gross_income"] == 3_800_000
    assert body["taxable_income"] == 2_000_000
    assert body["tax_payable"] == 270_000
    assert [row["rate_percent"] for row in body["slab_lines"]] == [6.0, 18.0, 24.0, 30.0, 36.0]
    assert body["slab_lines"][0]["source_doc_id"] == "oee-act-02-2025"


def test_calculate_solar_min_claim_cap_from_extracted_10_2021(
    client, db_session: Session
) -> None:
    promote_acts(db_session, PHASE6_CALC_ACTS)
    listed = client.get("/reliefs/2025_26").json()["entries"]
    solar = next(row for row in listed if row["compare_group_id"] == "solar_panel_relief")
    assert solar["cap_amount"] in {"600000", 600000}
    assert solar["source_doc_id"] == "oee-act-10-2021"
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
    body = response.json()
    line = next(
        row
        for row in body["relief_lines"]
        if row["compare_group_id"] == "solar_panel_relief"
    )
    assert line["binder"] == "min(claim, cap)"
    assert line["applied"] == 600_000
    assert body["taxable_income"] == 1_400_000
    assert body["tax_payable"] == 132_000


def test_calculate_excel_2023_24_wht_path_extracted_slabs(client, db_session: Session) -> None:
    """Employment + personal 1.2M + WHT credit; slabs from Act 45/2022, not xlsx."""
    promote_acts(db_session, PHASE6_CALC_ACTS)
    response = client.post(
        "/calculate",
        json={
            "assessment_year": "2023_24",
            "income": EXCEL_2023_24_INCOME,
            "claims": [],
            "wht_already_paid": 50_000,
        },
    )
    assert response.status_code == 200
    body = response.json()
    personal = _personal(body["relief_lines"])
    assert personal["applied"] == 1_200_000
    assert personal["source_doc_id"] == "oee-act-45-2022"
    assert body["gross_income"] == 2_000_000
    assert body["taxable_income"] == 800_000
    assert [row["rate_percent"] for row in body["slab_lines"]][:2] == [6.0, 12.0]
    assert body["slab_lines"][0]["source_doc_id"] == "oee-act-45-2022"
    assert body["tax_payable"] == 66_000
    assert body["wht_credit"] == 50_000
    assert body["balance_payable"] == 16_000
    assert body["tax_refund"] == 0


def test_compare_personal_caps_after_phase6_promotes(client, db_session: Session) -> None:
    promote_acts(db_session, PHASE6_COMPARE_ACTS)
    response = client.get("/compare", params={"compare_group_id": "personal_relief"})
    assert response.status_code == 200
    body = response.json()
    caps = {row["assessment_year"]: row.get("cap_amount") for row in body["series"]}
    assert caps["2018_19"] == "500000"
    assert caps["2020_21"] == "3000000"
    assert caps["2022_23"] == "2250000"
    assert caps["2023_24"] == "1200000"
    assert caps["2025_26"] == "1800000"
    assert "2026_27" not in caps
    solar = client.get("/compare", params={"compare_group_id": "solar_panel_relief"}).json()
    solar_caps = {row["assessment_year"]: row.get("cap_amount") for row in solar["series"]}
    assert solar_caps["2020_21"] in {None, ""}
    assert solar_caps["2021_22"] == "600000"
    assert solar_caps["2025_26"] == "600000"


def test_mismatch_tab_open_flags_from_consolidated_extract(
    client, db_session: Session
) -> None:
    promote_acts(db_session, PHASE6_COMPARE_ACTS)
    apply_extract_terminus(db_session, load_extracted("oee-consolidated-2025"))
    db_session.commit()
    response = client.get("/mismatches")
    assert response.status_code == 200
    flags = response.json()["flags"]
    assert flags
    open_flags = [row for row in flags if row["status"] == "open"]
    keys = {(row["compare_group_id"], row["year"]) for row in open_flags}
    assert ("first_schedule_rates", "2020_21") in keys
    assert ("solar_panel_relief", "2020_21") in keys
    listed = list_flags(db_session)
    assert len(listed) == response.json()["flag_count"]


def test_ready_chunk_coverage_ok_after_promote(client, db_session: Session) -> None:
    promote_extracted(db_session, "oee-act-02-2025")
    db_session.commit()
    response = client.get("/ready")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["checks"]["chunk_coverage"] is True
    assert payload["checks"]["rag_index"] is True
    assert payload["checks"]["promoted_without_chunks"] == []


def test_ready_degraded_when_promoted_act_has_no_chunks(client, db_session: Session) -> None:
    promote_extracted(db_session, "oee-act-02-2025")
    db_session.query(OeEngineChunk).delete()
    db_session.commit()
    response = client.get("/ready")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "degraded"
    assert payload["checks"]["chunk_coverage"] is False
    assert "oee-act-02-2025" in payload["checks"]["promoted_without_chunks"]


def _seed_quote_chunks(session: Session) -> HashEmbedder:
    cap = (
        "(v) Rs. 1,800,000, for each year of assessment commencing on or after April 1, 2025,"
    )
    slab = "Not exceeding Rs. 500,000\t6% of the amount in excess of Rs.0"
    eligibility = (
        "in the case of a resident individual who has acquired solar panels "
        "to fix on hispremises and connected to the nationalgrid"
    )
    distractor = "A company shall be taxed at thirty percent on gains from betting and gaming."
    rows = (
        ("oee-act-02-2025", "c-cap", cap, "Fifth Schedule"),
        ("oee-act-45-2022", "c-slab", slab, "First Schedule"),
        ("oee-act-10-2021", "c-elig", eligibility, "Fifth Schedule"),
        ("oee-act-24-2017", "c-noise", distractor, "Part II"),
    )
    embedder = HashEmbedder()
    texts = [text for _sid, _cid, text, _sec in rows]
    vectors = embedder.embed_batch(texts)
    for (source_doc_id, chunk_id, text, section), vec in zip(rows, vectors, strict=True):
        seed_act_document(
            session, source_doc_id=source_doc_id, title=source_doc_id, with_chunk=False
        )
        session.add(
            OeEngineChunk(
                chunk_id=chunk_id,
                source_doc_id=source_doc_id,
                channel="text_stream",
                page=1,
                chunk_index=9,
                text=text,
                section_ref=section,
                embedding_json=json.dumps(vec),
                embedding_model=embedder.model,
            )
        )
    session.commit()
    return embedder


def test_retrieve_cap_quote_ranks_1800000_chunk(db_session: Session) -> None:
    embedder = _seed_quote_chunks(db_session)
    query = "Rs. 1,800,000 commencing on or after April 1, 2025"
    hits = hybrid_retrieve(
        db_session,
        query=query,
        query_embedding=embedder.embed_batch([query])[0],
        top_k=3,
    )
    assert hits
    assert hits[0].chunk_id == "c-cap"
    assert "1,800,000" in hits[0].text
    assert hits[0].source_doc_id == "oee-act-02-2025"


def test_retrieve_slab_quote_ranks_first_schedule_6pct(db_session: Session) -> None:
    embedder = _seed_quote_chunks(db_session)
    query = "Not exceeding Rs. 500,000 6% First Schedule"
    hits = hybrid_retrieve(
        db_session,
        query=query,
        query_embedding=embedder.embed_batch([query])[0],
        top_k=3,
    )
    assert hits
    assert hits[0].chunk_id == "c-slab"
    assert "6%" in hits[0].text
    assert hits[0].source_doc_id == "oee-act-45-2022"


def test_retrieve_eligibility_quote_ranks_solar_panels(db_session: Session) -> None:
    embedder = _seed_quote_chunks(db_session)
    query = "resident individual who has acquired solar panels"
    hits = hybrid_retrieve(
        db_session,
        query=query,
        query_embedding=embedder.embed_batch([query])[0],
        top_k=3,
    )
    assert hits
    assert hits[0].chunk_id == "c-elig"
    assert "solar panels" in hits[0].text.lower()
    assert hits[0].source_doc_id == "oee-act-10-2021"
