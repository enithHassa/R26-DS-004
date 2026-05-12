from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import get_lm_settings
from app.main import create_app


def test_query_stub_without_corpus(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("COMP_LLM_CORPUS_JSONL", raising=False)
    monkeypatch.delenv("COMP_LLM_RETRIEVAL_BACKEND", raising=False)
    get_lm_settings.cache_clear()
    with TestClient(create_app()) as client:
        r = client.post("/api/v1/query", json={"question": "What is personal relief?"})
    assert r.status_code == 200
    body = r.json()
    assert body["retrieval_model"] == "stub-no-corpus"
    assert body["citations"] == []
    assert body["question"] == "What is personal relief?"


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
    assert "Personal relief" in body["citations"][0]["text"]
    assert body["citations"][0]["text"].endswith("...")
    assert isinstance(body["citations"][0]["score"], float)
    assert body["citations"][0].get("source_doc_id") is None


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
    assert c0["instrument_type"] == "act"
    assert c0["content_kind"] == "text"
