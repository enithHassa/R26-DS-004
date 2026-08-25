"""FastAPI entrypoint for the Adaptive Tax component (Component 5)."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from adaptive_tax_app import __version__
from adaptive_tax_app.config import get_adaptive_tax_settings
from adaptive_tax_app.routers import (
    amendments,
    calculate,
    calculations,
    catalog_admin,
    catalog_engine,
    explain,
    filing_catalog,
    health,
    knowledge,
    params,
    relief_interview,
)
from backend.shared.config.settings import settings
from backend.shared.utils.logging import configure_logging, logger


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    configure_logging(service_name="comp-adaptive-tax")
    get_adaptive_tax_settings.cache_clear()
    cfg = get_adaptive_tax_settings()
    logger.info(
        "Adaptive Tax component starting (version={}, extraction_mode={}, openai_key_set={})",
        __version__,
        cfg.COMP_ADAPTIVE_TAX_EXTRACTION_MODE,
        bool(cfg.OPENAI_API_KEY and cfg.OPENAI_API_KEY.strip()),
    )
    from adaptive_tax_app.services.catalog_extract import resume_interrupted_extracts

    resumed = resume_interrupted_extracts()
    if resumed:
        logger.info("Resumed {} interrupted catalog-admin extract job(s)", len(resumed))
    yield
    logger.info("Adaptive Tax component shutting down")


def create_app() -> FastAPI:
    app = FastAPI(
        title="AI Tax Advisory — Adaptive Tax",
        description=(
            "Component 5 (R26-DS-004). AI-assisted adaptive tax calculation with "
            "explainable legal grounding: amendment ingestion, Neo4j/Chroma knowledge "
            "stores, pure-Python rule engine (POST /api/v1/calculate), Phase 4 "
            "calc persistence, and RAG-grounded explain (POST /api/v1/explain)."
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
    # Gateway strips /adaptive-tax and forwards as /api/v1/{path}.
    app.include_router(health.router, prefix="/api/v1", tags=["health"])
    app.include_router(amendments.router, prefix="/api/v1")
    app.include_router(params.router, prefix="/api/v1")
    app.include_router(knowledge.router, prefix="/api/v1")
    app.include_router(filing_catalog.router, prefix="/api/v1")
    app.include_router(relief_interview.router, prefix="/api/v1")  # Phase 3 catalogs
    app.include_router(catalog_engine.router, prefix="/api/v1")  # Phase 8 catalog rates
    app.include_router(catalog_admin.router, prefix="/api/v1")  # Add New Act (gated)
    app.include_router(calculate.router, prefix="/api/v1")
    app.include_router(calculations.router, prefix="/api/v1")
    app.include_router(explain.router, prefix="/api/v1")
    return app


app = create_app()
