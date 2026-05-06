"""Pytest fixtures for Component 1 (transaction semantic) HTTP tests."""

from __future__ import annotations

import importlib.util
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

C1_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture()
def client() -> Iterator[TestClient]:
    """Load ``app/main.py`` without colliding with other ``app`` packages on ``sys.path``."""
    main_path = C1_ROOT / "app" / "main.py"
    spec = importlib.util.spec_from_file_location("comp_transaction_semantic_main", main_path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    app = mod.app
    with TestClient(app) as c:
        yield c
