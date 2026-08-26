"""GET /retrieve/* — Search reliefs using hybrid search."""

from typing import Any

from fastapi import APIRouter, HTTPException, Query, status
from openai import OpenAI

from app.config import get_rag_relief_settings
from app.services.db_retriever import DatabaseRetriever
from app.services.retriever_state import (
    get_retriever as get_shared_retriever,
    set_retriever,
)

router = APIRouter(prefix="/retrieve", tags=["retrieve"])
settings = get_rag_relief_settings()


def get_retriever():
    """Get the shared retriever instance, or initialize from database."""
    retriever = get_shared_retriever()
    if retriever is None:
        # Try to initialize from database
        try:
            retriever = DatabaseRetriever(settings.DATABASE_URL)
            set_retriever(retriever)
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"Retriever not initialized. Database error: {str(e)}",
            )
    return retriever


@router.post("/search", summary="Search reliefs (hybrid: keyword + semantic)")
async def search_reliefs(
    query: str = Query(..., min_length=3, description="Search query"),
    top_k: int = Query(5, ge=1, le=20, description="Number of results"),
    alpha: float = Query(0.5, ge=0.0, le=1.0, description="Semantic weight (0=keyword, 1=semantic)"),
) -> dict[str, Any]:
    """
    Search reliefs using hybrid search.

    Args:
        query: "personal relief cap", "employment income", etc.
        top_k: Number of results to return (1-20)
        alpha: Weight for semantic search (0.5 = balanced)

    Returns:
        {
            "query": "personal relief cap",
            "results": [
                {
                    "rank": 1,
                    "score": 0.85,
                    "text": "Relief provision text...",
                    "has_relief": true,
                    "has_amount": true,
                    "amounts": ["1200000"]
                }
            ]
        }
    """
    try:
        retriever = get_retriever()

        # Get query embedding
        client = OpenAI(api_key=settings.OPENAI_API_KEY)
        response = client.embeddings.create(
            model=settings.EMBEDDING_MODEL,
            input=query,
        )
        query_embedding = response.data[0].embedding

        # Hybrid search
        results = retriever.hybrid_search(
            query,
            query_embedding,
            top_k=top_k,
            alpha=alpha,
        )

        # Format results
        formatted = [
            {
                "rank": i + 1,
                "score": result["score"],
                "text": result["text"],
                "has_relief": result.get("has_relief", False),
                "has_amount": result.get("has_amount", False),
                "amounts": result.get("relief_amounts", []),
            }
            for i, result in enumerate(results)
        ]

        return {
            "query": query,
            "top_k": top_k,
            "alpha": alpha,
            "result_count": len(formatted),
            "results": formatted,
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Search failed: {str(e)}",
        ) from e


@router.get("/keyword", summary="Keyword search only (TF-IDF/BM25)")
async def keyword_search(
    query: str = Query(..., min_length=3, description="Search query"),
    top_k: int = Query(5, ge=1, le=20, description="Number of results"),
) -> dict[str, Any]:
    """
    Fast keyword search using TF-IDF (no API call).

    Args:
        query: "personal relief", "Rs. 1200000", etc.
        top_k: Number of results

    Returns:
        Same as /search but keyword-only
    """
    try:
        retriever = get_retriever()
        results = retriever.keyword_search(query, top_k=top_k)

        formatted = [
            {
                "rank": i + 1,
                "score": result["score"],
                "text": result["text"],
            }
            for i, result in enumerate(results)
        ]

        return {
            "query": query,
            "method": "keyword",
            "result_count": len(formatted),
            "results": formatted,
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Keyword search failed: {str(e)}",
        ) from e


@router.get("/semantic", summary="Semantic search only (embeddings)")
async def semantic_search(
    query: str = Query(..., min_length=3, description="Search query"),
    top_k: int = Query(5, ge=1, le=20, description="Number of results"),
) -> dict[str, Any]:
    """
    Semantic search using embeddings (API call required).

    Args:
        query: "reliefs for business owners", etc.
        top_k: Number of results

    Returns:
        Same as /search but semantic-only
    """
    try:
        retriever = get_retriever()

        # Get query embedding
        client = OpenAI(api_key=settings.OPENAI_API_KEY)
        response = client.embeddings.create(
            model=settings.EMBEDDING_MODEL,
            input=query,
        )
        query_embedding = response.data[0].embedding

        results = retriever.semantic_search(query_embedding, top_k=top_k)

        formatted = [
            {
                "rank": i + 1,
                "score": result["score"],
                "text": result["text"],
            }
            for i, result in enumerate(results)
        ]

        return {
            "query": query,
            "method": "semantic",
            "result_count": len(formatted),
            "results": formatted,
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Semantic search failed: {str(e)}",
        ) from e
