"""Defined terms are read from the Act and attached only where they are used."""

from __future__ import annotations

from oe_engine_app.services.definitions import (
    definitions_for,
    extract_definitions,
    interpretation_section_ref,
)

INTERPRETATION = (
    "195. In this Act, unless the context otherwise requires - "
    "\u201csenior citizen\u201d with respect to a year of assessment means an individual "
    "who is - (a) a citizen of Sri Lanka during the year of assessment; (b) resident "
    "in Sri Lanka for the year of assessment; and (c) who is sixty years old or above "
    "at any time during the year of assessment; "
    "\u201cfinancial institution\u201d means any company carrying on banking business; "
    "\u201cperson\u201d means an individual or entity; "
    "\u201cService Provider\u201d shall be appointed by the Minister; "
)

SENIOR_RELIEF = {
    "quote": (
        "in the case of an individual who is a senior citizen in a year with interest "
        "income derived from a financial institution"
    ),
    "eligibility": {"text": "individuals who are senior citizens"},
}


def test_definitions_are_keyed_by_term():
    found = extract_definitions(INTERPRETATION)
    assert "senior citizen" in found
    assert "financial institution" in found
    assert found["senior citizen"].endswith(
        "sixty years old or above at any time during the year of assessment"
    )


def test_a_quoted_phrase_without_a_defining_verb_is_not_a_definition():
    assert "service provider" not in extract_definitions(INTERPRETATION)


def test_the_interpretation_section_number_is_recovered():
    assert interpretation_section_ref(INTERPRETATION) == "195"
    assert interpretation_section_ref("no interpretation section here") == ""


def test_only_terms_the_relief_uses_are_attached():
    terms = definitions_for(SENIOR_RELIEF, extract_definitions(INTERPRETATION), "195")
    assert [d["term"] for d in terms] == ["senior citizen", "financial institution"]


def test_single_word_terms_are_never_attached():
    relief = {"quote": "a payment made by a person to another person"}
    assert definitions_for(relief, extract_definitions(INTERPRETATION)) == []


def test_terms_follow_the_order_the_relief_mentions_them():
    relief = {"quote": "interest from a financial institution paid to a senior citizen"}
    terms = definitions_for(relief, extract_definitions(INTERPRETATION))
    assert [d["term"] for d in terms] == ["financial institution", "senior citizen"]


def test_a_relief_that_uses_no_defined_term_gets_nothing():
    relief = {"quote": "Rs. 500,000 for each year of assessment"}
    assert definitions_for(relief, extract_definitions(INTERPRETATION)) == []


def test_the_section_ref_travels_with_each_definition():
    terms = definitions_for(SENIOR_RELIEF, extract_definitions(INTERPRETATION), "195")
    assert {d["section_ref"] for d in terms} == {"195"}
