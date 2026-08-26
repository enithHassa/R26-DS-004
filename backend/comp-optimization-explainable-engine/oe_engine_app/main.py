"""FastAPI entrypoint for Optimization and Explainable Engine (port 8009)."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.shared.config.settings import settings
from backend.shared.utils.logging import configure_logging, logger
from oe_engine_app import __version__
from oe_engine_app.routers import calculate, catalog, documents, explain, health, load_act, promote, retrieve


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    configure_logging(service_name="comp-optimization-explainable-engine")
    logger.info(
        "Optimization and Explainable Engine starting (version={}, phase=7)",
        __version__,
    )
    yield
    logger.info("Optimization and Explainable Engine shutting down")


def create_app() -> FastAPI:
    app = FastAPI(
        title="AI Tax Advisory — Optimization and Explainable Engine",
        description=(
            "Independent RAG, quote-gated extraction, and interview. "
            "Phase 7: goldens and retrieve against promoted Phase 6 extracts."
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
    app.include_router(health.router, tags=["health"])
    app.include_router(health.router, prefix="/api/v1", tags=["health"])
    app.include_router(catalog.router)
    app.include_router(catalog.router, prefix="/api/v1")
    app.include_router(documents.router)
    app.include_router(documents.router, prefix="/api/v1")
    app.include_router(retrieve.router)
    app.include_router(retrieve.router, prefix="/api/v1")
    app.include_router(calculate.router)
    app.include_router(calculate.router, prefix="/api/v1")
    app.include_router(explain.router)
    app.include_router(explain.router, prefix="/api/v1")
    app.include_router(promote.router)
    app.include_router(promote.router, prefix="/api/v1")
    app.include_router(load_act.router)
    app.include_router(load_act.router, prefix="/api/v1")
    return app


app = create_app()
