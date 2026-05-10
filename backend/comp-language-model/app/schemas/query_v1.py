"""Law-grounded query with citations (Phase 2 Step 14).

Frozen JSON Schemas: ``evaluation/frozen/query_*.schema.json``.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class QueryRequest(BaseModel):
    question: str = Field(..., min_length=1)
    top_k: int | None = Field(default=None, ge=1, le=50)


class Citation(BaseModel):
    chunk_id: str
    score: float = Field(..., description="Retrieval score (cosine similarity).")
    text: str = Field(
        ...,
        description="Excerpt of chunk text from corpus (truncated per server citation cap).",
    )
    source_doc_id: str | None = Field(
        default=None,
        description="LawInstrument key from corpus (Phase 3 Step 15).",
    )
    section_uid: str | None = Field(default=None, description="Section key matching ETL / Neo4j.")
    section_label: str | None = Field(default=None, description="Section label used for section_uid.")
    tier: str | None = Field(default=None, description="Corpus tier when present.")
    instrument_type: str | None = Field(default=None, description="Corpus instrument_type when present.")
    content_kind: str | None = Field(default=None, description="text/table from corpus when present.")


class QueryResponse(BaseModel):
    question: str
    top_k: int
    citations: list[Citation]
    retrieval_model: str = Field(
        ...,
        description="Same retrieval backend id as NLU parse: tfidf-baseline, dense-baseline, or stub-no-corpus.",
    )
