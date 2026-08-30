"""Fixture JSON is the Phase 4 contract."""

from __future__ import annotations

import json
from pathlib import Path

from oe_engine_app.schemas.extract import RateBandEntity, ReliefEntity
from oe_engine_app.services.shape import compare_entity_shape

FIXTURES = (
    Path(__file__).resolve().parents[3]
    / "models"
    / "opt-explain-engine"
    / "fixtures"
)


def test_relief_fixture_validates() -> None:
    payload = json.loads((FIXTURES / "extract_schema_relief.json").read_text(encoding="utf-8"))
    entity = ReliefEntity.model_validate(payload)
    assert entity.eligibility.review_status == "pending"
    assert entity.paragraph_ref
    roundtrip = compare_entity_shape(entity.model_dump(mode="json"), payload)
    assert roundtrip["missing_keys"] == []


def test_rate_band_fixture_validates() -> None:
    payload = json.loads((FIXTURES / "extract_schema_rate_band.json").read_text(encoding="utf-8"))
    entity = RateBandEntity.model_validate(payload)
    assert entity.entity_kind == "rate_band"
    assert entity.lower == "0"
    roundtrip = compare_entity_shape(entity.model_dump(mode="json"), payload)
    assert roundtrip["missing_keys"] == []
