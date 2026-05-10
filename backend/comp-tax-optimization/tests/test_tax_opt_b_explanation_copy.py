"""Unit tests for FR5 copy helpers (display labels, tier blurbs)."""

from tax_opt_b_app.services.tax_opt_b_explanation_copy import (
    narrative_tier_blurb_compute,
    relief_display_name,
)


def test_relief_display_name_known_code() -> None:
    assert relief_display_name("life_insurance_premium") == "Life insurance premiums"


def test_relief_display_name_unknown_fallback() -> None:
    assert relief_display_name("custom_snake_code") == "Custom Snake Code"


def test_narrative_tier_blurbs_distinct() -> None:
    assert "Summary narrative" in narrative_tier_blurb_compute("summary")
    assert "Detailed narrative" in narrative_tier_blurb_compute("detailed")
    assert narrative_tier_blurb_compute("summary") != narrative_tier_blurb_compute("detailed")
