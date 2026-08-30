"""Pytest fixtures for Optimization and Explainable."""

from __future__ import annotations

import asyncio
from collections.abc import Iterator
from typing import Any

import httpx
import pytest
from httpx import ASGITransport

from opt_explain_app.main import create_app


class _SyncASGIClient:
    """httpx 0.28 ASGITransport is async-only; wrap it for sync pytest."""

    def __init__(self, app: Any) -> None:
        self._app = app

    def get(self, url: str, params: dict[str, str] | None = None) -> httpx.Response:
        async def _go() -> httpx.Response:
            transport = ASGITransport(app=self._app)
            async with httpx.AsyncClient(
                transport=transport,
                base_url="http://testserver",
            ) as client:
                return await client.get(url, params=params)

        return asyncio.run(_go())

    def post(self, url: str, json: dict[str, Any] | None = None) -> httpx.Response:
        async def _go() -> httpx.Response:
            transport = ASGITransport(app=self._app)
            async with httpx.AsyncClient(
                transport=transport,
                base_url="http://testserver",
            ) as client:
                return await client.post(url, json=json)

        return asyncio.run(_go())


@pytest.fixture()
def client() -> Iterator[_SyncASGIClient]:
    yield _SyncASGIClient(create_app())
