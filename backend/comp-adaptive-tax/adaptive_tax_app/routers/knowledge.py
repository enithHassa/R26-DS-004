"""Debug knowledge-store endpoints (Neo4j graph-stats + Chroma RAG search)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from adaptive_tax_app.config import get_adaptive_tax_settings

router = APIRouter(prefix="/knowledge", tags=["knowledge"])


class RagSearchRequest(BaseModel):
    query: str = Field(..., min_length=1)
    section_ref: str | None = None
    source_doc_id: str | None = None
    top_k: int = Field(default=5, ge=1, le=20)


class RagHitOut(BaseModel):
    chunk_id: str
    text: str
    score: float | None = None
    source_doc_id: str | None = None
    section_ref: str | None = None
    page: int | None = None


class RagSearchResponse(BaseModel):
    query: str
    section_ref: str | None = None
    hits: list[RagHitOut]


def _neo4j_driver() -> Any:
    from neo4j import GraphDatabase

    settings = get_adaptive_tax_settings()
    password = (settings.NEO4J_PASSWORD or "").strip()
    if not password:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="NEO4J_PASSWORD is not set",
        )
    uri = (settings.NEO4J_URI or "bolt://127.0.0.1:7687").strip()
    if uri.startswith("neo4j://"):
        uri = "bolt://" + uri[len("neo4j://") :]
    try:
        driver = GraphDatabase.driver(uri, auth=(settings.NEO4J_USER or "neo4j", password))
        driver.verify_connectivity()
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Neo4j unavailable: {exc}",
        ) from exc
    return driver


@router.get("/graph-stats")
def graph_stats() -> dict[str, Any]:
    """Return node counts by label and relationship counts by type."""
    driver = _neo4j_driver()
    try:
        with driver.session() as session:
            nodes = session.run(
                """
                MATCH (n)
                RETURN labels(n)[0] AS label, count(*) AS count
                ORDER BY count DESC
                """
            ).data()
            edges = session.run(
                """
                MATCH ()-[r]->()
                RETURN type(r) AS type, count(*) AS count
                ORDER BY count DESC
                """
            ).data()
            calc_types = ("DEFINES", "COVERS_RELIEF", "APPLIES_TO")
            calc_total = session.run(
                """
                MATCH ()-[r]->()
                WHERE type(r) IN $types
                RETURN count(r) AS count
                """,
                types=list(calc_types),
            ).single()
            modifies = session.run(
                "MATCH ()-[r:MODIFIES]->() RETURN count(r) AS count"
            ).single()
    finally:
        driver.close()

    return {
        "nodes": {row["label"]: row["count"] for row in nodes if row.get("label")},
        "relationships": {row["type"]: row["count"] for row in edges if row.get("type")},
        "calc_edge_total": int(calc_total["count"]) if calc_total else 0,
        "modifies_total": int(modifies["count"]) if modifies else 0,
        "calc_rel_types": list(calc_types),
    }


@router.post("/rag/search", response_model=RagSearchResponse)
def rag_search(body: RagSearchRequest) -> RagSearchResponse:
    """Semantic search over the embedded adaptive-tax Chroma collection."""
    try:
        from adaptive_tax_app.services.chroma_index import get_chroma_index

        index = get_chroma_index()
        hits = index.search(
            body.query,
            section_ref=body.section_ref,
            source_doc_id=body.source_doc_id,
            top_k=body.top_k,
        )
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Chroma unavailable: {exc}",
        ) from exc

    return RagSearchResponse(
        query=body.query,
        section_ref=body.section_ref,
        hits=[
            RagHitOut(
                chunk_id=h.chunk_id,
                text=h.text,
                score=h.score,
                source_doc_id=h.source_doc_id,
                section_ref=h.section_ref,
                page=h.page,
            )
            for h in hits
        ],
    )
