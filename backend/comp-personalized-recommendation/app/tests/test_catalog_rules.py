"""Tests for opt-in Adaptive Tax catalog → recommendation rules loader."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "backend" / "comp-personalized-recommendation"))

from app.services.catalog_rules_service import (  # noqa: E402
    build_rules_dict_from_catalog,
    clear_synced_catalog,
    diff_catalog_vs_default,
    get_synced_snapshot,
    sync_catalog_rules,
)


def test_build_rules_from_catalog_2024_25_personal_relief() -> None:
    built = build_rules_dict_from_catalog("2024_25")
    rules = built["rules_dict"]
    assert rules["version"] == "2024_25"
    assert rules["personal_relief_annual"] == 1_200_000
    assert len(rules["apit_slabs"]) >= 5


def test_build_rules_from_catalog_2026_27_higher_relief() -> None:
    built = build_rules_dict_from_catalog("2026_27")
    rules = built["rules_dict"]
    assert rules["personal_relief_annual"] == 2_000_000


def test_diff_shows_personal_relief_change_between_years() -> None:
    diffs_2026 = {d.field: d for d in diff_catalog_vs_default("2026_27")}
    assert "personal_relief_annual" in diffs_2026 or "apit_slabs" in diffs_2026


def test_preview_metadata_includes_act_and_period() -> None:
    from app.services.catalog_rules_service import extract_catalog_preview_metadata

    meta = extract_catalog_preview_metadata("2026_27")
    assert "2026/27" in meta.assessment_period
    assert meta.promoted_at
    assert len(meta.legal_references) >= 1
    assert meta.legal_references[0].act_name
    assert meta.mapped_fields


def test_sync_puts_year_in_memory_cache() -> None:
    clear_synced_catalog()
    assert get_synced_snapshot("2026_27") is None
    snapshot = sync_catalog_rules("2026_27")
    assert snapshot.assessment_year == "2026_27"
    assert get_synced_snapshot("2026_27") is not None
    assert "personal_relief_annual" in snapshot.mapped_fields
    clear_synced_catalog()


def test_missing_year_raises() -> None:
    with pytest.raises(FileNotFoundError):
        build_rules_dict_from_catalog("2099_00")
