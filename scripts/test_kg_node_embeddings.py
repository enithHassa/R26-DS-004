"""Tests for Phase 3 Step 13 — node embedding bundles (meta + NPZ, no sentence-transformers)."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import numpy as np
import pytest

_ROOT = Path(__file__).resolve().parent
_REPO = Path(__file__).resolve().parents[1]

_spec = importlib.util.spec_from_file_location("kg_node_embeddings_lib", _ROOT / "kg_node_embeddings_lib.py")
_mod = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
_spec.loader.exec_module(_mod)


def _good_npz_meta() -> dict:
    return {
        "schema_version": "1",
        "neo4j_label": "TextChunk",
        "id_property": "chunk_id",
        "embedding_model_id": "sentence-transformers/all-MiniLM-L6-v2",
        "embedding_run_id": "run_2026-05-12_a",
        "corpus_version": "corpus_v1",
        "vector_storage": {
            "format": "npz_compressed",
            "filename": "textchunk__all-MiniLM-L6-v2.npz",
            "array_key": "embeddings",
            "ids_key": "chunk_ids",
            "dimensions": 384,
            "dtype": "float32",
            "normalized": True,
        },
    }


def test_validate_meta_npz_ok() -> None:
    errs = _mod.validate_meta(_good_npz_meta())
    assert not errs, errs


def test_validate_meta_bad_schema_version() -> None:
    m = _good_npz_meta()
    m["schema_version"] = "2"
    errs = _mod.validate_meta(m)
    assert errs and any("schema_version" in e for e in errs)


def test_validate_meta_unsafe_run_id() -> None:
    m = _good_npz_meta()
    m["embedding_run_id"] = "bad id"
    errs = _mod.validate_meta(m)
    assert errs and any("embedding_run_id" in e for e in errs)


def test_validate_meta_pending_ok() -> None:
    m = {
        "schema_version": "1",
        "neo4j_label": "TextChunk",
        "id_property": "chunk_id",
        "embedding_model_id": "sentence-transformers/all-MiniLM-L6-v2",
        "embedding_run_id": "dry-run-1",
        "vector_storage": {
            "format": "pending",
            "filename": "textchunk__all-MiniLM-L6-v2.npz",
            "array_key": "embeddings",
            "ids_key": "chunk_ids",
            "dtype": "float32",
        },
        "row_count": 42,
    }
    assert not _mod.validate_meta(m)


def test_write_load_bundle_roundtrip(tmp_path: Path) -> None:
    out = tmp_path / "bundle"
    meta = _good_npz_meta()
    chunk_ids = ["c1", "c2", "c3"]
    emb = np.random.randn(3, 384).astype(np.float32)
    _mod.write_bundle(out, meta=meta, chunk_ids=chunk_ids, embeddings=emb)

    meta2, ids2, emb2 = _mod.load_bundle(out)
    assert meta2["embedding_run_id"] == meta["embedding_run_id"]
    assert list(ids2) == chunk_ids
    assert emb2.shape == (3, 384)
    assert np.allclose(emb, emb2)


def test_load_bundle_rejects_pending(tmp_path: Path) -> None:
    out = tmp_path / "pending"
    meta = {
        "schema_version": "1",
        "neo4j_label": "TextChunk",
        "id_property": "chunk_id",
        "embedding_model_id": "m",
        "embedding_run_id": "p1",
        "vector_storage": {
            "format": "pending",
            "filename": "v.npz",
            "array_key": "embeddings",
            "ids_key": "chunk_ids",
            "dtype": "float32",
        },
    }
    out.mkdir(parents=True)
    (out / "node_embeddings_meta.json").write_text(json.dumps(meta), encoding="utf-8")
    with pytest.raises(ValueError, match="pending"):
        _mod.load_bundle(out)


def test_validate_npz_against_meta_length_mismatch() -> None:
    meta = _good_npz_meta()
    emb = np.zeros((2, 384), dtype=np.float32)
    ids = np.array(["a", "b", "c"], dtype=object)
    errs = _mod.validate_npz_against_meta(meta, embeddings=emb, ids=ids)
    assert errs and any("length mismatch" in e for e in errs)


def test_spec_json_exists() -> None:
    p = _REPO / "knowledge_graph" / "node_embeddings_v1.json"
    assert p.is_file()
    doc = json.loads(p.read_text(encoding="utf-8"))
    assert doc.get("spec_version") == "1.0.0"
    impl = doc.get("implementations", {})
    assert impl.get("python_module") == "scripts/kg_node_embeddings_lib.py"
    assert "COMP_LLM_DENSE_EMBEDDING_BUNDLE_DIR" in (impl.get("language_model_env") or "")
