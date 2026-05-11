from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import get_lm_settings
from app.main import create_app


def test_nlu_parse_stub_without_corpus(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("COMP_LLM_CORPUS_JSONL", raising=False)
    monkeypatch.delenv("COMP_LLM_RETRIEVAL_BACKEND", raising=False)
    monkeypatch.delenv("COMP_LLM_DENSE_MODEL", raising=False)
    get_lm_settings.cache_clear()
    with TestClient(create_app()) as client:
        r = client.post("/api/v1/nlu/parse", json={"utterance": "What is personal relief?"})
    assert r.status_code == 200
    body = r.json()
    assert body["corpus_loaded"] is False
    assert body["model"] == "stub-no-corpus"
    assert body["retrieval_hits"] == []
    assert body.get("predicted_intent") is None
    assert body.get("intent_model") is None


def test_nlu_parse_with_corpus(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    corpus = tmp_path / "corpus.jsonl"
    rows = [
        {"chunk_id": "t::a", "text": "Personal relief for the year of assessment is defined herein."},
        {"chunk_id": "t::b", "text": "Recipes for coconut sambal unrelated to tax."},
    ]
    with corpus.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row) + "\n")

    monkeypatch.setenv("COMP_LLM_CORPUS_JSONL", str(corpus))
    monkeypatch.delenv("COMP_LLM_RETRIEVAL_BACKEND", raising=False)
    get_lm_settings.cache_clear()
    with TestClient(create_app()) as client:
        r = client.post(
            "/api/v1/nlu/parse",
            json={"utterance": "personal relief year of assessment", "top_k": 2},
        )
    assert r.status_code == 200
    body = r.json()
    assert body["corpus_loaded"] is True
    assert body["model"] == "tfidf-baseline"
    assert len(body["retrieval_hits"]) == 2
    ids = [h["chunk_id"] for h in body["retrieval_hits"]]
    assert "t::a" in ids
    assert ids[0] == "t::a"
    assert body.get("predicted_intent") is None
    assert body.get("intent_model") is None


def test_nlu_parse_intent_benchmark_without_corpus(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    bench = tmp_path / "bench.jsonl"
    bench.write_text(
        json.dumps(
            {
                "example_id": "e1",
                "task_id": "intent_classification",
                "utterance": "personal relief for this year",
                "gold_intent": "personal_relief",
            }
        )
        + "\n"
        + json.dumps(
            {
                "example_id": "e2",
                "task_id": "intent_classification",
                "utterance": "tax resident days in sri lanka",
                "gold_intent": "residence_scope",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.delenv("COMP_LLM_CORPUS_JSONL", raising=False)
    monkeypatch.delenv("COMP_LLM_RETRIEVAL_BACKEND", raising=False)
    monkeypatch.setenv("COMP_LLM_INTENT_BENCHMARK_JSONL", str(bench))
    get_lm_settings.cache_clear()
    with TestClient(create_app()) as client:
        r = client.post("/api/v1/nlu/parse", json={"utterance": "question about personal relief amount"})
    assert r.status_code == 200
    body = r.json()
    assert body["corpus_loaded"] is False
    assert body["predicted_intent"] == "personal_relief"
    assert body["intent_model"] == "tfidf-centroid"


def test_nlu_parse_corpus_and_intent_benchmark(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    corpus = tmp_path / "corpus.jsonl"
    corpus.write_text(
        json.dumps({"chunk_id": "t::a", "text": "Personal relief rules."}) + "\n", encoding="utf-8"
    )
    bench = tmp_path / "bench.jsonl"
    bench.write_text(
        json.dumps(
            {
                "example_id": "e1",
                "task_id": "intent_classification",
                "utterance": "relief for individuals",
                "gold_intent": "personal_relief",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("COMP_LLM_CORPUS_JSONL", str(corpus))
    monkeypatch.delenv("COMP_LLM_RETRIEVAL_BACKEND", raising=False)
    monkeypatch.setenv("COMP_LLM_INTENT_BENCHMARK_JSONL", str(bench))
    get_lm_settings.cache_clear()
    with TestClient(create_app()) as client:
        r = client.post("/api/v1/nlu/parse", json={"utterance": "tell me about relief for individuals"})
    assert r.status_code == 200
    body = r.json()
    assert body["corpus_loaded"] is True
    assert body["intent_model"] == "tfidf-centroid"
    assert body["predicted_intent"] == "personal_relief"
    assert len(body["retrieval_hits"]) >= 1


def test_nlu_parse_dense_retrieval_backend(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    pytest.importorskip("sentence_transformers")
    corpus = tmp_path / "corpus.jsonl"
    corpus.write_text(
        json.dumps(
            {
                "chunk_id": "t::relief",
                "text": "Personal relief for the year of assessment shall be allowed as specified.",
            }
        )
        + "\n"
        + json.dumps({"chunk_id": "t::other", "text": "Unrelated cooking recipes."})
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("COMP_LLM_CORPUS_JSONL", str(corpus))
    monkeypatch.setenv("COMP_LLM_RETRIEVAL_BACKEND", "dense")
    monkeypatch.setenv("COMP_LLM_DENSE_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
    get_lm_settings.cache_clear()
    with TestClient(create_app()) as client:
        r = client.post(
            "/api/v1/nlu/parse",
            json={"utterance": "How does personal relief work for the year of assessment?", "top_k": 2},
        )
    assert r.status_code == 200
    body = r.json()
    assert body["corpus_loaded"] is True
    assert body["model"] == "dense-baseline"
    assert len(body["retrieval_hits"]) == 2
    assert body["retrieval_hits"][0]["chunk_id"] == "t::relief"
