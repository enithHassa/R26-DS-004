"""Dense embedding retrieval over corpus_v1 JSONL (sentence-transformers, Phase 2 Step 11)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np


class DenseChunkIndex:
    """In-memory cosine retrieval using normalized sentence embeddings."""

    def __init__(
        self,
        chunk_ids: list[str],
        embeddings: np.ndarray,
        model_name: str,
        *,
        model: object | None = None,
    ) -> None:
        if len(chunk_ids) != len(embeddings):
            raise ValueError("chunk_ids and embeddings length mismatch")
        self._chunk_ids = chunk_ids
        self._emb = np.asarray(embeddings, dtype=np.float32)
        self._model_name = model_name
        self._model = model

    @property
    def model_name(self) -> str:
        return self._model_name

    @classmethod
    def from_jsonl(
        cls,
        path: Path,
        *,
        model_name: str = "sentence-transformers/all-MiniLM-L6-v2",
        batch_size: int = 64,
        device: str | None = None,
    ) -> DenseChunkIndex:
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as e:  # pragma: no cover - optional dependency
            raise ImportError(
                "Dense retrieval requires sentence-transformers. "
                "Install: pip install -r backend/requirements-retrieval-dense.txt"
            ) from e

        chunk_ids: list[str] = []
        texts: list[str] = []
        with path.open(encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                obj: dict[str, Any] = json.loads(line)
                cid = obj.get("chunk_id")
                if not cid:
                    continue
                chunk_ids.append(str(cid))
                texts.append(str(obj.get("text") or ""))
        if not chunk_ids:
            raise ValueError(f"no chunks loaded from {path}")

        model = SentenceTransformer(model_name, device=device)
        emb = model.encode(
            texts,
            batch_size=batch_size,
            normalize_embeddings=True,
            show_progress_bar=False,
            convert_to_numpy=True,
        )
        return cls(chunk_ids, emb, model_name, model=model)

    @classmethod
    def from_embedding_bundle_dir(
        cls,
        bundle_dir: Path,
        *,
        query_model_name: str | None = None,
    ) -> DenseChunkIndex:
        """Load corpus vectors from a Step 13 bundle; query encoding uses ``query_model_name`` (SentenceTransformer).

        ``query_model_name`` defaults to ``embedding_model_id`` in ``node_embeddings_meta.json``.
        If both are set and differ, a warning is logged (query side uses ``query_model_name``).
        """
        from app.services.node_embedding_bundle import load_bundle_arrays
        from backend.shared.utils.logging import logger

        meta, chunk_ids, emb = load_bundle_arrays(bundle_dir)
        meta_model = str(meta.get("embedding_model_id") or "").strip()
        qm = (query_model_name or meta_model).strip()
        if not qm:
            raise ValueError(
                "Dense bundle: set embedding_model_id in meta or pass query_model_name / COMP_LLM_DENSE_MODEL"
            )
        if query_model_name and meta_model and meta_model != query_model_name:
            logger.warning(
                "Dense embedding bundle was built with embedding_model_id={!r} but "
                "query encoding uses COMP_LLM_DENSE_MODEL={!r} (cosine scores assume matched spaces).",
                meta_model,
                query_model_name,
            )
        return cls(chunk_ids, emb, qm, model=None)

    @property
    def size(self) -> int:
        return len(self._chunk_ids)

    @property
    def chunk_ids(self) -> list[str]:
        """Stable graph join keys (same order as ``embeddings`` rows)."""
        return list(self._chunk_ids)

    @property
    def embeddings(self) -> np.ndarray:
        """Matrix shape (n_chunks, dim), float32; L2-normalized when built via ``from_jsonl``."""
        return self._emb

    def _encode_query(self, query: str) -> np.ndarray:
        if self._model is None:
            try:
                from sentence_transformers import SentenceTransformer
            except ImportError as e:  # pragma: no cover
                raise ImportError(
                    "Dense retrieval requires sentence-transformers. "
                    "Install: pip install -r backend/requirements-retrieval-dense.txt"
                ) from e
            self._model = SentenceTransformer(self._model_name)

        q = self._model.encode(
            [query],
            normalize_embeddings=True,
            show_progress_bar=False,
            convert_to_numpy=True,
        )
        return np.asarray(q, dtype=np.float32)

    def search(self, query: str, k: int) -> list[tuple[str, float]]:
        if not query.strip():
            return []
        k = min(k, len(self._chunk_ids))
        q = self._encode_query(query).reshape(-1)
        sims = (self._emb @ q.reshape(-1)).ravel()
        top_idx = np.argpartition(-sims, k - 1)[:k]
        top_idx = top_idx[np.argsort(-sims[top_idx])]
        return [(self._chunk_ids[int(i)], float(sims[int(i)])) for i in top_idx]
