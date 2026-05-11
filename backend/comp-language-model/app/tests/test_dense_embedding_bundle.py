"""Phase 3 Step 14 — dense index from precomputed node embedding bundle."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import numpy as np
import pytest

from app.services.dense_chunk_index import DenseChunkIndex

_REPO_ROOT = Path(__file__).resolve().parents[4]
_SCRIPTS = _REPO_ROOT / "scripts"


def _kg_embeddings_mod():
    spec = importlib.util.spec_from_file_location(
        "kg_node_embeddings_lib",
        _SCRIPTS / "kg_node_embeddings_lib.py",
    )
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _sample_meta() -> dict:
    return {
        "schema_version": "1",
        "neo4j_label": "TextChunk",
        "id_property": "chunk_id",
        "embedding_model_id": "sentence-transformers/all-MiniLM-L6-v2",
        "embedding_run_id": "test-bundle-1",
        "corpus_version": "corpus_v1",
        "vector_storage": {
            "format": "npz_compressed",
            "filename": "vectors.npz",
            "array_key": "embeddings",
            "ids_key": "chunk_ids",
            "dimensions": 3,
            "dtype": "float32",
            "normalized": True,
        },
    }


def test_dense_chunk_index_from_embedding_bundle_dir_loads(tmp_path: Path) -> None:
    kne = _kg_embeddings_mod()
    out = tmp_path / "b1"
    cids = ["c-a", "c-b"]
    emb = np.array([[1.0, 0.0, 0.0], [0.0, 1.0, 0.0]], dtype=np.float32)
    kne.write_bundle(out, meta=_sample_meta(), chunk_ids=cids, embeddings=emb)

    idx = DenseChunkIndex.from_embedding_bundle_dir(out)
    assert idx.size == 2
    assert idx.chunk_ids == cids
    assert idx.embeddings.shape == (2, 3)


def test_dense_chunk_index_from_bundle_search_with_mocked_query(tmp_path: Path) -> None:
    kne = _kg_embeddings_mod()
    out = tmp_path / "b2"
    cids = ["near", "far"]
    emb = np.array([[1.0, 0.0, 0.0], [0.0, 1.0, 0.0]], dtype=np.float32)
    kne.write_bundle(out, meta=_sample_meta(), chunk_ids=cids, embeddings=emb)

    idx = DenseChunkIndex.from_embedding_bundle_dir(out)

    def fake_encode(_q: str) -> np.ndarray:
        return np.array([[1.0, 0.0, 0.0]], dtype=np.float32)

    idx._encode_query = fake_encode  # type: ignore[method-assign]
    hits = idx.search("anything", k=2)
    assert [h[0] for h in hits] == ["near", "far"]


def test_nlu_uses_embedding_bundle_when_configured(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
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
    kne = _kg_embeddings_mod()
    bundle = tmp_path / "bundle"
    # Same chunk order as a minimal dense encode would need — use tiny random + orthonormal-ish for test stability
    from sentence_transformers import SentenceTransformer

    model_name = "sentence-transformers/all-MiniLM-L6-v2"
    model = SentenceTransformer(model_name)
    texts = [
        "Personal relief for the year of assessment shall be allowed as specified.",
        "Unrelated cooking recipes.",
    ]
    emb = model.encode(
        texts,
        normalize_embeddings=True,
        show_progress_bar=False,
        convert_to_numpy=True,
    )
    meta = _sample_meta()
    meta["embedding_model_id"] = model_name
    meta["vector_storage"]["dimensions"] = int(emb.shape[1])
    meta["vector_storage"]["filename"] = "textchunk__all-MiniLM-L6-v2.npz"
    kne.write_bundle(
        bundle,
        meta=meta,
        chunk_ids=["t::relief", "t::other"],
        embeddings=np.asarray(emb, dtype=np.float32),
    )

    monkeypatch.setenv("COMP_LLM_CORPUS_JSONL", str(corpus))
    monkeypatch.setenv("COMP_LLM_RETRIEVAL_BACKEND", "dense")
    monkeypatch.setenv("COMP_LLM_DENSE_MODEL", model_name)
    monkeypatch.setenv("COMP_LLM_DENSE_EMBEDDING_BUNDLE_DIR", str(bundle))

    from app.config import get_lm_settings

    get_lm_settings.cache_clear()
    from fastapi.testclient import TestClient

    from app.main import create_app

    with TestClient(create_app()) as client:
        r = client.post(
            "/api/v1/nlu/parse",
            json={"utterance": "How does personal relief work for the year of assessment?", "top_k": 2},
        )
    assert r.status_code == 200
    body = r.json()
    assert body["corpus_loaded"] is True
    assert body["retrieval_hits"][0]["chunk_id"] == "t::relief"
