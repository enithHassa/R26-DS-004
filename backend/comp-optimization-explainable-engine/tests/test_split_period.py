"""Split intra-year dual caps from a relief quote (no GPT)."""

from __future__ import annotations

from oe_engine_app.services.split_period import expand_split_period_relief


def test_nine_and_three_month_personal_relief_split() -> None:
    entity = {
        "entity_kind": "relief",
        "entry_id": "oee-act-45-2022:w004:relief:2",
        "compare_group_id": "personal_relief",
        "cap_amount": "2250000",
        "effective_from": "2022-04-01",
        "effective_to": "2023-03-31",
        "quote": (
            "(iii) Rs. 2,250,000, for first nine months and Rs. 300,000 for "
            "second three months of the year of assessment commencing on April 1, 2022;"
        ),
    }
    rows = expand_split_period_relief(entity)
    assert len(rows) == 2
    assert rows[0]["cap_amount"] == "2250000"
    assert rows[0]["effective_from"] == "2022-04-01"
    assert rows[0]["effective_to"] == "2023-01-01"
    assert rows[1]["cap_amount"] == "300000"
    assert rows[1]["effective_from"] == "2023-01-01"
    assert rows[1]["effective_to"] == "2023-04-01"
    assert rows[1]["entry_id"] == "oee-act-45-2022:w004:relief:2:b"
    assert expand_split_period_relief(rows[0]) == [rows[0]]
    assert expand_split_period_relief(rows[1]) == [rows[1]]


def test_single_cap_unchanged() -> None:
    entity = {
        "entity_kind": "relief",
        "entry_id": "x:relief:0",
        "cap_amount": "1200000",
        "quote": "Rs. 1,200,000, for each year of assessment commencing on or after April 1, 2023,",
        "effective_from": "2023-04-01",
        "effective_to": "",
    }
    assert expand_split_period_relief(entity) == [entity]
