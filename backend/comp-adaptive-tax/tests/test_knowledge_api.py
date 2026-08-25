"""Knowledge debug API tests (graph-stats / rag search)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from adaptive_tax_app.services.chroma_index import RagHit


def test_graph_stats_returns_503_when_password_missing(client: TestClient) -> None:
    with patch(
        "adaptive_tax_app.routers.knowledge.get_adaptive_tax_settings"
    ) as settings_fn:
        settings = MagicMock()
        settings.NEO4J_PASSWORD = ""
        settings.NEO4J_URI = "bolt://127.0.0.1:7687"
        settings.NEO4J_USER = "neo4j"
        settings_fn.return_value = settings
        response = client.get("/api/v1/knowledge/graph-stats")
    assert response.status_code == 503


def test_graph_stats_ok_with_mocked_driver(client: TestClient) -> None:
    session = MagicMock()
    session.run.side_effect = [
        MagicMock(
            data=lambda: [
                {"label": "TextChunk", "count": 10},
                {"label": "Concept", "count": 2},
            ]
        ),
        MagicMock(
            data=lambda: [
                {"type": "DEFINES", "count": 15},
                {"type": "APPLIES_TO", "count": 20},
                {"type": "COVERS_RELIEF", "count": 2},
                {"type": "MENTIONS", "count": 300},
            ]
        ),
        MagicMock(single=lambda: {"count": 337}),
        MagicMock(single=lambda: {"count": 37}),
        MagicMock(single=lambda: {"count": 1}),
        MagicMock(
            data=lambda: [
                {"concept_id": "qualifying_payment", "present": True},
                {"concept_id": "solar_panel_relief", "present": True},
            ]
        ),
    ]
    driver = MagicMock()
    driver.session.return_value.__enter__.return_value = session
    driver.session.return_value.__exit__.return_value = False

    with patch("adaptive_tax_app.routers.knowledge._neo4j_driver", return_value=driver):
        response = client.get("/api/v1/knowledge/graph-stats")
    assert response.status_code == 200
    body = response.json()
    assert body["calc_edge_total"] == 337
    assert body["executable_calc_edge_total"] == 37
    assert body["modifies_total"] == 1
    assert body["nodes"]["TextChunk"] == 10
    assert "MENTIONS" in body["calc_rel_types"]
    assert "required_concepts" in body
    assert body["required_concepts"]["qualifying_payment"] is True
    assert body["required_concepts"]["solar_panel_relief"] is True


def test_rag_search_ok_with_mocked_index(client: TestClient) -> None:
    index = MagicMock()
    index.search.return_value = [
        RagHit(
            chunk_id="c1",
            text="Section 52 qualifying payment",
            score=0.9,
            source_doc_id="ird-ira-2017-base",
            section_ref="Section 52",
            page=1,
            metadata={},
        ),
        RagHit(
            chunk_id="c-weak",
            text="weak",
            score=0.40,
            source_doc_id="ird-ira-2017-base",
            section_ref="Section 52",
            page=2,
            metadata={},
        ),
    ]
    with patch(
        "adaptive_tax_app.services.chroma_index.get_chroma_index",
        return_value=index,
    ):
        response = client.post(
            "/api/v1/knowledge/rag/search",
            json={
                "query": "qualifying payment",
                "section_ref": "52",
                "top_k": 3,
                "min_score": 0.55,
                "assessment_year": "2025_26",
            },
        )
    assert response.status_code == 200
    body = response.json()
    assert body["query"] == "qualifying payment"
    assert body["min_score"] == 0.55
    assert body["assessment_year"] == "2025_26"
    assert len(body["hits"]) == 1
    assert body["hits"][0]["chunk_id"] == "c1"
    assert "52" in (body["hits"][0]["section_ref"] or "")
    index.search.assert_called_once()
