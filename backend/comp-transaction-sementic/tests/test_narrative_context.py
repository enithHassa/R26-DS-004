"""Taxonomy narrative retrieval tests."""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
C1_ROOT = Path(__file__).resolve().parents[1]
for path in (str(REPO_ROOT), str(C1_ROOT)):
    if path not in sys.path:
        sys.path.insert(0, path)

from app.services.narrative_context import resolve_narrative_context


def test_cefts_description_prefers_non_internal_class() -> None:
    resolution = resolve_narrative_context("CEFTS (S456878)", direction="CR")
    assert resolution.suggested_class_key is not None
    assert resolution.suggested_class_key != "inter_account_transfer"
    assert resolution.interpretation


def test_round_up_transfer_can_map_internal_pattern() -> None:
    resolution = resolve_narrative_context(
        "Fund transfer from FriMi to Round up account",
        direction="CR",
    )
    assert resolution.suggested_class_key == "inter_account_transfer"
    assert resolution.hits


def test_noisy_description_routes_to_unknown() -> None:
    resolution = resolve_narrative_context(
        "0020122050016019840040129000500600100",
        direction="DR",
    )
    assert resolution.suggested_class_key == "unknown"
    assert "noisy" in resolution.interpretation.lower()
