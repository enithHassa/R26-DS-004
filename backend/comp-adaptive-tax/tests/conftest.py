"""Pytest fixtures for Adaptive Tax."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from adaptive_tax_app.config import get_adaptive_tax_settings
from adaptive_tax_app.main import create_app
from adaptive_tax_app.services.param_store import clear_param_store_cache


@pytest.fixture(autouse=True)
def _default_fixture_extraction_mode(
    tmp_path_factory: pytest.TempPathFactory,
    monkeypatch: pytest.MonkeyPatch,
) -> Iterator[None]:
    """Keep unit tests offline and isolate Phase 4 calc/override stores."""
    calc_root = tmp_path_factory.mktemp("adaptive_tax_calc_store")
    override_path = tmp_path_factory.mktemp("adaptive_tax_override") / "active_relief_caps.json"
    get_adaptive_tax_settings.cache_clear()
    clear_param_store_cache()
    monkeypatch.setenv("COMP_ADAPTIVE_TAX_EXTRACTION_MODE", "fixture")
    monkeypatch.setenv("COMP_ADAPTIVE_TAX_EXPLAIN_MODE", "fixture")
    monkeypatch.setenv("COMP_ADAPTIVE_TAX_KG_MODE", "file")
    monkeypatch.setenv("COMP_ADAPTIVE_TAX_CALC_STORE_DIR", str(Path(calc_root)))
    monkeypatch.setenv("COMP_ADAPTIVE_TAX_PARAM_OVERRIDE_PATH", str(override_path))
    get_adaptive_tax_settings.cache_clear()
    clear_param_store_cache()
    yield
    get_adaptive_tax_settings.cache_clear()
    clear_param_store_cache()


@pytest.fixture()
def client() -> Iterator[TestClient]:
    app = create_app()
    with TestClient(app) as test_client:
        yield test_client
