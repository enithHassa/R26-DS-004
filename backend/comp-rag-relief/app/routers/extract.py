"""POST /extract/* — Extract structured reliefs with confidence scoring."""

from typing import Any

from fastapi import APIRouter, HTTPException, Query, status
from openai import OpenAI

from app.config import get_rag_relief_settings
from app.services.db_retriever import DatabaseRetriever
from app.services.retriever_state import (
    get_retriever as get_shared_retriever,
    set_retriever,
)

router = APIRouter(prefix="/extract", tags=["extract"])
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


@router.post("/relief", summary="Extract structured relief from query")
async def extract_relief(
    query: str = Query(..., min_length=10, description="Relief query/description"),
) -> dict[str, Any]:
    """
    Extract structured relief information from act PDFs.

    Uses RAG to find relevant provisions, then Claude extracts structured data
    with confidence scoring for auditor approval.

    Args:
        query: "Personal relief cap for 2024/25", etc.

    Returns:
        {
            "query": "...",
            "extracted_relief": {
                "name": "Personal Relief",
                "cap_amount": "1,200,000",
                "currency": "LKR",
                "effective_from": "2023-04-01",
                "assessment_years": ["2023_24", "2024_25"],
                "section_ref": "Fifth Schedule, paragraph 2(iv)",
                "quote": "Rs. 1,200,000, for each year...",
                "source_act": "Inland Revenue Amendment Act No. 45 of 2022"
            },
            "confidence_scores": {
                "relief_name": 0.95,
                "cap_amount": 0.92,
                "effective_date": 0.88,
                "overall": 0.92
            },
            "auditor_action_required": false,
            "message": "High confidence extraction. Ready for approval."
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

        # Retrieve relevant chunks
        results = retriever.hybrid_search(
            query,
            query_embedding,
            top_k=5,  # Get top 5 for context
            alpha=0.6,  # Favor semantic
        )

        if not results:
            return {
                "query": query,
                "status": "no_results",
                "message": "No relevant relief provisions found in the acts.",
                "extracted_relief": None,
                "confidence_scores": None,
            }

        # Combine top results as context
        context = "\n\n".join([f"[Source {i+1}]\n{r['text']}" for i, r in enumerate(results[:3])])

        # Use Claude to extract structured relief
        extraction_prompt = f"""Extract structured relief information from the following tax act excerpts.

CONTEXT:
{context}

USER QUERY: {query}

Extract and return a JSON object with:
- name: Relief name (e.g., "Personal Relief")
- cap_amount: Maximum amount in LKR (just number, e.g., "1200000")
- currency: Always "LKR"
- effective_from: Start date (YYYY-MM-DD format)
- assessment_years: List of applicable years (e.g., ["2023_24", "2024_25"])
- section_ref: Section reference (e.g., "Fifth Schedule, para 2(iv)")
- quote: Exact quote from act
- source_act: Act name and number

For confidence, provide a score 0.0-1.0 for each field based on:
- How clearly the information appears in the source
- How specific vs. ambiguous the language is
- Whether dates/amounts are explicitly stated

Return JSON only (no explanation).
"""

        extraction_response = client.chat.completions.create(
            model=settings.OPENAI_MODEL,
            max_tokens=1000,
            messages=[
                {
                    "role": "user",
                    "content": extraction_prompt,
                }
            ],
        )

        extraction_text = extraction_response.choices[0].message.content

        # Parse response
        import json
        try:
            # Try to extract JSON from response
            json_start = extraction_text.find("{")
            json_end = extraction_text.rfind("}") + 1
            if json_start >= 0 and json_end > json_start:
                extracted_json = json.loads(extraction_text[json_start:json_end])
            else:
                extracted_json = {}
        except json.JSONDecodeError:
            extracted_json = {}

        # Calculate confidence scores
        confidence_scores = {
            "relief_name": float(extracted_json.get("confidence_name", 0.7)),
            "cap_amount": float(extracted_json.get("confidence_amount", 0.7)),
            "effective_date": float(extracted_json.get("confidence_date", 0.7)),
        }
        confidence_scores["overall"] = sum(confidence_scores.values()) / len(confidence_scores)

        # Determine if auditor action needed
        auditor_action = confidence_scores["overall"] < settings.CONFIDENCE_THRESHOLD

        return {
            "query": query,
            "status": "success",
            "extracted_relief": {
                "name": extracted_json.get("name", "Unknown"),
                "cap_amount": extracted_json.get("cap_amount", "Unknown"),
                "currency": extracted_json.get("currency", "LKR"),
                "effective_from": extracted_json.get("effective_from", "Unknown"),
                "assessment_years": extracted_json.get("assessment_years", []),
                "section_ref": extracted_json.get("section_ref", "Unknown"),
                "quote": extracted_json.get("quote", "N/A"),
                "source_act": extracted_json.get("source_act", "Unknown"),
            },
            "confidence_scores": confidence_scores,
            "auditor_action_required": auditor_action,
            "message": (
                f"✅ High confidence ({confidence_scores['overall']:.0%}). Ready for approval."
                if not auditor_action
                else f"⚠️ Low confidence ({confidence_scores['overall']:.0%}). Needs manual review."
            ),
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Extraction failed: {str(e)}",
        ) from e


@router.get("/status", summary="Check extraction service status")
async def extract_status() -> dict[str, Any]:
    return {
        "status": "ok",
        "confidence_threshold": settings.CONFIDENCE_THRESHOLD,
        "openai_model": settings.OPENAI_MODEL,
        "temperature": settings.TEMPERATURE,
    }
