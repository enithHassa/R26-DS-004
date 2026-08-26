"""A relief that cites numbered items of another paragraph resolves them."""

from __future__ import annotations

from typing import Any

from oe_engine_app.services.cross_reference import (
    attach_covered_items,
    parse_item_reference,
    resolve_covered_items,
)

CARRY_FORWARD_ELIGIBILITY = (
    "individual or entity with qualifying payments referred to in items (i) and (v) "
    "of sub-paragraph (b) of paragraph 1 of the Fifth Schedule"
)


def donation_relief(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "compare_group_id": "donation_to_government_or_approved_fund",
        "display_name": "Donation to government or approved fund",
        "act_name": "Inland Revenue Act No. 24 of 2017",
        "section_ref": "Section 52",
        "paragraph_ref": "1(b)",
        "sub_items": [
            {"component_id": "d:i", "roman": "i", "label": "the Government", "quote": "q1"},
            {"component_id": "d:ii", "roman": "ii", "label": "a local authority", "quote": "q2"},
            {"component_id": "d:v", "roman": "v", "label": "a Government fund", "quote": "q5"},
        ],
    }
    base.update(overrides)
    return base


def carry_forward(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "compare_group_id": "qualifying_payment_carry_forward",
        "paragraph_ref": "5(4)",
        "eligibility": {"text": CARRY_FORWARD_ELIGIBILITY},
        "quote": "such amount ... shall be carried forward",
    }
    base.update(overrides)
    return base


def test_reference_is_parsed_into_romans_and_a_paragraph():
    reference = parse_item_reference(CARRY_FORWARD_ELIGIBILITY)
    assert reference is not None
    assert reference.romans == ["i", "v"]
    assert reference.paragraph_ref == "1(b)"


def test_text_without_a_reference_parses_to_nothing():
    assert parse_item_reference("Rs. 500,000 for each year of assessment") is None
    assert parse_item_reference("expenditure under item (iii) of the Schedule") is None


def test_only_the_referenced_items_are_resolved():
    covers = resolve_covered_items(carry_forward(), [donation_relief()])
    assert covers is not None
    assert [item["roman"] for item in covers["items"]] == ["i", "v"]
    assert covers["items"][1]["label"] == "a Government fund"


def test_resolution_carries_the_source_provenance():
    covers = resolve_covered_items(carry_forward(), [donation_relief()])
    assert covers is not None
    assert covers["paragraph_ref"] == "1(b)"
    assert covers["source_group"] == "donation_to_government_or_approved_fund"
    assert covers["source_act_name"] == "Inland Revenue Act No. 24 of 2017"


def test_a_different_paragraph_is_not_matched():
    other = donation_relief(paragraph_ref="1(a)")
    assert resolve_covered_items(carry_forward(), [other]) is None


def test_punctuation_in_the_paragraph_ref_still_matches():
    other = donation_relief(paragraph_ref="1 (b)")
    covers = resolve_covered_items(carry_forward(), [other])
    assert covers is not None
    assert len(covers["items"]) == 2


def test_missing_romans_in_the_source_resolve_to_nothing():
    thin = donation_relief(
        sub_items=[
            {"component_id": "d:ii", "roman": "ii", "label": "a local authority", "quote": "q"}
        ]
    )
    assert resolve_covered_items(carry_forward(), [thin]) is None


def test_a_relief_never_resolves_against_itself():
    self_referencing = donation_relief(
        paragraph_ref="1(b)", eligibility={"text": CARRY_FORWARD_ELIGIBILITY}
    )
    assert resolve_covered_items(self_referencing, [self_referencing]) is None


def test_attach_marks_only_the_relief_that_cites_another():
    reliefs = [donation_relief(), carry_forward()]
    attach_covered_items(reliefs)
    assert "covers" not in reliefs[0]
    assert reliefs[1]["covers"]["items"][0]["roman"] == "i"
