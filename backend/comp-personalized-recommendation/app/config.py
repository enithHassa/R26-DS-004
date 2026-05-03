"""Settings owned by Component 3 (Personalized Recommendation).

Anything that is *only* meaningful to this component belongs here rather
than in :mod:`backend.shared.config.settings`. Every key is picked up from
the same ``.env`` at the repo root — prefix each with ``COMP_RECOMMENDATION_``
so teammates' component settings do not collide.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from backend.shared.config.settings import PROJECT_ROOT


class ComponentSettings(BaseSettings):
    """Component-3-only configuration."""

    # Service port used by `uvicorn` when running this component directly.
    COMP_RECOMMENDATION_PORT: int = 8003

    # Filesystem locations that belong to this component's ML package.
    COMP_RECOMMENDATION_RULES_PATH: Path = (
        PROJECT_ROOT / "models" / "personalized-recommendation" / "rules" / "sl_tax_2024_25.yaml"
    )
    COMP_RECOMMENDATION_ARTIFACTS_DIR: Path = (
        PROJECT_ROOT / "models" / "personalized-recommendation" / "artifacts"
    )
    COMP_RECOMMENDATION_DATA_DIR: Path = PROJECT_ROOT / "data" / "synthetic"

    # Ranking + Monte Carlo defaults (overridable per request).
    COMP_RECOMMENDATION_DEFAULT_TOP_K: int = Field(default=5, ge=1, le=25)
    COMP_RECOMMENDATION_DEFAULT_MC_PATHS: int = Field(default=2_000, ge=100, le=50_000)
    COMP_RECOMMENDATION_DEFAULT_HORIZON_YEARS: int = Field(default=10, ge=1, le=40)

    # Multi-objective score weights (WP6).
    COMP_RECOMMENDATION_W_SAVINGS: float = 0.40
    COMP_RECOMMENDATION_W_ADOPTION: float = 0.30
    COMP_RECOMMENDATION_W_FEASIBILITY: float = 0.20
    COMP_RECOMMENDATION_W_RISK_PENALTY: float = 0.10

    model_config = SettingsConfigDict(
        env_file=str(PROJECT_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=True,
    )


@lru_cache
def get_component_settings() -> ComponentSettings:
    return ComponentSettings()


component_settings = get_component_settings()
