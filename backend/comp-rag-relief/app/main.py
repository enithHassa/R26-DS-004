"""RAG Relief Component — Tax Act PDF retrieval and extraction."""

from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_rag_relief_settings

settings = get_rag_relief_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown logic."""
    # Startup
    print(
        f"RAG Relief component starting "
        f"(version={settings.COMPONENT_VERSION}, env={settings.APP_ENV})"
    )
    yield
    # Shutdown
    print("RAG Relief component shutting down")


app = FastAPI(
    title="RAG Relief Component",
    description="Tax Act PDF retrieval and relief extraction using RAG",
    version=settings.COMPONENT_VERSION,
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health", summary="Health check")
async def health() -> dict[str, Any]:
    return {
        "status": "ok",
        "component": settings.COMPONENT_NAME,
        "version": settings.COMPONENT_VERSION,
    }


@app.get("/", summary="API root")
async def root() -> dict[str, Any]:
    return {
        "message": "RAG Relief Component",
        "docs": "/docs",
        "version": settings.COMPONENT_VERSION,
    }


# Import and register routers
from app.routers import extract, ingest, retrieve

app.include_router(ingest.router)
app.include_router(retrieve.router)
app.include_router(extract.router)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host="127.0.0.1",
        port=8006,
        reload=True,
    )
