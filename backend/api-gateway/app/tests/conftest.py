"""Pytest fixtures for the gateway."""

from __future__ import annotations

import sys
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

GATEWAY_ROOT = Path(__file__).resolve().parents[2]
if str(GATEWAY_ROOT) not in sys.path:
    sys.path.insert(0, str(GATEWAY_ROOT))


@pytest.fixture(scope="session")
def client() -> TestClient:
    from app.main import create_app

    with TestClient(create_app()) as test_client:
        yield test_client


@pytest.fixture()
def auth_client() -> Iterator[TestClient]:
    """Gateway client with in-memory SQLite for shared auth routes."""
    from backend.shared.auth import router as auth_router_module
    from backend.shared.auth.models import User  # noqa: F401
    from backend.shared.config.database import Base
    from app.main import create_app

    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    # Auth only needs ``users``; financial_profiles is optional for login.
    User.__table__.create(engine, checkfirst=True)
    # Minimal stub so authenticate SQL against financial_profiles does not fail.
    from sqlalchemy import Column, DateTime, MetaData, Table, Uuid, func
    import uuid

    meta = MetaData()
    Table(
        "financial_profiles",
        meta,
        Column("id", Uuid, primary_key=True, default=uuid.uuid4),
        Column("user_id", Uuid, nullable=False),
        Column("created_at", DateTime(timezone=True), server_default=func.now()),
    )
    meta.create_all(engine)

    TestingSession = sessionmaker(bind=engine, autocommit=False, autoflush=False)

    def _override_get_db() -> Iterator[Session]:
        session = TestingSession()
        try:
            yield session
        finally:
            session.close()

    from backend.shared.config import database as shared_db

    app = create_app()
    # Override both the router wrapper and the shared get_db callable.
    app.dependency_overrides[auth_router_module.get_db] = _override_get_db
    app.dependency_overrides[shared_db.get_db] = _override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
    engine.dispose()
