"""M5 gate: example payloads must match frozen NLU parse contract (app/schemas/nlu_v1.py)."""

from __future__ import annotations

from pathlib import Path

from app.schemas.nlu_v1 import NLUParseRequest, NLUParseResponse, RetrievalHit
from app.schemas.query_v1 import Citation, QueryRequest, QueryResponse

_REPO_ROOT = Path(__file__).resolve().parents[4]
_FROZEN_BASELINE = _REPO_ROOT / "evaluation" / "frozen" / "phase2_M5_baseline.json"
_FROZEN_RESPONSE_SCHEMA = _REPO_ROOT / "evaluation" / "frozen" / "nlu_parse_response.schema.json"
_FROZEN_REQUEST_SCHEMA = _REPO_ROOT / "evaluation" / "frozen" / "nlu_parse_request.schema.json"
_FROZEN_QUERY_REQUEST = _REPO_ROOT / "evaluation" / "frozen" / "query_request.schema.json"
_FROZEN_QUERY_RESPONSE = _REPO_ROOT / "evaluation" / "frozen" / "query_response.schema.json"


def test_m5_frozen_artifacts_exist() -> None:
    assert _FROZEN_BASELINE.is_file()
    assert _FROZEN_RESPONSE_SCHEMA.is_file()
    assert _FROZEN_REQUEST_SCHEMA.is_file()
    assert _FROZEN_QUERY_REQUEST.is_file()
    assert _FROZEN_QUERY_RESPONSE.is_file()


def test_nlu_parse_request_examples_validate() -> None:
    NLUParseRequest.model_validate({"utterance": "What is personal relief?"})
    NLUParseRequest.model_validate(
        {"utterance": "x", "top_k": 5, "intent_hint": "personal_relief"}
    )


def test_nlu_parse_response_examples_validate() -> None:
    NLUParseResponse.model_validate(
        {
            "utterance": "q",
            "intent": None,
            "predicted_intent": None,
            "intent_model": None,
            "retrieval_hits": [],
            "model": "stub-no-corpus",
            "corpus_loaded": False,
        }
    )
    NLUParseResponse.model_validate(
        {
            "utterance": "q",
            "intent": "hint",
            "predicted_intent": "personal_relief",
            "intent_model": "tfidf-centroid",
            "retrieval_hits": [RetrievalHit(chunk_id="a::1", score=0.9)],
            "model": "tfidf-baseline",
            "corpus_loaded": True,
        }
    )
    NLUParseResponse.model_validate(
        {
            "utterance": "q",
            "intent": None,
            "predicted_intent": None,
            "intent_model": None,
            "retrieval_hits": [RetrievalHit(chunk_id="a::1", score=0.85)],
            "model": "dense-baseline",
            "corpus_loaded": True,
        }
    )
    NLUParseResponse.model_validate(
        {
            "utterance": "q",
            "intent": None,
            "predicted_intent": None,
            "intent_model": None,
            "retrieval_hits": [
                RetrievalHit(
                    chunk_id="a::1",
                    score=0.9,
                    source_doc_id="doc1",
                    section_uid="doc1::sec::part_a",
                    section_label="Part A",
                    tier="A",
                    instrument_type="act",
                    content_kind="text",
                )
            ],
            "model": "tfidf-baseline",
            "corpus_loaded": True,
        }
    )


def test_pydantic_json_schema_has_m5_fields() -> None:
    schema = NLUParseResponse.model_json_schema()
    props = schema.get("properties", {})
    for key in (
        "utterance",
        "intent",
        "predicted_intent",
        "intent_model",
        "retrieval_hits",
        "model",
        "corpus_loaded",
    ):
        assert key in props


def test_query_request_examples_validate() -> None:
    QueryRequest.model_validate({"question": "What is personal relief?"})
    QueryRequest.model_validate({"question": "x", "top_k": 5})


def test_query_response_examples_validate() -> None:
    QueryResponse.model_validate(
        {
            "question": "q",
            "top_k": 8,
            "citations": [],
            "retrieval_model": "stub-no-corpus",
        }
    )
    QueryResponse.model_validate(
        {
            "question": "q",
            "top_k": 4,
            "citations": [Citation(chunk_id="a::1", score=0.9, text="excerpt")],
            "retrieval_model": "tfidf-baseline",
        }
    )
    QueryResponse.model_validate(
        {
            "question": "q",
            "top_k": 4,
            "citations": [
                Citation(
                    chunk_id="a::1",
                    score=0.9,
                    text="excerpt",
                    source_doc_id="doc1",
                    section_uid="doc1::sec::x",
                    tier="B",
                )
            ],
            "retrieval_model": "dense-baseline",
        }
    )
