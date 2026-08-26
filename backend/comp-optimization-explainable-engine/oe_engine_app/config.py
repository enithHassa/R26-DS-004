"""Settings owned by Optimization and Explainable Engine (port 8009)."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from backend.shared.config.settings import PROJECT_ROOT


class OeEngineSettings(BaseSettings):
    COMP_OPTIMIZATION_EXPLAINABLE_ENGINE_PORT: int = 8009
    OPENAI_API_KEY: str | None = None
    OE_ENGINE_EMBEDDING_MODEL: str = "text-embedding-3-small"
    OE_ENGINE_PDF_ROOT: Path = Field(
        default_factory=lambda: PROJECT_ROOT / "data" / "raw" / "opt-explain-engine"
    )
    OE_ENGINE_MANIFEST_PATH: Path = Field(
        default_factory=lambda: PROJECT_ROOT
        / "models"
        / "opt-explain-engine"
        / "corpus_manifest.json"
    )
    OE_ENGINE_MAX_CHUNK_CHARS: int = 1200
    OE_ENGINE_CHUNK_OVERLAP: int = 150
    OE_ENGINE_EMBED_BATCH_SIZE: int = 64
    OE_ENGINE_EXTRACT_MODEL: str = "gpt-4o"
    OE_ENGINE_WINDOW_MIN_CHARS: int = 6000
    OE_ENGINE_WINDOW_MAX_CHARS: int = 11000
    OE_ENGINE_EXTRACT_OUT: Path = Field(
        default_factory=lambda: PROJECT_ROOT / "models" / "opt-explain-engine" / "extracted"
    )

    model_config = SettingsConfigDict(
        env_file=str(PROJECT_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=True,
    )


@lru_cache
def get_oe_engine_settings() -> OeEngineSettings:
    return OeEngineSettings()
