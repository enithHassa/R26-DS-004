from pathlib import Path
from pydantic_settings import BaseSettings
from dotenv import load_dotenv
import os

PROJECT_ROOT = Path(__file__).parent.parent.parent.parent

# Load .env before creating settings instance
load_dotenv(PROJECT_ROOT / ".env")


class RAGReliefSettings(BaseSettings):
    """RAG Relief Component settings."""

    # Component info
    COMPONENT_NAME: str = "rag-relief"
    COMPONENT_VERSION: str = "0.1.0"
    APP_ENV: str = "development"
    LOG_LEVEL: str = "INFO"

    # Database (loaded from .env or environment)
    DATABASE_URL: str = "postgresql://user:password@localhost/tax_advisory"

    # Embeddings
    EMBEDDING_MODEL: str = "text-embedding-3-small"
    OPENAI_API_KEY: str = ""

    # Vector Store
    PGVECTOR_DIMENSION: int = 1536  # text-embedding-3-small dimension

    # PDF Processing
    PDF_UPLOAD_DIR: Path = PROJECT_ROOT / "models" / "rag-relief" / "uploads"
    CHUNKS_DIR: Path = PROJECT_ROOT / "models" / "rag-relief" / "chunks"
    MAX_PDF_SIZE_MB: int = 50

    # Chunking
    CHUNK_SIZE: int = 800  # tokens per chunk (semantic, not fixed)
    CHUNK_OVERLAP: int = 100

    # Retrieval
    RETRIEVAL_TOP_K: int = 5
    RERANK_TOP_K: int = 3
    CONFIDENCE_THRESHOLD: float = 0.7

    # OpenAI (for extraction)
    OPENAI_MODEL: str = "gpt-4"
    TEMPERATURE: float = 0.2

    class Config:
        env_file = str(PROJECT_ROOT / ".env")
        case_sensitive = True
        extra = "ignore"  # Ignore extra fields from .env


def get_rag_relief_settings() -> RAGReliefSettings:
    return RAGReliefSettings()
