"""OpenAI embeddings stored as JSON text (no pgvector)."""

from __future__ import annotations

from typing import Protocol

EMBEDDING_USD_PER_MILLION = 0.020  # text-embedding-3-small list price


class Embedder(Protocol):
    model: str

    def embed_batch(self, texts: list[str]) -> list[list[float]]: ...


class OpenAIEmbedder:
    def __init__(self, api_key: str, model: str, batch_size: int = 64) -> None:
        from openai import OpenAI

        if not isinstance(api_key, str) or not api_key.strip():
            raise TypeError("OpenAIEmbedder expects an API key string, not a client object")
        self._client = OpenAI(api_key=api_key)
        self.model = model
        self.batch_size = batch_size

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        out: list[list[float]] = []
        for start in range(0, len(texts), self.batch_size):
            batch = texts[start : start + self.batch_size]
            response = self._client.embeddings.create(model=self.model, input=batch)
            ordered = sorted(response.data, key=lambda item: item.index)
            out.extend(item.embedding for item in ordered)
        return out


class HashEmbedder:
    """Deterministic stand-in for tests (no API spend)."""

    def __init__(self, dim: int = 16) -> None:
        self.model = "hash-embed-test"
        self.dim = dim

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        vectors: list[list[float]] = []
        for text in texts:
            vec = [0.0] * self.dim
            for i, ch in enumerate(text.encode("utf-8")):
                vec[i % self.dim] += (ch % 13) / 13.0
            norm = sum(x * x for x in vec) ** 0.5 or 1.0
            vectors.append([x / norm for x in vec])
        return vectors


def estimate_embedding_usd(texts: list[str]) -> float:
    chars = sum(len(t) for t in texts)
    tokens = max(chars / 4.0, 1.0)
    return (tokens / 1_000_000.0) * EMBEDDING_USD_PER_MILLION
