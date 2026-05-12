"""FastAPI entrypoint for the Intelligent Tax Advisory language-model component."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import __version__
from app.config import get_lm_settings
from app.routers import health, nlu, query
from app.routers.nlu import attach_intent_classifier, attach_retrieval_index
from app.services.corpus_chunk_kg_join import load_chunk_kg_join_by_id
from app.services.corpus_chunk_texts import load_chunk_texts
from backend.shared.config.settings import settings
from backend.shared.utils.logging import configure_logging, logger


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    configure_logging(service_name="comp-language-model")
    logger.info("Language-model component starting (version={})", __version__)
    lm_cfg = get_lm_settings()
    attach_retrieval_index(app.state, lm_cfg)
    texts = load_chunk_texts(lm_cfg.COMP_LLM_CORPUS_JSONL)
    app.state.chunk_text_by_id = texts
    join_map = load_chunk_kg_join_by_id(lm_cfg.COMP_LLM_CORPUS_JSONL)
    app.state.chunk_kg_join_by_id = join_map
    if texts:
        logger.info("Corpus citation texts loaded (chunks={})", len(texts))
    if join_map:
        logger.info("Corpus KG join metadata loaded (chunks={})", len(join_map))
    attach_intent_classifier(app.state, lm_cfg.COMP_LLM_INTENT_BENCHMARK_JSONL)
    idx = getattr(app.state, "retrieval_index", None)
    if idx is not None:
        if getattr(app.state, "retrieval_from_embedding_bundle", False) and lm_cfg.COMP_LLM_DENSE_EMBEDDING_BUNDLE_DIR:
            logger.info(
                "Corpus retrieval index loaded (backend=dense, chunks={}, embedding_bundle={}, corpus_jsonl={})",
                idx.size,
                lm_cfg.COMP_LLM_DENSE_EMBEDDING_BUNDLE_DIR,
                lm_cfg.COMP_LLM_CORPUS_JSONL,
            )
        else:
            logger.info(
                "Corpus retrieval index loaded (backend={}, chunks={}, path={})",
                lm_cfg.COMP_LLM_RETRIEVAL_BACKEND,
                idx.size,
                lm_cfg.COMP_LLM_CORPUS_JSONL,
            )
    else:
        logger.info(
            "No corpus index loaded (set COMP_LLM_CORPUS_JSONL, or fix dense deps if backend=dense)"
        )
    if getattr(app.state, "intent_classifier", None) is not None:
        logger.info(
            "TF-IDF intent centroid loaded from benchmark (path={})",
            lm_cfg.COMP_LLM_INTENT_BENCHMARK_JSONL,
        )
    else:
        logger.info("No intent benchmark configured (set COMP_LLM_INTENT_BENCHMARK_JSONL)")
    yield
    logger.info("Language-model component shutting down")


def create_app() -> FastAPI:
    app = FastAPI(
        title="AI Tax Advisory - Intelligent Tax Advisory Language Model",
        description=(
            "Component 4 (R26-DS-004). Hosts legal retrieval, reasoning, and answer "
            "generation endpoints for Sri Lankan income-tax advisory workflows."
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
    app.include_router(nlu.router)
    app.include_router(query.router)
    return app


app = create_app()
