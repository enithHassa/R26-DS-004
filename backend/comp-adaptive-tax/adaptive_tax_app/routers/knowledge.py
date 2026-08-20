"""Debug knowledge-store endpoints (Neo4j graph-stats + Chroma RAG search)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from adaptive_tax_app.config import get_adaptive_tax_settings
from adaptive_tax_app.schemas.legal_coverage import LegalCoverageResponseV1
from adaptive_tax_app.services.kg_client import REQUIRED_CALC_CONCEPTS
from adaptive_tax_app.services.legal_coverage import build_legal_coverage

router = APIRouter(prefix="/knowledge", tags=["knowledge"])


class RagSearchRequest(BaseModel):
    query: str = Field(..., min_length=1)
    section_ref: str | None = None
    source_doc_id: str | None = None
    top_k: int = Field(default=5, ge=1, le=20)
    # Retrieval noise floor only — NOT legal confidence (Phase 7/8).
    min_score: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Optional similarity floor (defaults to settings.RAG_MIN_SCORE when null).",
    )
    assessment_year: str | None = Field(
        default=None,
        description="Optional YA hint for clients; ranking uses legal precedence in gather_evidence.",
    )


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
    min_score: float | None = None
    assessment_year: str | None = None
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
            calc_types = (
                "DEFINES",
                "COVERS_RELIEF",
                "APPLIES_TO",
                "CONTRIBUTES_TO",
                "DEDUCTED_FROM",
                "LIMITED_BY",
                "GOVERNED_BY",
                "SUPPORTED_BY",
                "CALCULATED_USING",
                "MENTIONS",
            )
            calc_total = session.run(
                """
                MATCH ()-[r]->()
                WHERE type(r) IN $types
                RETURN count(r) AS count
                """,
                types=list(calc_types),
            ).single()
            executable_types = [
                t for t in calc_types if t != "MENTIONS"
            ]
            executable_total = session.run(
                """
                MATCH ()-[r]->()
                WHERE type(r) IN $types
                RETURN count(r) AS count
                """,
                types=executable_types,
            ).single()
            modifies = session.run(
                "MATCH ()-[r:MODIFIES]->() RETURN count(r) AS count"
            ).single()
            required_rows = session.run(
                """
                UNWIND $ids AS cid
                OPTIONAL MATCH (c:Concept {concept_id: cid})
                RETURN cid AS concept_id, c IS NOT NULL AS present
                """,
                ids=list(REQUIRED_CALC_CONCEPTS),
            ).data()
    finally:
        driver.close()

    presence = {
        str(row["concept_id"]): bool(row.get("present"))
        for row in required_rows
        if row.get("concept_id")
    }
    missing = [cid for cid, ok in presence.items() if not ok]

    return {
        "nodes": {row["label"]: row["count"] for row in nodes if row.get("label")},
        "relationships": {row["type"]: row["count"] for row in edges if row.get("type")},
        "calc_edge_total": int(calc_total["count"]) if calc_total else 0,
        "executable_calc_edge_total": (
            int(executable_total["count"]) if executable_total else 0
        ),
        "modifies_total": int(modifies["count"]) if modifies else 0,
        "calc_rel_types": list(calc_types),
        "required_concepts": presence,
        "required_concepts_missing": missing,
        "notes": (
            "calc_edge_total includes MENTIONS (Phase 5.10 breadth). "
            "Coverage is checklist-based and is not inflated by bulk MENTIONS. "
            "required_concepts lists calculator concepts that must exist in Neo4j."
        ),
    }


@router.get(
    "/legal-coverage",
    response_model=LegalCoverageResponseV1,
    summary="Legal coverage dashboard — checklist + catalog section grain (Phase 6.8)",
)
def legal_coverage(
    include_optional: bool = False,
) -> LegalCoverageResponseV1:
    """Section-grain coverage for viva / Chapter 4 export."""
    try:
        return build_legal_coverage(include_optional=include_optional)
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc


@router.post("/rag/search", response_model=RagSearchResponse)
def rag_search(body: RagSearchRequest) -> RagSearchResponse:
    """Semantic search over the embedded adaptive-tax Chroma collection."""
    settings = get_adaptive_tax_settings()
    floor = body.min_score
    if floor is None:
        floor = float(settings.RAG_MIN_SCORE)
    try:
        from adaptive_tax_app.services.chroma_index import get_chroma_index

        index = get_chroma_index()
        # Over-fetch then apply score floor client-side (noise filter only).
        raw = index.search(
            body.query,
            section_ref=body.section_ref,
            source_doc_id=body.source_doc_id,
            top_k=max(body.top_k * 4, body.top_k),
        )
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Chroma unavailable: {exc}",
        ) from exc

    hits = [
        h
        for h in raw
        if h.score is None or float(h.score) >= float(floor)
    ][: body.top_k]

    return RagSearchResponse(
        query=body.query,
        section_ref=body.section_ref,
        min_score=floor,
        assessment_year=body.assessment_year,
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
