"""Hybrid retrieve: TF-IDF keyword + embedding cosine."""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from typing import Any

from sqlalchemy.orm import Session

from db.models import OeEngineChunk


@dataclass
class RetrieveHit:
    chunk_id: str
    source_doc_id: str
    channel: str
    page: int
    text: str
    score: float
    keyword_score: float
    semantic_score: float
    section_ref: str | None


def _cosine(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    n1 = math.sqrt(sum(x * x for x in a))
    n2 = math.sqrt(sum(y * y for y in b))
    if n1 == 0 or n2 == 0:
        return 0.0
    return dot / (n1 * n2)


def _load_rows(
    session: Session,
    source_doc_id: str | None,
) -> list[OeEngineChunk]:
    query = session.query(OeEngineChunk)
    if source_doc_id:
        query = query.filter(OeEngineChunk.source_doc_id == source_doc_id)
    return query.all()


def keyword_scores(query: str, texts: list[str]) -> list[float]:
    if not texts:
        return []
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.metrics.pairwise import cosine_similarity

    vectorizer = TfidfVectorizer(
        max_features=4000,
        lowercase=True,
        ngram_range=(1, 2),
    )
    matrix = vectorizer.fit_transform(texts)
    query_vec = vectorizer.transform([query])
    return [float(x) for x in cosine_similarity(query_vec, matrix)[0]]


def hybrid_retrieve(
    session: Session,
    *,
    query: str,
    query_embedding: list[float] | None,
    source_doc_id: str | None = None,
    top_k: int = 8,
    alpha: float = 0.5,
) -> list[RetrieveHit]:
    rows = _load_rows(session, source_doc_id)
    if not rows:
        return []
    texts = [row.text for row in rows]
    kw = keyword_scores(query, texts)
    combined: list[RetrieveHit] = []
    for i, row in enumerate(rows):
        semantic = 0.0
        if query_embedding and row.embedding_json:
            try:
                stored = json.loads(row.embedding_json)
                if isinstance(stored, list) and stored:
                    semantic = _cosine(query_embedding, [float(x) for x in stored])
            except json.JSONDecodeError:
                semantic = 0.0
        keyword = kw[i] if i < len(kw) else 0.0
        score = alpha * semantic + (1.0 - alpha) * keyword
        combined.append(
            RetrieveHit(
                chunk_id=row.chunk_id,
                source_doc_id=row.source_doc_id,
                channel=row.channel,
                page=row.page,
                text=row.text,
                score=score,
                keyword_score=keyword,
                semantic_score=semantic,
                section_ref=row.section_ref,
            )
        )
    combined.sort(key=lambda hit: hit.score, reverse=True)
    return [hit for hit in combined if hit.score > 0][:top_k]


def hits_to_json(hits: list[RetrieveHit]) -> list[dict[str, Any]]:
    return [
        {
            "chunk_id": hit.chunk_id,
            "source_doc_id": hit.source_doc_id,
            "channel": hit.channel,
            "page": hit.page,
            "section_ref": hit.section_ref,
            "score": round(hit.score, 6),
            "keyword_score": round(hit.keyword_score, 6),
            "semantic_score": round(hit.semantic_score, 6),
            "text": hit.text[:1200],
        }
        for hit in hits
    ]
