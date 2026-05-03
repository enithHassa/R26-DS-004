"""Pytest fixtures for the gateway."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

GATEWAY_ROOT = Path(__file__).resolve().parents[2]
if str(GATEWAY_ROOT) not in sys.path:
    sys.path.insert(0, str(GATEWAY_ROOT))


@pytest.fixture(scope="session")
def client() -> TestClient:
    from app.main import create_app

    return TestClient(create_app())
