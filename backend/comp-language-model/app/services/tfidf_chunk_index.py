"""TF-IDF retrieval index over corpus_v1 JSONL (Phase 2 baseline)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity


class TfidfChunkIndex:
    """In-memory TF-IDF index over chunk text."""

    def __init__(self, chunk_ids: list[str], texts: list[str]) -> None:
        if len(chunk_ids) != len(texts):
            raise ValueError("chunk_ids and texts length mismatch")
        self._chunk_ids = chunk_ids
        self._vectorizer = TfidfVectorizer(
            max_features=50_000,
            ngram_range=(1, 2),
            min_df=1,
            sublinear_tf=True,
        )
        self._matrix = self._vectorizer.fit_transform(texts)

    @classmethod
    def from_jsonl(cls, path: Path) -> TfidfChunkIndex:
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
        return cls(chunk_ids, texts)

    @property
    def size(self) -> int:
        return len(self._chunk_ids)

    def search(self, query: str, k: int) -> list[tuple[str, float]]:
        if not query.strip():
            return []
        k = min(k, len(self._chunk_ids))
        q = self._vectorizer.transform([query])
        sims = cosine_similarity(q, self._matrix)[0]
        top_idx = np.argpartition(-sims, k - 1)[:k]
        top_idx = top_idx[np.argsort(-sims[top_idx])]
        return [(self._chunk_ids[int(i)], float(sims[int(i)])) for i in top_idx]
