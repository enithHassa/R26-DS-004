"""FastAPI entrypoint for the Personalized Recommendation component (Component 3)."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import __version__, models  # noqa: F401 — register ORM tables on Base.metadata
from app.routers import health, impact, profiles, recommendations, strategies
from backend.shared.config.settings import settings
from backend.shared.utils.logging import configure_logging, logger


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    configure_logging(service_name="comp-recommendation")
    logger.info("Recommendation component starting (version={})", __version__)
    yield
    logger.info("Recommendation component shutting down")


def create_app() -> FastAPI:
    app = FastAPI(
        title="AI Tax Advisory — Personalized Recommendation",
        description=(
            "Component 3 of R26-DS-004. Provides financial profile management, "
            "tax strategy generation, learning-to-rank recommendations with "
            "adoption-probability modelling, and Monte-Carlo predictive impact simulation."
        ),
        version=__version__,
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    api_prefix = "/api/v1"
    app.include_router(health.router, tags=["health"])
    app.include_router(profiles.router, prefix=f"{api_prefix}/profiles", tags=["profiles"])
    app.include_router(strategies.router, prefix=f"{api_prefix}/strategies", tags=["strategies"])
    app.include_router(
        recommendations.router,
        prefix=f"{api_prefix}/recommendations",
        tags=["recommendations"],
    )
    app.include_router(impact.router, prefix=f"{api_prefix}/impact", tags=["impact"])

    return app


app = create_app()
