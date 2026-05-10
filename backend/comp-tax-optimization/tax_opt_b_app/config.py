"""Settings owned by Component B (Tax Strategy Optimization).

Keys use the ``COMP_OPTIMIZATION_`` prefix so they do not collide with other
components in the shared root ``.env``.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from backend.shared.config.settings import PROJECT_ROOT


class ComponentSettings(BaseSettings):
    """Component-B-only configuration."""

    COMP_OPTIMIZATION_PORT: int = 8002

    COMP_OPTIMIZATION_RULES_PATH: Path = (
        PROJECT_ROOT / "models" / "tax-optimization" / "rules" / "it22064486_sl_tax_mvp.yaml"
    )

    COMP_OPTIMIZATION_RULES_VERSION: str | None = Field(
        default=None,
        description="Optional override label echoed in API responses for traceability.",
    )

    COMP_ML_ARTIFACTS_PATH: Path = Field(
        default=PROJECT_ROOT / "models" / "tax-optimization" / "artifacts",
        description=(
            "Directory containing best_model_summary.json and trained joblib "
            "(Function 3 ML-assisted ranking)."
        ),
    )

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
