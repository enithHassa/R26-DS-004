"""POST /ingest/* — Upload PDF, chunk, embed, store."""

import os
from pathlib import Path
from typing import Any
from dotenv import load_dotenv

from fastapi import APIRouter, File, HTTPException, UploadFile, status

from app.config import get_rag_relief_settings, PROJECT_ROOT
from app.services.chunker import ReliefChunker
from app.services.embedder import ReliefEmbedder
from app.services.pdf_loader import PDFLoader
from app.services.db_retriever import DatabaseRetriever
from app.services.retriever_state import set_retriever

# Load .env at router init time
load_dotenv(PROJECT_ROOT / ".env")

router = APIRouter(prefix="/ingest", tags=["ingest"])
settings = get_rag_relief_settings()


@router.post("/pdf", summary="Upload & process PDF (chunk + embed)")
async def ingest_pdf(file: UploadFile = File(...)) -> dict[str, Any]:
    """
    Upload a PDF act and process it:
    1. Extract text
    2. Chunk semantically
    3. Embed with OpenAI
    4. Return metadata

    Returns:
        {
            "filename": "act.pdf",
            "pages": 234,
            "chunks": 124,
            "reliefs_found": 39,
            "amounts_found": 12,
            "job_id": "uuid-xxx"
        }
    """
    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No filename provided",
        )

    # Validate PDF
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File must be a PDF",
        )

    try:
        # Read file
        content = await file.read()

        # Save temporarily
        temp_path = settings.PDF_UPLOAD_DIR / file.filename
        settings.PDF_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
        temp_path.write_bytes(content)

        # Load PDF
        loader = PDFLoader()
        pdf_data = loader.load_pdf(temp_path)

        # Chunk
        chunker = ReliefChunker()
        chunks = chunker.chunk_text(
            pdf_data["text"],
            chunk_size=settings.CHUNK_SIZE,
            overlap=settings.CHUNK_OVERLAP,
        )

        # Embed (get API key - try multiple sources)
        api_key = settings.OPENAI_API_KEY
        api_key_source = "settings"

        if not api_key:
            api_key = os.getenv("OPENAI_API_KEY", "")
            api_key_source = "environment"

        if not api_key:
            env_file = PROJECT_ROOT / ".env"
            if env_file.exists():
                with open(env_file, "r") as f:
                    for line in f:
                        if line.startswith("OPENAI_API_KEY="):
                            api_key = line.split("=", 1)[1].strip()
                            api_key_source = "env_file"
                            break

        if not api_key:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"API key not found. Checked: settings, environment, .env file at {PROJECT_ROOT / '.env'}",
            )

        # Debug: return API key status
        if len(api_key) < 20:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"API key too short ({len(api_key)} chars) from {api_key_source}",
            )

        embedder = ReliefEmbedder(
            api_key=api_key,
            model=settings.EMBEDDING_MODEL,
        )
        chunks_with_embeddings = embedder.embed_chunks(chunks)

        # Store chunks to database
        db_retriever = DatabaseRetriever(settings.DATABASE_URL)
        for chunk in chunks_with_embeddings:
            chunk["source_act"] = file.filename
        db_retriever.store_chunks(chunks_with_embeddings)

        # Initialize retriever and share across routers
        set_retriever(db_retriever)

        # Log operation
        db_retriever.log_operation(
            operation="ingest",
            pdf_filename=file.filename,
            chunks_affected=len(chunks_with_embeddings),
            success=True,
        )

        # Stats
        reliefs_found = sum(1 for c in chunks if c["has_relief"])
        amounts_found = sum(1 for c in chunks if c["has_amount"])

        return {
            "status": "success",
            "filename": file.filename,
            "pages": pdf_data["pages"],
            "chunks_created": len(chunks_with_embeddings),
            "reliefs_detected": reliefs_found,
            "amounts_detected": amounts_found,
            "storage_path": str(temp_path),
            "message": "PDF processed successfully. Ready for retrieval.",
        }

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"PDF processing failed: {str(e)}",
        ) from e


@router.post("/test-mock", summary="Initialize with mock data for testing")
async def init_mock_data() -> dict[str, Any]:
    """Initialize retriever with mock chunks for endpoint testing."""
    mock_chunks = [
        {
            "chunk_id": "test_001",
            "text": "Personal Relief: A relief of Rs. 1,200,000 for each year of assessment. This relief is available to all resident individuals earning taxable income.",
            "has_relief": True,
            "has_amount": True,
            "relief_amounts": ["1200000"],
            "embedding": [0.1] * settings.PGVECTOR_DIMENSION,
        },
        {
            "chunk_id": "test_002",
            "text": "Employment Income Relief: For employees, a relief of Rs. 500,000 per year is available for contributions to approved pension schemes and life insurance.",
            "has_relief": True,
            "has_amount": True,
            "relief_amounts": ["500000"],
            "embedding": [0.2] * settings.PGVECTOR_DIMENSION,
        },
        {
            "chunk_id": "test_003",
            "text": "Business Loss Relief: A taxpayer may carry forward business losses incurred to set off against future business income over a period of six years.",
            "has_relief": True,
            "has_amount": False,
            "relief_amounts": [],
            "embedding": [0.3] * settings.PGVECTOR_DIMENSION,
        },
        {
            "chunk_id": "test_004",
            "text": "Capital Gains Tax: Capital gains are subject to income tax at the rate applicable to the taxpayer. Long-term capital gains may have preferential treatment.",
            "has_relief": False,
            "has_amount": False,
            "relief_amounts": [],
            "embedding": [0.4] * settings.PGVECTOR_DIMENSION,
        },
        {
            "chunk_id": "test_005",
            "text": "Mortgage Interest Relief: Interest paid on home loans of up to Rs. 3,000,000 is eligible for relief, subject to specified conditions.",
            "has_relief": True,
            "has_amount": True,
            "relief_amounts": ["3000000"],
            "embedding": [0.5] * settings.PGVECTOR_DIMENSION,
        },
    ]

    retriever = ReliefRetriever(mock_chunks)
    set_retriever(retriever)

    return {
        "status": "success",
        "message": "Mock retriever initialized for testing",
        "chunks_loaded": len(mock_chunks),
        "reliefs_in_mock_data": sum(1 for c in mock_chunks if c["has_relief"]),
    }


@router.get("/status", summary="Check ingest service status")
async def ingest_status() -> dict[str, Any]:
    return {
        "status": "ok",
        "pdf_upload_dir": str(settings.PDF_UPLOAD_DIR),
        "chunk_size": settings.CHUNK_SIZE,
        "embedding_model": settings.EMBEDDING_MODEL,
        "confidence_threshold": settings.CONFIDENCE_THRESHOLD,
    }
