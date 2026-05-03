"""Thin async reverse-proxy gateway for the AI Tax Advisory System.

Routing map (only Component 3 is wired for now; others are placeholders):

    /api/v1/recommendation/**  ->  COMP_RECOMMENDATION_URL
    /api/v1/transaction/**     ->  (TBD, Component 1)
    /api/v1/optimization/**    ->  (TBD, Component 2)
    /api/v1/llm/**             ->  (TBD, Component 4)
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import httpx
from fastapi import APIRouter, FastAPI, HTTPException, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware

from app import __version__
from backend.shared.config.settings import settings
from backend.shared.utils.logging import configure_logging, logger

_HOP_BY_HOP = {
    "connection",
    "keep-alive",
    "proxy-authenticate",
    "proxy-authorization",
    "te",
    "trailers",
    "transfer-encoding",
    "upgrade",
    "content-encoding",
    "content-length",
    "host",
}


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    configure_logging(service_name="api-gateway")
    logger.info("API gateway starting (version={})", __version__)
    app.state.http = httpx.AsyncClient(timeout=httpx.Timeout(30.0, connect=5.0))
    try:
        yield
    finally:
        await app.state.http.aclose()
        logger.info("API gateway shutting down")


def create_app() -> FastAPI:
    app = FastAPI(
        title="AI Tax Advisory — API Gateway",
        description="Aggregates component APIs behind a single origin for the dashboard.",
        version=__version__,
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(_system_router())
    _register_proxy(app, prefix="/api/v1/recommendation", upstream=settings.COMP_RECOMMENDATION_URL)
    return app


def _system_router() -> APIRouter:
    router = APIRouter()

    @router.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "service": "api-gateway", "version": __version__}

    @router.get("/ready")
    async def ready(request: Request) -> dict[str, object]:
        client: httpx.AsyncClient = request.app.state.http
        checks: dict[str, bool] = {}
        try:
            r = await client.get(f"{settings.COMP_RECOMMENDATION_URL}/health", timeout=5.0)
            checks["recommendation"] = r.status_code == 200
        except Exception:
            checks["recommendation"] = False
        return {"status": "ok" if all(checks.values()) else "degraded", "checks": checks}

    return router


def _register_proxy(app: FastAPI, *, prefix: str, upstream: str) -> None:
    """Mount a catch-all reverse proxy at ``prefix`` forwarding to ``upstream``."""

    async def proxy(request: Request, path: str) -> Response:
        client: httpx.AsyncClient = request.app.state.http
        upstream_path = f"{upstream.rstrip('/')}/api/v1/{path}"
        headers = {k: v for k, v in request.headers.items() if k.lower() not in _HOP_BY_HOP}
        body = await request.body()
        try:
            upstream_resp = await client.request(
                request.method,
                upstream_path,
                params=request.query_params,
                headers=headers,
                content=body,
            )
        except httpx.RequestError as exc:
            logger.warning("Upstream {} unreachable: {}", upstream_path, exc)
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Upstream service unavailable: {exc}",
            ) from exc
        resp_headers = {
            k: v for k, v in upstream_resp.headers.items() if k.lower() not in _HOP_BY_HOP
        }
        return Response(
            content=upstream_resp.content,
            status_code=upstream_resp.status_code,
            headers=resp_headers,
            media_type=upstream_resp.headers.get("content-type"),
        )

    app.add_api_route(
        f"{prefix}/{{path:path}}",
        proxy,
        methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        include_in_schema=False,
        name=f"proxy_{prefix.strip('/').replace('/', '_')}",
    )


app = create_app()
