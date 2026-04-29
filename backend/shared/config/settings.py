from functools import lru_cache
from pathlib import Path
from urllib.parse import quote_plus

from pydantic_settings import BaseSettings

PROJECT_ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    # Database
    DATABASE_HOST: str
    DATABASE_PORT: int = 5432
    DATABASE_NAME: str = "tax-advisory-db"
    DATABASE_USER: str
    DATABASE_PASSWORD: str
    DATABASE_SSLMODE: str = "require"

    # Application
    APP_ENV: str = "development"
    APP_DEBUG: bool = False
    LOG_LEVEL: str = "INFO"
    #: Emit newline-delimited JSON logs (aggregation / audit pipelines).
    LOG_JSON: bool = False

    @property
    def database_url(self) -> str:
        password = quote_plus(self.DATABASE_PASSWORD)
        return (
            f"postgresql+psycopg2://{self.DATABASE_USER}:{password}"
            f"@{self.DATABASE_HOST}:{self.DATABASE_PORT}/{self.DATABASE_NAME}"
            f"?sslmode={self.DATABASE_SSLMODE}"
        )

    model_config = {
        "env_file": str(PROJECT_ROOT / ".env"),
        "env_file_encoding": "utf-8",
        "extra": "ignore",
    }


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
