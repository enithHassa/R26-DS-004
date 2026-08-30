from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import get_lm_settings
from app.main import create_app


def _disable_domain_gate(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("COMP_LLM_DOMAIN_GATE_ENABLED", "false")


def test_query_stub_without_corpus(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    missing = tmp_path / "no_corpus.jsonl"
    monkeypatch.setenv("COMP_LLM_CORPUS_JSONL", str(missing))
    monkeypatch.delenv("COMP_LLM_RETRIEVAL_BACKEND", raising=False)
    _disable_domain_gate(monkeypatch)
    get_lm_settings.cache_clear()
    with TestClient(create_app()) as client:
        r = client.post("/api/v1/query", json={"question": "What is personal relief?"})
    assert r.status_code == 200
    body = r.json()
    assert body["retrieval_model"] == "stub-no-corpus"
    assert body["citations"] == []
    assert body["proof_map"] is not None
    assert body["normalized_question"] == "What is personal relief?"


def test_query_returns_citations_with_text(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    corpus = tmp_path / "corpus.jsonl"
    long_text = "Personal relief for the year of assessment is defined in this statute section. " * 20
    corpus.write_text(
        json.dumps({"chunk_id": "t::relief", "text": long_text.strip()}) + "\n"
        + json.dumps({"chunk_id": "t::noise", "text": "Cooking recipes."}) + "\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("COMP_LLM_CORPUS_JSONL", str(corpus))
    monkeypatch.delenv("COMP_LLM_RETRIEVAL_BACKEND", raising=False)
    monkeypatch.setenv("COMP_LLM_QUERY_CITATION_MAX_CHARS", "300")
    get_lm_settings.cache_clear()
    with TestClient(create_app()) as client:
        r = client.post(
            "/api/v1/query",
            json={"question": "personal relief year of assessment", "top_k": 2},
        )
    assert r.status_code == 200
    body = r.json()
    assert body["retrieval_model"] == "tfidf-baseline"
    assert len(body["citations"]) == 2
    assert body["citations"][0]["chunk_id"] == "t::relief"
    assert body["proof_map"] is not None
    assert len(body["proof_map"]["steps"]) >= 3


def test_query_citations_include_kg_join_fields(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    corpus = tmp_path / "corpus.jsonl"
    corpus.write_text(
        json.dumps(
            {
                "chunk_id": "t::relief",
                "text": "Personal relief year of assessment statute.",
                "source_doc_id": "ird-act-join",
                "section_ref": ["Division 1"],
                "tier": "A",
                "instrument_type": "act",
                "content_kind": "text",
            }
        )
        + "\n"
        + json.dumps({"chunk_id": "t::noise", "text": "Recipes.", "source_doc_id": "cookbook"})
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("COMP_LLM_CORPUS_JSONL", str(corpus))
    monkeypatch.delenv("COMP_LLM_RETRIEVAL_BACKEND", raising=False)
    get_lm_settings.cache_clear()
    with TestClient(create_app()) as client:
        r = client.post(
            "/api/v1/query",
            json={"question": "personal relief assessment year statute", "top_k": 1},
        )
    assert r.status_code == 200
    c0 = r.json()["citations"][0]
    assert c0["chunk_id"] == "t::relief"
    assert c0["source_doc_id"] == "ird-act-join"
    assert c0["section_label"] == "Division 1"
    assert c0["section_uid"] == "ird-act-join::sec::division_1"
    assert c0["tier"] == "A"


def test_chat_creates_session(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    corpus = tmp_path / "corpus.jsonl"
    corpus.write_text(
        json.dumps({"chunk_id": "t::relief", "text": "Personal relief year of assessment."}) + "\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("COMP_LLM_CORPUS_JSONL", str(corpus))
    monkeypatch.setenv("COMP_LLM_ANSWER_SYNTHESIS_ENABLED", "false")
    get_lm_settings.cache_clear()
    with TestClient(create_app()) as client:
        r = client.post(
            "/api/v1/chat",
            json={"message": "personal relief assessment year", "synthesize_answer": False},
        )
    assert r.status_code == 200
    body = r.json()
    assert body["session_id"]
    assert body["turn_index"] == 1
    assert body["query_result"]["citations"]
    assert body["proof_map"] is not None
