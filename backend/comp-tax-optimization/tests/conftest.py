"""Pytest fixtures for Component B."""

from __future__ import annotations

import sys
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

# ``tax_opt_b_app`` package lives under ``backend/comp-tax-optimization/`` (avoids colliding with ``app`` in api-gateway).
COMPONENT_ROOT = Path(__file__).resolve().parents[1]
if str(COMPONENT_ROOT) not in sys.path:
    sys.path.insert(0, str(COMPONENT_ROOT))


@pytest.fixture()
def client() -> Iterator[TestClient]:
    from tax_opt_b_app.main import create_app

    with TestClient(create_app()) as c:
        yield c
