"""Pytest fixtures for Component 1 (transaction semantic) HTTP tests."""

from __future__ import annotations

import sys
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

C1_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture()
def client() -> Iterator[TestClient]:
    """Load the component FastAPI app from ``backend/comp-transaction-sementic``."""
    root = str(C1_ROOT)
    if root not in sys.path:
        sys.path.insert(0, root)
    from app.main import app

    with TestClient(app) as c:
        yield c
