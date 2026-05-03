"""Framework-wide settings shared by every component service.

IMPORTANT: Only add fields here that more than one component genuinely
shares (DB, gateway routing, CORS, cross-cutting observability).
Component-specific paths, models, and knobs live in the component's own
config module — e.g. ``backend/comp-personalized-recommendation/app/config.py``.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal
from urllib.parse import quote_plus

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    """Typed application settings shared across all backend services."""

    # ---------- Database ----------
    # ``azure``  → shared Azure Postgres (production / multi-component);
    # ``local``  → local Postgres via docker-compose;
    # ``sqlite`` → file-based SQLite at ``SQLITE_PATH`` (handy for isolated
    # end-to-end testing of one component without touching the shared schema).
    DATABASE_MODE: Literal["azure", "local", "sqlite"] = "azure"
    DATABASE_HOST: str = "tax-advisory-db.postgres.database.azure.com"
    DATABASE_PORT: int = 5432
    DATABASE_NAME: str = "tax-advisory-db"
    DATABASE_USER: str = "axadvisor_admin"
    DATABASE_PASSWORD: str = ""
    DATABASE_SSLMODE: str = "require"

    LOCAL_DATABASE_HOST: str = "localhost"
    LOCAL_DATABASE_PORT: int = 5432
    LOCAL_DATABASE_NAME: str = "tax_advisory"
    LOCAL_DATABASE_USER: str = "tax_advisory"
    LOCAL_DATABASE_PASSWORD: str = "tax_advisory"

    SQLITE_PATH: Path = Field(
        default_factory=lambda: PROJECT_ROOT / "data" / "dev.db",
        description="Used when DATABASE_MODE=sqlite.",
    )

    # ---------- Application ----------
    APP_ENV: Literal["development", "staging", "production"] = "development"
    APP_DEBUG: bool = False
    LOG_LEVEL: str = "INFO"
    #: Emit newline-delimited JSON logs (aggregation / audit pipelines).
    LOG_JSON: bool = False

    # ---------- Gateway + component service discovery ----------
    # Component teams add their own *_URL entries as their services come online.
    # The gateway only needs to know where each component lives; component
    # services read their own port from their own config module.
    GATEWAY_PORT: int = 8000
    COMP_TRANSACTION_URL: str = "http://localhost:8001"
    COMP_OPTIMIZATION_URL: str = "http://localhost:8002"
    COMP_RECOMMENDATION_URL: str = "http://localhost:8003"
    COMP_LLM_URL: str = "http://localhost:8004"

    # ---------- CORS (comma-separated list in env) ----------
    CORS_ORIGINS: list[str] = Field(
        default_factory=lambda: [
            "http://localhost:5173",
            "http://localhost:3000",
        ]
    )

    # ---------- Cross-cutting observability ----------
    MLFLOW_TRACKING_URI: str = Field(default_factory=lambda: f"file:{PROJECT_ROOT / 'mlruns'}")

    model_config = SettingsConfigDict(
        env_file=str(PROJECT_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=True,
    )

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def _split_cors(cls, v: object) -> object:
        if isinstance(v, str):
            return [o.strip() for o in v.split(",") if o.strip()]
        return v

    @property
    def database_url(self) -> str:
        if self.DATABASE_MODE == "sqlite":
            self.SQLITE_PATH.parent.mkdir(parents=True, exist_ok=True)
            return f"sqlite:///{self.SQLITE_PATH}"
        if self.DATABASE_MODE == "local":
            return (
                f"postgresql+psycopg2://{self.LOCAL_DATABASE_USER}:{quote_plus(self.LOCAL_DATABASE_PASSWORD)}"
                f"@{self.LOCAL_DATABASE_HOST}:{self.LOCAL_DATABASE_PORT}/{self.LOCAL_DATABASE_NAME}"
            )
        password = quote_plus(self.DATABASE_PASSWORD)
        return (
            f"postgresql+psycopg2://{self.DATABASE_USER}:{password}"
            f"@{self.DATABASE_HOST}:{self.DATABASE_PORT}/{self.DATABASE_NAME}"
            f"?sslmode={self.DATABASE_SSLMODE}"
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
