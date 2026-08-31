"""An eligibility threshold must not be compiled as a deduction ceiling."""

from __future__ import annotations

from oe_engine_app.services.calculate import binder_for
from oe_engine_app.services.cap_semantics import cap_is_threshold, strip_threshold_cap
from oe_engine_app.services.compiler import infer_input_kind

FILM = (
    "(i) in the production of a film at a cost of (including promotional "
    "expenditure of such film) not less than five million rupees"
)
CINEMA = (
    "(ii) in the construction and equipping of a new cinema at a cost of not "
    "exceeding twenty-five million rupees"
)


def test_not_less_than_is_a_threshold() -> None:
    assert cap_is_threshold(FILM, "5000000") is True


def test_not_exceeding_is_a_real_cap() -> None:
    assert cap_is_threshold(CINEMA, "25000000") is False


def test_no_cap_means_nothing_to_reclassify() -> None:
    assert cap_is_threshold(FILM, None) is False
    assert cap_is_threshold(FILM, "") is False


def test_threshold_cap_is_moved_not_discarded() -> None:
    out = strip_threshold_cap({"quote": FILM, "cap_amount": "5000000"})
    assert out["cap_amount"] is None
    assert out["min_qualifying_amount"] == "5000000"
    assert out["quote"] == FILM


def test_threshold_parsed_from_quote_when_cap_empty() -> None:
    out = strip_threshold_cap({"quote": FILM, "cap_amount": None})
    assert out["min_qualifying_amount"] == "5000000"


def test_film_claim_below_minimum_applies_zero() -> None:
    from oe_engine_app.services.calculate import _apply_one

    entry = strip_threshold_cap(
        {
            "entry_id": "film-1",
            "compare_group_id": "qp_film_production",
            "display_name": "Expenditure on film production",
            "quote": FILM,
            "cap_amount": "5000000",
            "unit": "lkr",
            "input_kind": "amount",
            "engine_binding": {"kind": "none"},
        }
    )
    income = {
        "gross": 3_800_000.0,
        "employment": 1_800_000.0,
        "business": 0.0,
        "interest": 0.0,
        "rents": 0.0,
    }
    below = _apply_one(entry, income, {"amount": 230, "affirmed": True, "skipped": False})
    assert below["applied"] == 0.0
    assert below["min_qualifying"] == 5_000_000.0
    assert "below min qualifying" in below["formula"]

    ok = _apply_one(
        entry, income, {"amount": 5_000_000, "affirmed": True, "skipped": False}
    )
    assert ok["applied"] == 5_000_000.0


def test_cinema_ceiling_still_caps_claim() -> None:
    from oe_engine_app.services.calculate import _apply_one

    entry = {
        "entry_id": "cinema-1",
        "compare_group_id": "qp_cinema_construction",
        "display_name": "Expenditure on construction",
        "quote": CINEMA,
        "cap_amount": "25000000",
        "unit": "lkr",
        "input_kind": "amount",
        "engine_binding": {"kind": "none"},
    }
    income = {
        "gross": 3_800_000.0,
        "employment": 1_800_000.0,
        "business": 0.0,
        "interest": 0.0,
        "rents": 0.0,
    }
    line = _apply_one(
        entry, income, {"amount": 30_000_000, "affirmed": True, "skipped": False}
    )
    assert line["applied"] == 25_000_000.0
    assert line["min_qualifying"] is None
    assert line["cap"] == 25_000_000.0


def test_an_uncapped_relief_with_a_minimum_spend_stays_claimable() -> None:
    payload = strip_threshold_cap(
        {
            "compare_group_id": "film_production_expenditure",
            "quote": FILM,
            "cap_amount": "5000000",
            "input_kind": "notice",
        }
    )
    assert infer_input_kind(payload) == "amount"
    assert _binder(payload) == "min(claim, cap)"


def test_ceiling_payload_is_untouched() -> None:
    payload = {"quote": CINEMA, "cap_amount": "25000000"}
    assert strip_threshold_cap(payload) is payload


def _binder(payload: dict) -> str:
    payload = dict(payload)
    payload.setdefault("unit", "lkr")
    payload.setdefault("engine_binding", {"kind": "none"})
    payload["input_kind"] = infer_input_kind(payload)
    return binder_for(payload)


def test_a_newly_surfaced_capped_relief_must_be_claimed() -> None:
    payload = {
        "compare_group_id": "cinema_upgrading_expenditure",
        "paragraph_ref": "1(f)(iii)",
        "cap_amount": "10000000",
    }
    assert infer_input_kind(payload) == "amount"
    assert _binder(payload) == "min(claim, cap)"


def test_modelled_reliefs_still_apply_automatically() -> None:
    for group, cap in (
        ("personal_relief", "1800000"),
        ("senior_citizen_interest_income_relief", "1500000"),
        ("donation_to_charitable_institution", "75000"),
    ):
        payload = {"compare_group_id": group, "cap_amount": cap}
        assert infer_input_kind(payload) == "notice", group
        assert _binder(payload) == "auto_cap", group


def test_foreign_currency_relief_is_claimable_not_auto() -> None:
    payload = {
        "compare_group_id": "foreign_currency_income_relief",
        "cap_amount": "15000000",
    }
    assert infer_input_kind(payload) == "amount"
    assert _binder(payload) == "min(claim, cap)"

def test_an_uncapped_unknown_relief_stays_a_notice() -> None:
    payload = {"compare_group_id": "new_undertaking_exemption", "cap_amount": None}
    assert infer_input_kind(payload) == "notice"
    assert _binder(payload) == "notice"


def test_extraction_cannot_declare_an_unmodelled_capped_relief_automatic() -> None:
    payload = {
        "compare_group_id": "cinema_upgrading_expenditure",
        "cap_amount": "10000000",
        "input_kind": "notice",
    }
    assert infer_input_kind(payload) == "amount"
    assert _binder(payload) == "min(claim, cap)"


def test_an_explicit_claim_kind_is_respected() -> None:
    payload = {
        "compare_group_id": "cinema_upgrading_expenditure",
        "cap_amount": "10000000",
        "input_kind": "yes_no_amount",
    }
    assert infer_input_kind(payload) == "yes_no_amount"
