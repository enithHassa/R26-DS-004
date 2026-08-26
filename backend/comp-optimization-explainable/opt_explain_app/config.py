"""Settings owned by Optimization and Explainable."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

from backend.shared.config.settings import PROJECT_ROOT


class OptimizationExplainableSettings(BaseSettings):
    COMP_OPTIMIZATION_EXPLAINABLE_PORT: int = 8008
    COMP_OPTIMIZATION_EXPLAINABLE_APPROVED_DIR: str = (
        "models/adaptive-tax/relief-interview/approved"
    )
    COMP_OPTIMIZATION_EXPLAINABLE_RATES_DIR: str = "models/adaptive-tax/relief-interview/rates"
    COMP_OPTIMIZATION_EXPLAINABLE_INDEX_DIR: str = "models/optimization-explainable"
    # Live narrative (Phase 6). Shared OPENAI_API_KEY with Adaptive Tax.
    OPENAI_API_KEY: str | None = None
    COMP_OPTIMIZATION_EXPLAINABLE_EXPLAIN_MODE: Literal["openai"] = "openai"
    COMP_OPTIMIZATION_EXPLAINABLE_OPENAI_EXPLAIN_MODEL: str = "gpt-4o-mini"

    model_config = SettingsConfigDict(
        env_file=str(PROJECT_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=True,
    )

    def _under_project(self, raw: str) -> Path:
        path = Path(raw)
        if not path.is_absolute():
            path = PROJECT_ROOT / path
        return path.resolve()

    @property
    def approved_dir(self) -> Path:
        return self._under_project(self.COMP_OPTIMIZATION_EXPLAINABLE_APPROVED_DIR)

    @property
    def rates_dir(self) -> Path:
        return self._under_project(self.COMP_OPTIMIZATION_EXPLAINABLE_RATES_DIR)

    @property
    def index_dir(self) -> Path:
        return self._under_project(self.COMP_OPTIMIZATION_EXPLAINABLE_INDEX_DIR)

    @property
    def rule_docs_dir(self) -> Path:
        return self.index_dir / "rule_docs"

    @property
    def rate_docs_dir(self) -> Path:
        return self.index_dir / "rate_docs"


@lru_cache
def get_oe_settings() -> OptimizationExplainableSettings:
    return OptimizationExplainableSettings()
