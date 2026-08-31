"""A relief split across its listed recipients still lands as one deduction."""

from __future__ import annotations

from typing import Any

from oe_engine_app.services.calculate import _apply_one

INCOME = {
    "employment": 1_800_000,
    "business": 0,
    "investment": 2_000_000,
    "other": 0,
    "interest": 2_000_000,
    "rents": 0,
    "gross": 3_800_000,
}


def entry(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "entry_id": "oee-act-24-2017:fifth_schedule:relief:2",
        "compare_group_id": "donation_to_government_or_approved_fund",
        "display_name": "Donation to Government or Approved Fund",
        "input_kind": "amount",
        "cap_amount": None,
        "unit": "lkr",
        "sub_items": [
            {"component_id": "d:i", "roman": "i", "label": "Government", "quote": "x"},
            {"component_id": "d:ii", "roman": "ii", "label": "Local authority", "quote": "y"},
        ],
    }
    base.update(overrides)
    return base


def claim(*amounts: int) -> dict[str, Any]:
    return {
        "entry_id": entry()["entry_id"],
        "amount": 0,
        "components": [
            {"component_id": f"d:{roman}", "amount": amount}
            for roman, amount in zip(("i", "ii"), amounts, strict=False)
        ],
    }


def test_components_are_added_into_one_claim():
    line = _apply_one(entry(), INCOME, claim(120_000, 30_000))
    assert line["claim"] == 150_000
    assert line["applied"] == 150_000


def test_the_split_is_kept_on_the_line_for_the_result_page():
    line = _apply_one(entry(), INCOME, claim(120_000, 30_000))
    assert line["components"] == [
        {"component_id": "d:i", "amount": 120_000},
        {"component_id": "d:ii", "amount": 30_000},
    ]
    assert "120000 + 30000" in line["formula"]


def test_a_cap_still_limits_the_combined_total():
    line = _apply_one(entry(cap_amount="100000"), INCOME, claim(120_000, 30_000))
    assert line["claim"] == 150_000
    assert line["applied"] == 100_000


def test_components_override_the_flat_amount():
    body = claim(10_000, 5_000)
    body["amount"] = 999_999
    assert _apply_one(entry(), INCOME, body)["applied"] == 15_000


def test_a_relief_with_no_components_still_uses_the_flat_amount():
    body = {"entry_id": entry()["entry_id"], "amount": 40_000}
    assert _apply_one(entry(), INCOME, body)["applied"] == 40_000


def test_empty_boxes_leave_the_relief_unclaimed():
    line = _apply_one(entry(), INCOME, claim(0, 0))
    assert line["claim"] == 0
    assert line["applied"] == 0


def test_malformed_component_rows_are_ignored():
    body = {
        "entry_id": entry()["entry_id"],
        "amount": 0,
        "components": ["not a row", {"component_id": "", "amount": 500}, {"amount": 700}],
    }
    line = _apply_one(entry(), INCOME, body)
    assert line["components"] == []
    assert line["applied"] == 0


def test_a_skipped_relief_ignores_its_boxes():
    body = claim(120_000, 30_000)
    body["skipped"] = True
    assert _apply_one(entry(), INCOME, body)["applied"] == 0
