from oe_engine_app.services.sub_items import (
    collapse_immediate_repeats,
    complete_from_document,
    split_enumeration,
    strip_running_header,
    sub_items_for,
)

DONATION_QUOTE = (
    "a donation made by an individual or entity in money or otherwise to the "
    "following:- (i) the Government of Sri Lanka; (ii) a local authority; "
    "(iii) any Higher Education Institution established or deemed to be "
    "established under the Universities Act, No. 16 of 1978; (iv) the Buddhist "
    "and Pali University of Sri Lanka or any Higher Educational Institution "
    "established by or under"
)


def test_enumeration_splits_into_one_item_per_roman():
    items = split_enumeration(DONATION_QUOTE)
    assert [item["roman"] for item in items] == ["i", "ii", "iii", "iv"]
    assert items[0]["text"] == "the Government of Sri Lanka"
    assert items[1]["text"] == "a local authority"


def test_a_single_roman_is_the_rows_own_label_not_a_list():
    quote = "(iii) expenditure on upgrading a cinema, not exceeding ten million rupees"
    assert split_enumeration(quote) == []


def test_text_without_romans_has_no_sub_items():
    assert sub_items_for({"quote": "Rs. 500,000 for each year of assessment"}) == []


def test_component_ids_are_namespaced_by_relief():
    items = sub_items_for(
        {"quote": DONATION_QUOTE, "compare_group_id": "donation_to_government"}
    )
    assert items[0]["component_id"] == "donation_to_government:i"
    assert items[3]["component_id"] == "donation_to_government:iv"


def test_long_item_gets_a_short_label_but_keeps_the_full_quote():
    items = sub_items_for({"quote": DONATION_QUOTE, "compare_group_id": "g"})
    third = items[2]
    assert third["label"].endswith("...")
    assert len(third["label"]) <= 93
    assert third["quote"].endswith("Universities Act, No. 16 of 1978")


def test_repeated_span_from_the_pdf_is_collapsed_once():
    span = "the same clause repeated verbatim by the extractor here; "
    assert collapse_immediate_repeats(f"start {span}{span}end") == f"start {span}end"


def test_collapse_leaves_text_without_a_repeat_alone():
    text = "(i) the Government of Sri Lanka; (ii) a local authority; (iii) a fund"
    assert collapse_immediate_repeats(text) == text


def test_running_header_is_matched_despite_registry_punctuation():
    text = "Authority Act, No. 17 of 1979; 218 Inland Revenue Act, No. 24 of 2017 (viii) a fund"
    out = strip_running_header(text, "Inland Revenue Act No. 24 of 2017")
    assert "218" not in out
    assert out.startswith("Authority Act, No. 17 of 1979;")
    assert out.endswith("(viii) a fund")


def test_truncated_quote_is_completed_from_the_document():
    document = (
        "preamble text " + DONATION_QUOTE + " the Buddhist and Pali University Act, "
        "No. 74 of 1981; (v) a fund established by the Government of Sri Lanka; "
        "(c) profits remitted to the President's Fund"
    )
    items = sub_items_for({"quote": DONATION_QUOTE, "compare_group_id": "g"}, document)
    assert [item["roman"] for item in items] == ["i", "ii", "iii", "iv", "v"]
    assert items[4]["label"] == "a fund established by the Government of Sri Lanka"


def test_document_without_the_quote_leaves_it_untouched():
    assert complete_from_document(DONATION_QUOTE, "unrelated act text") == DONATION_QUOTE


def test_completion_never_runs_into_the_next_paragraph():
    document = (
        DONATION_QUOTE + " the rest of item four; (v) a fund established by the "
        "Government; (c) a different paragraph"
    )
    extended = complete_from_document(DONATION_QUOTE, document)
    assert "(c) a different paragraph" not in extended
    assert extended.endswith("(v) a fund established by the Government")


def test_a_list_that_does_not_continue_leaves_the_quote_as_stored():
    document = DONATION_QUOTE + " the rest of item four; (c) a different paragraph"
    assert complete_from_document(DONATION_QUOTE, document) == DONATION_QUOTE
