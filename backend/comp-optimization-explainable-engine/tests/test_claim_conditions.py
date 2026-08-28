"""Act-stated claim conditions for the interview stepper."""

from __future__ import annotations

from oe_engine_app.services.year_store import present_relief


def test_cinema_upgrade_conditions_from_act_wording() -> None:
    presented = present_relief(
        {
            "display_name": "Expenditure on upgrading a cinema",
            "quote": (
                "(iii) in the upgrading of a cinema at a cost of not exceeding "
                "ten million rupees: provided that the deduction under this "
                "subparagraph shall be restricted to one third of the taxable "
                "income of the year of assessment"
            ),
            "eligibility": {
                "text": (
                    "any person incurring expenditure on upgrading a cinema "
                    "costing up to ten million rupees"
                ),
                "quote": (
                    "expenditure incurred on or after April 1, 2021, by any person"
                ),
                "review_status": "pending",
            },
            "cap_amount": "10000000",
            "unit": "lkr",
            "effective_from": "2021-04-01",
            "required_evidence": [],
            "stacking": "",
        }
    )
    texts = " ".join(item["text"] for item in presented["claim_conditions"]).lower()
    assert "cinema" in texts
    assert "any person" in texts
    assert "1 april 2021" in texts
    assert "10,000,000" in texts
    assert "one third" in texts
    assert presented["proof"]["act_names_documents"] is False
    assert presented["proof"]["named_by_act"] == []


def test_proof_uses_only_act_named_documents() -> None:
    presented = present_relief(
        {
            "quote": "expenditure incurred on solar panels",
            "eligibility": {
                "text": "Expenditure on solar panels at the individual's residence",
                "quote": "expenditure incurred on solar panels",
            },
            "required_evidence": ["invoice for solar panels", "photo of installation"],
            "cap_amount": "600000",
            "unit": "lkr",
            "effective_from": "2021-04-01",
        }
    )
    assert presented["proof"]["act_names_documents"] is True
    assert presented["proof"]["named_by_act"] == [
        "invoice for solar panels",
        "photo of installation",
    ]
    assert presented["required_evidence"] == presented["proof"]["named_by_act"]


def test_does_not_invent_documents_when_act_is_silent() -> None:
    presented = present_relief(
        {
            "quote": "(iii) in the upgrading of a cinema at a cost of not exceeding ten million rupees",
            "eligibility": {
                "text": "persons incurring expenditure on upgrading a cinema costing up to ten million rupees"
            },
            "cap_amount": "10000000",
            "unit": "lkr",
            "effective_from": "2021-04-01",
            "required_evidence": [],
        }
    )
    assert presented["proof"]["named_by_act"] == []
    kinds = {item["kind"] for item in presented["claim_conditions"]}
    assert "who" in kinds
    assert "when" in kinds
    assert "cap" in kinds
