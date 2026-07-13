"""FastAPI entrypoint for Tax Strategy Optimization (Component B)."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from tax_opt_b_app import __version__
from tax_opt_b_app.config import component_settings
from tax_opt_b_app.routers import health, tax_opt_b_compliance, tax_opt_b_strategies_ml, tax_opt_b_phase2_ml_rank
from tax_opt_b_app.routers.tax_opt_b_rf_tax import router as rf_tax_router
from tax_opt_b_app.services.tax_opt_b_ml_ranking import load_ml_bundle_summary, load_ml_estimator
from tax_opt_b_app.services.tax_opt_b_rf_predictor import load_rf_bundle
from tax_opt_b_app.services.tax_opt_b_rules_loader import load_tax_opt_b_rules
from phase2_ml import MLStrategyRanker, FeatureEngineeringService, LegalRAGService
from backend.shared.config.settings import settings
from backend.shared.utils.logging import configure_logging, logger


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    configure_logging(service_name="comp-tax-optimization")
    rules_path = component_settings.COMP_OPTIMIZATION_RULES_PATH
    logger.info("Loading tax optimization rules from {}", rules_path)
    app.state.tax_opt_b_rules = load_tax_opt_b_rules(rules_path)
    rules_path_2025_26 = component_settings.COMP_OPTIMIZATION_RULES_PATH_2025_26
    logger.info("Loading 2025_26 tax optimization rules from {}", rules_path_2025_26)
    app.state.tax_opt_b_rules_2025_26 = load_tax_opt_b_rules(rules_path_2025_26)
    logger.info(
        "Tax optimization component started (version={}, assessment_years={}/{})",
        __version__,
        app.state.tax_opt_b_rules.assessment_year,
        app.state.tax_opt_b_rules_2025_26.assessment_year,
    )
    art_dir = component_settings.COMP_ML_ARTIFACTS_PATH
    logger.info("Pre-loading ML model from {}", art_dir)
    summary = load_ml_bundle_summary(art_dir)
    app.state.ml_summary = summary
    app.state.ml_estimator = load_ml_estimator(art_dir, summary)
    logger.info("ML model loaded (model_id={})", summary.model_id)
    try:
        app.state.rf_tax_bundle = load_rf_bundle(art_dir)
        logger.info("RF tax model loaded (model_id={})", app.state.rf_tax_bundle.model_id)
    except FileNotFoundError as _exc:
        logger.warning("RF tax model not found — /tax-filing/rf-predict will return 503 until trained: {}", _exc)
        app.state.rf_tax_bundle = None

    # === PHASE 2: ML STRATEGY RANKING ===
    try:
        logger.info("Loading Phase 2 ML models for strategy ranking...")
        logger.info("Component settings PHASE2_MODELS_PATH: {}", component_settings.PHASE2_MODELS_PATH)
        models_path = component_settings.PHASE2_MODELS_PATH
        logger.info("Looking for ML models in: {}", models_path)
        logger.info("Path type: {}", type(models_path))
        logger.info("Path exists: {}", models_path.exists())
        if models_path.exists():
            joblib_files = list(models_path.glob("*.joblib"))
            logger.info("Found {} .joblib files: {}", len(joblib_files), [f.name for f in joblib_files])
        else:
            logger.warning("Models directory not found at: {}", models_path)
        app.state.ml_strategy_ranker = MLStrategyRanker(models_dir=str(models_path))
        if app.state.ml_strategy_ranker.is_ready():
            logger.info("Phase 2 ML models loaded successfully (2 models for 2024_25 and 2025_26)")
        else:
            logger.warning("Phase 2 ML models not fully loaded — /optimization/ml-rank-strategies may have limited functionality")
    except Exception as _exc:
        logger.warning("Failed to load Phase 2 ML models: {} — Strategy ranking will be unavailable", _exc)
        app.state.ml_strategy_ranker = None

    try:
        logger.info("Initializing feature engineering service...")
        app.state.feature_engineer = FeatureEngineeringService()
        logger.info("Feature engineering service initialized (74 features)")
    except Exception as _exc:
        logger.warning("Failed to initialize feature engineering service: {}", _exc)
        app.state.feature_engineer = None

    try:
        logger.info("Initializing legal RAG service...")
        app.state.legal_rag = LegalRAGService()
        logger.info("Legal RAG service initialized (6 relief types)")
    except Exception as _exc:
        logger.warning("Failed to initialize legal RAG service: {}", _exc)
        app.state.legal_rag = None

    yield
    logger.info("Tax optimization component shutting down")


def create_app() -> FastAPI:
    app = FastAPI(
        title="AI Tax Advisory — Tax Strategy Optimization",
        description=(
            "Component B (R26-DS-004). Function 1: rule-backed compliance gate "
            "for Sri Lankan APIT-style MVP thresholds."
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

    api = "/api/v1"
    app.include_router(health.router, tags=["health"])
    app.include_router(tax_opt_b_compliance.router, prefix=f"{api}/compliance")
    app.include_router(tax_opt_b_strategies_ml.router, prefix=f"{api}/strategies")
    app.include_router(tax_opt_b_phase2_ml_rank.router, prefix=f"{api}/strategies")
    app.include_router(rf_tax_router, prefix=f"{api}/tax-filing")

    return app


app = create_app()
