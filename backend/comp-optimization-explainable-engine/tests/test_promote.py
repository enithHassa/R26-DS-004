"""HTTP terminus: Guide/Consolidated promote is 400; Act without chunks is 409."""

from __future__ import annotations

from sqlalchemy.orm import Session

from oe_engine_app.services.fixtures import seed_act_document


def test_promote_guide_http_400(client, monkeypatch) -> None:
    monkeypatch.setattr(
        "oe_engine_app.routers.promote.document_tier",
        lambda _session, _sid: "guide",
    )
    response = client.post("/promote", json={"source_doc_id": "oee-guide-ira"})
    assert response.status_code == 400
    assert "Act-only" in response.json()["detail"]


def test_promote_consolidated_http_400(client, monkeypatch) -> None:
    monkeypatch.setattr(
        "oe_engine_app.routers.promote.document_tier",
        lambda _session, _sid: "consolidated",
    )
    response = client.post("/promote", json={"source_doc_id": "oee-consolidated-2025"})
    assert response.status_code == 400


def test_promote_act_without_chunks_http_409(client, db_session: Session) -> None:
    seed_act_document(
        db_session, source_doc_id="oee-fixture-act-2025", with_chunk=False
    )
    db_session.commit()
    response = client.post(
        "/promote",
        json={
            "source_doc_id": "oee-fixture-act-2025",
            "extraction_run_id": "fixture-2025-act",
        },
    )
    assert response.status_code == 409
    assert "no chunks" in response.json()["detail"]
