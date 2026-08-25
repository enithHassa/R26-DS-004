"""FastAPI entrypoint for Optimization and Explainable (port 8008)."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.shared.config.settings import settings
from backend.shared.utils.logging import configure_logging, logger
from opt_explain_app import __version__
from opt_explain_app.routers import calculate, catalog, explain, health
from opt_explain_app.services.rag_index import ensure_index


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    configure_logging(service_name="comp-optimization-explainable")
    logger.info(
        "Optimization and Explainable starting (version={}, phase=7)",
        __version__,
    )
    summary = ensure_index()
    logger.info(
        "RAG index ready (years={}, rules={}, rates={})",
        len(summary.get("years") or []),
        summary.get("rule_count"),
        summary.get("rate_count"),
    )
    yield
    logger.info("Optimization and Explainable shutting down")


def create_app() -> FastAPI:
    app = FastAPI(
        title="AI Tax Advisory — Optimization and Explainable",
        description=(
            "Year-aware RAG reliefs, tax calculation, and explanations. "
            "Phase 7: auditor-approved questions; promote HTTP-refreshes the RAG index."
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
    # Root probes for direct hits and gateway /ready checks.
    app.include_router(health.router, tags=["health"])
    # Gateway strips /optimization-explainable and forwards as /api/v1/{path}.
    app.include_router(health.router, prefix="/api/v1", tags=["health"])
    app.include_router(catalog.router)
    app.include_router(catalog.router, prefix="/api/v1")
    app.include_router(calculate.router)
    app.include_router(calculate.router, prefix="/api/v1")
    app.include_router(explain.router)
    app.include_router(explain.router, prefix="/api/v1")
    return app


app = create_app()
