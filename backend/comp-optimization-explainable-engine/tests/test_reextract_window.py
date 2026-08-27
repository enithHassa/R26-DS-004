"""Targeted window re-extract replaces only that window's rows."""

from __future__ import annotations

from oe_engine_app.services.reextract_window import merge_window_entities

STORED = [
    {"entry_id": "oee-act-10-2021:w008:relief:0", "compare_group_id": "personal_relief"},
    {"entry_id": "oee-act-10-2021:w009:relief:0", "compare_group_id": "lumped"},
    {"entry_id": "oee-act-10-2021:w009:relief:1", "compare_group_id": "lumped_two"},
    {"entry_id": "oee-act-10-2021:w010:band:0", "compare_group_id": "first_schedule_rates"},
]

FRESH = [
    {"entry_id": "oee-act-10-2021:w009:relief:0", "compare_group_id": "qp_film"},
    {"entry_id": "oee-act-10-2021:w009:relief:1", "compare_group_id": "qp_cinema_new"},
    {"entry_id": "oee-act-10-2021:w009:relief:2", "compare_group_id": "qp_cinema_upgrade"},
]


def test_only_target_window_rows_are_replaced() -> None:
    merged = merge_window_entities(STORED, "w009", FRESH)
    assert [e["compare_group_id"] for e in merged] == [
        "personal_relief",
        "qp_film",
        "qp_cinema_new",
        "qp_cinema_upgrade",
        "first_schedule_rates",
    ]


def test_rows_keep_their_original_position() -> None:
    merged = merge_window_entities(STORED, "w009", FRESH)
    assert merged[0] is STORED[0]
    assert merged[-1] is STORED[-1]


def test_window_with_no_prior_rows_appends() -> None:
    merged = merge_window_entities(STORED, "w999", FRESH)
    assert len(merged) == len(STORED) + len(FRESH)
    assert merged[: len(STORED)] == STORED


def test_empty_extract_drops_the_window_rows() -> None:
    merged = merge_window_entities(STORED, "w009", [])
    assert [e["compare_group_id"] for e in merged] == [
        "personal_relief",
        "first_schedule_rates",
    ]
