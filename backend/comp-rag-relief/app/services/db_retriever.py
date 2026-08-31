"""Database-backed retriever with pgvector support."""

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker
from typing import Any
import json
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity

from app.config import get_rag_relief_settings
from app.models import RagReliefChunk, RagReliefAuditLog


class DatabaseRetriever:
    """Retriever backed by PostgreSQL + pgvector."""

    def __init__(self, database_url: str = None):
        """Initialize database connection."""
        if database_url is None:
            settings = get_rag_relief_settings()
            database_url = settings.DATABASE_URL

        self.engine = create_engine(database_url)
        self.SessionLocal = sessionmaker(bind=self.engine)

    def store_chunks(self, chunks: list[dict]) -> int:
        """Store chunks to database."""
        session = self.SessionLocal()
        try:
            count = 0
            for chunk in chunks:
                # Convert embedding list to pgvector string format
                embedding = chunk.get("embedding")
                if isinstance(embedding, list):
                    embedding_str = "[" + ",".join(f"{x:.6f}" for x in embedding) + "]"
                else:
                    embedding_str = str(embedding)

                db_chunk = RagReliefChunk(
                    text=chunk.get("text", ""),
                    has_relief=chunk.get("has_relief", False),
                    has_amount=chunk.get("has_amount", False),
                    relief_amounts=chunk.get("relief_amounts", []),
                    embedding=embedding_str,
                    source_act=chunk.get("source_act"),
                    source_section=chunk.get("source_section"),
                    page_number=chunk.get("page_number"),
                )
                session.add(db_chunk)
                count += 1

            session.commit()
            return count
        finally:
            session.close()

    def keyword_search(self, query: str, top_k: int = 5) -> list[dict]:
        """Search using TF-IDF (text search)."""
        session = self.SessionLocal()
        try:
            # Simple substring/text search (TF-IDF would require text search config)
            chunks = (
                session.query(RagReliefChunk)
                .filter(RagReliefChunk.searchable == True)
                .filter(
                    RagReliefChunk.text.ilike(f"%{query}%")
                )  # Simple substring match
                .limit(top_k)
                .all()
            )

            results = [
                {
                    "chunk_id": str(c.chunk_id),
                    "text": c.text,
                    "score": 0.5,  # Placeholder
                    "has_relief": c.has_relief,
                    "relief_amounts": c.relief_amounts,
                    "source_act": c.source_act,
                }
                for c in chunks
            ]
            return results
        finally:
            session.close()

    def semantic_search(self, query_embedding: list[float], top_k: int = 5) -> list[dict]:
        """Search using vector similarity (Azure-compatible: in-memory cosine distance)."""
        session = self.SessionLocal()
        try:
            # Get all chunks with embeddings from database
            chunks = (
                session.query(RagReliefChunk)
                .filter(RagReliefChunk.searchable == True)
                .filter(RagReliefChunk.embedding != None)
                .all()
            )

            # Calculate cosine similarity in Python
            query_vec = np.array(query_embedding).reshape(1, -1)
            results_with_scores = []

            for chunk in chunks:
                try:
                    # Parse embedding string to list
                    embedding_list = json.loads(chunk.embedding)
                    chunk_vec = np.array(embedding_list).reshape(1, -1)
                    # Cosine similarity (1 = identical, 0 = orthogonal, -1 = opposite)
                    score = float(cosine_similarity(query_vec, chunk_vec)[0][0])
                    results_with_scores.append(
                        {
                            "chunk_id": str(chunk.chunk_id),
                            "text": chunk.text,
                            "has_relief": chunk.has_relief,
                            "relief_amounts": chunk.relief_amounts or [],
                            "source_act": chunk.source_act,
                            "score": score,
                        }
                    )
                except (json.JSONDecodeError, ValueError):
                    continue

            # Sort by score and take top_k
            sorted_results = sorted(
                results_with_scores, key=lambda x: x["score"], reverse=True
            )
            return sorted_results[:top_k]
        finally:
            session.close()

    def hybrid_search(
        self,
        query: str,
        query_embedding: list[float],
        top_k: int = 5,
        alpha: float = 0.5,
    ) -> list[dict]:
        """Hybrid search combining keyword and semantic."""
        keyword_results = self.keyword_search(query, top_k)
        semantic_results = self.semantic_search(query_embedding, top_k)

        # Combine results by chunk_id
        combined = {}

        for i, result in enumerate(keyword_results):
            chunk_id = result["chunk_id"]
            score = 1.0 / (i + 1)  # Ranking score
            combined[chunk_id] = result.copy()
            combined[chunk_id]["keyword_score"] = score

        for i, result in enumerate(semantic_results):
            chunk_id = result["chunk_id"]
            if chunk_id in combined:
                combined[chunk_id]["semantic_score"] = result["score"]
                combined[chunk_id]["score"] = (
                    (1 - alpha) * combined[chunk_id]["keyword_score"]
                    + alpha * result["score"]
                )
            else:
                combined[chunk_id] = result.copy()
                combined[chunk_id]["semantic_score"] = result["score"]
                combined[chunk_id]["score"] = alpha * result["score"]

        # Sort by combined score and return top_k
        sorted_results = sorted(
            combined.values(),
            key=lambda x: x.get("score", 0),
            reverse=True,
        )[:top_k]

        return sorted_results

    def log_operation(
        self,
        operation: str,
        user_email: str = None,
        details: dict = None,
        pdf_filename: str = None,
        chunks_affected: int = None,
        success: bool = True,
        error_message: str = None,
    ) -> str:
        """Log an operation to audit trail."""
        session = self.SessionLocal()
        try:
            log_entry = RagReliefAuditLog(
                operation=operation,
                user_email=user_email,
                details=details,
                pdf_filename=pdf_filename,
                chunks_affected=chunks_affected,
                success=success,
                error_message=error_message,
            )
            session.add(log_entry)
            session.commit()
            return str(log_entry.log_id)
        finally:
            session.close()
