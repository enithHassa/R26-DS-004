"""Settings for Component 4 (Intelligent Tax Advisory Language Model)."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from backend.shared.config.settings import PROJECT_ROOT


class LanguageModelSettings(BaseSettings):
    """Language-model-only configuration (env vars from repo root `.env`)."""

    COMP_LLM_CORPUS_JSONL: Path | None = Field(
        default=None,
        description="Path to corpus_v1.jsonl for retrieval index (TF-IDF or dense per COMP_LLM_RETRIEVAL_BACKEND).",
    )
    COMP_LLM_RETRIEVAL_BACKEND: Literal["tfidf", "dense"] = Field(
        default="tfidf",
        description="Retrieval index for NLU parse: tfidf (default) or dense (sentence-transformers; optional deps).",
    )
    COMP_LLM_DENSE_MODEL: str = Field(
        default="sentence-transformers/all-MiniLM-L6-v2",
        description="Sentence-Transformers model id when COMP_LLM_RETRIEVAL_BACKEND=dense.",
    )
    COMP_LLM_DENSE_DEVICE: str | None = Field(
        default=None,
        description="Optional torch device for dense model (e.g. cuda, cuda:0, cpu); default is library auto.",
    )
    COMP_LLM_DENSE_EMBEDDING_BUNDLE_DIR: Path | None = Field(
        default=None,
        description=(
            "Phase 3 Step 14: directory containing node_embeddings_meta.json + .npz from "
            "compute_node_embeddings_bundle.py. When set with retrieval_backend=dense, "
            "skips re-encoding the corpus at startup (corpus JSONL still used for citation text)."
        ),
    )
    COMP_LLM_RETRIEVAL_TOP_K: int = Field(default=8, ge=1, le=50)
    COMP_LLM_QUERY_CITATION_MAX_CHARS: int = Field(
        default=2000,
        ge=200,
        le=50_000,
        description="Max characters per citation excerpt on POST /api/v1/query.",
    )
    COMP_LLM_INTENT_BENCHMARK_JSONL: Path | None = Field(
        default=None,
        description="Phase 2 benchmark JSONL to fit TF-IDF centroid intent baseline (optional).",
    )

    model_config = SettingsConfigDict(
        env_file=str(PROJECT_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_lm_settings() -> LanguageModelSettings:
    return LanguageModelSettings()
