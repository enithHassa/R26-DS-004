"""Pytest fixtures for Optimization and Explainable Engine."""

from __future__ import annotations

import asyncio
from collections.abc import Iterator
from typing import Any

import httpx
import pytest
from httpx import ASGITransport
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

import db  # noqa: F401  -- register year-view / mismatch tables
from backend.shared.config.database import Base
from oe_engine_app.main import create_app


class _SyncASGIClient:
    """httpx 0.28 ASGITransport is async-only; wrap it for sync pytest."""

    def __init__(self, app: Any) -> None:
        self._app = app

    def get(
        self,
        url: str,
        params: dict[str, str] | None = None,
        headers: dict[str, str] | None = None,
    ) -> httpx.Response:
        async def _go() -> httpx.Response:
            transport = ASGITransport(app=self._app)
            async with httpx.AsyncClient(
                transport=transport,
                base_url="http://testserver",
            ) as client:
                return await client.get(url, params=params, headers=headers)

        return asyncio.run(_go())

    def post(
        self,
        url: str,
        json: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> httpx.Response:
        async def _go() -> httpx.Response:
            transport = ASGITransport(app=self._app)
            async with httpx.AsyncClient(
                transport=transport,
                base_url="http://testserver",
            ) as client:
                return await client.post(url, json=json, headers=headers)

        return asyncio.run(_go())

    def patch(
        self,
        url: str,
        json: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> httpx.Response:
        async def _go() -> httpx.Response:
            transport = ASGITransport(app=self._app)
            async with httpx.AsyncClient(
                transport=transport,
                base_url="http://testserver",
            ) as client:
                return await client.patch(url, json=json, headers=headers)

        return asyncio.run(_go())


@pytest.fixture()
def db_session() -> Iterator[Session]:
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    # Match production SessionLocal (autoflush=False) so promote/compile flush bugs surface.
    factory = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    session = factory()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


@pytest.fixture()
def client(monkeypatch: pytest.MonkeyPatch, db_session: Session) -> Iterator[_SyncASGIClient]:
    bind = db_session.get_bind()
    factory = sessionmaker(bind=bind, autocommit=False, autoflush=False)

    def _factory() -> Session:
        return factory()

    monkeypatch.setattr("oe_engine_app.deps.SessionLocal", _factory)
    yield _SyncASGIClient(create_app())
