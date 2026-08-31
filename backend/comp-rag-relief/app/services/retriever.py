"""Retrieval service for relief chunks using hybrid search."""

import logging
from typing import Any

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

logger = logging.getLogger(__name__)


class ReliefRetriever:
    """
    Hybrid retrieval: combines BM25 (keyword) + dense (semantic) search.
    For now, we use TF-IDF as a lightweight alternative to BM25.
    """

    def __init__(self, chunks: list[dict[str, Any]]):
        """
        Initialize retriever with chunks.

        Args:
            chunks: List of chunk dicts (from embedder, with embeddings)
        """
        self.chunks = chunks
        self.vectorizer = None
        self.tfidf_matrix = None
        self._build_tfidf_index()
        logger.info(f"Retriever initialized with {len(chunks)} chunks")

    def _build_tfidf_index(self):
        """Build TF-IDF index for keyword search."""
        if not self.chunks:
            logger.warning("No chunks to index")
            return

        texts = [chunk["text"] for chunk in self.chunks]
        try:
            self.vectorizer = TfidfVectorizer(
                max_features=1000,
                lowercase=True,
                stop_words="english",
                ngram_range=(1, 2),
            )
            self.tfidf_matrix = self.vectorizer.fit_transform(texts)
            logger.info(f"Built TF-IDF index for {len(texts)} chunks")
        except Exception as e:
            logger.error(f"Failed to build TF-IDF index: {e}")

    def keyword_search(self, query: str, top_k: int = 5) -> list[dict[str, Any]]:
        """
        Keyword search using TF-IDF.

        Args:
            query: Search query
            top_k: Number of results to return

        Returns:
            [{"chunk_id": "...", "text": "...", "score": 0.85}, ...]
        """
        if not self.vectorizer or self.tfidf_matrix is None:
            logger.warning("TF-IDF index not available")
            return []

        try:
            query_vec = self.vectorizer.transform([query])
            scores = cosine_similarity(query_vec, self.tfidf_matrix)[0]

            # Get top-k indices
            top_indices = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[
                :top_k
            ]

            results = [
                {
                    "chunk_id": self.chunks[i]["chunk_id"],
                    "text": self.chunks[i]["text"],
                    "score": float(scores[i]),
                    "method": "keyword",
                }
                for i in top_indices
                if scores[i] > 0.0
            ]

            logger.debug(f"Keyword search returned {len(results)} results")
            return results
        except Exception as e:
            logger.error(f"Keyword search failed: {e}")
            return []

    def semantic_search(self, query_embedding: list[float], top_k: int = 5) -> list[dict[str, Any]]:
        """
        Semantic search using embeddings.

        Args:
            query_embedding: Query embedding vector
            top_k: Number of results to return

        Returns:
            [{"chunk_id": "...", "text": "...", "score": 0.92}, ...]
        """
        if not query_embedding:
            logger.warning("Empty query embedding")
            return []

        results = []

        for chunk in self.chunks:
            if "embedding" not in chunk or not chunk["embedding"]:
                continue

            # Cosine similarity
            chunk_embedding = chunk["embedding"]
            similarity = self._cosine_similarity(query_embedding, chunk_embedding)

            results.append(
                {
                    "chunk_id": chunk["chunk_id"],
                    "text": chunk["text"],
                    "score": float(similarity),
                    "method": "semantic",
                }
            )

        # Sort by score and take top-k
        results = sorted(results, key=lambda x: x["score"], reverse=True)[:top_k]
        logger.debug(f"Semantic search returned {len(results)} results")
        return results

    def hybrid_search(
        self,
        query: str,
        query_embedding: list[float],
        top_k: int = 5,
        alpha: float = 0.5,
    ) -> list[dict[str, Any]]:
        """
        Hybrid search: combine keyword and semantic results.

        Args:
            query: Text query
            query_embedding: Query embedding vector
            top_k: Number of results to return
            alpha: Weight for semantic (1-alpha for keyword)

        Returns:
            Merged results with combined scores
        """
        # Get results from both methods
        keyword_results = self.keyword_search(query, top_k=top_k * 2)
        semantic_results = self.semantic_search(query_embedding, top_k=top_k * 2)

        # Combine by chunk_id
        combined = {}

        for result in keyword_results:
            chunk_id = result["chunk_id"]
            if chunk_id not in combined:
                combined[chunk_id] = {
                    "chunk_id": chunk_id,
                    "text": result["text"],
                    "keyword_score": result["score"],
                    "semantic_score": 0.0,
                }
            else:
                combined[chunk_id]["keyword_score"] = result["score"]

        for result in semantic_results:
            chunk_id = result["chunk_id"]
            if chunk_id not in combined:
                combined[chunk_id] = {
                    "chunk_id": chunk_id,
                    "text": result["text"],
                    "keyword_score": 0.0,
                    "semantic_score": result["score"],
                }
            else:
                combined[chunk_id]["semantic_score"] = result["score"]

        # Compute hybrid score
        for chunk_data in combined.values():
            hybrid_score = (
                alpha * chunk_data["semantic_score"] + (1 - alpha) * chunk_data["keyword_score"]
            )
            chunk_data["score"] = hybrid_score

        # Sort and return top-k
        results = sorted(combined.values(), key=lambda x: x["score"], reverse=True)[:top_k]
        logger.debug(f"Hybrid search returned {len(results)} results")
        return results

    @staticmethod
    def _cosine_similarity(vec1: list[float], vec2: list[float]) -> float:
        """Compute cosine similarity between two vectors."""
        if not vec1 or not vec2:
            return 0.0

        dot_product = sum(a * b for a, b in zip(vec1, vec2))
        norm1 = sum(a * a for a in vec1) ** 0.5
        norm2 = sum(b * b for b in vec2) ** 0.5

        if norm1 == 0 or norm2 == 0:
            return 0.0

        return dot_product / (norm1 * norm2)
