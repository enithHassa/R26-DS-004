"""NLU / retrieval API contracts (Phase 2).

M5-frozen JSON Schemas for clients: ``evaluation/frozen/nlu_parse_*.schema.json``.
When this module changes, update those files and ``evaluation/frozen/phase2_M5_baseline.json``.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class RetrievalHit(BaseModel):
    chunk_id: str
    score: float = Field(
        ...,
        description="Similarity or rank score (TF-IDF cosine or dense cosine, depending on retrieval backend).",
    )
    source_doc_id: str | None = Field(
        default=None,
        description="LawInstrument key from corpus (Phase 3 Step 15); aligns with Neo4j when loaded.",
    )
    section_uid: str | None = Field(
        default=None,
        description="Section key from ETL formula (Phase 3 Step 15); null when section_label missing.",
    )
    section_label: str | None = Field(
        default=None,
        description="Materialized section label used to build section_uid.",
    )
    tier: str | None = Field(default=None, description="Corpus tier when present.")
    instrument_type: str | None = Field(default=None, description="Corpus instrument_type when present.")
    content_kind: str | None = Field(
        default=None,
        description="text/table/etc. from corpus when present.",
    )


class NLUParseRequest(BaseModel):
    utterance: str = Field(..., min_length=1)
    top_k: int | None = Field(default=None, ge=1, le=50)
    intent_hint: str | None = Field(
        default=None,
        description="Optional intent label from routing; echoed when no intent model is loaded.",
    )


class NLUParseResponse(BaseModel):
    utterance: str
    intent: str | None = Field(
        default=None,
        description="Echo of request intent_hint when provided (upstream routing label).",
    )
    predicted_intent: str | None = Field(
        default=None,
        description="Intent from TF-IDF centroid model when COMP_LLM_INTENT_BENCHMARK_JSONL is loaded.",
    )
    intent_model: str | None = Field(
        default=None,
        description="Set to tfidf-centroid when an intent classifier is active; null otherwise.",
    )
    retrieval_hits: list[RetrievalHit]
    model: str = Field(
        ...,
        description="Retrieval mode: tfidf-baseline, dense-baseline, or stub-no-corpus.",
    )
    corpus_loaded: bool
