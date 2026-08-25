"""Phase 6 — live OpenAI narrative; engine amounts stay source of truth."""

from __future__ import annotations

from unittest.mock import patch

from opt_explain_app.config import get_oe_settings
from opt_explain_app.services.explain import collect_quotes, explain_from_calculation

TYPICAL_INCOME = {
    "employment": 1_800_000,
    "business": 0,
    "investment": 2_000_000,
    "other": 0,
    "interest": 2_000_000,
    "rents": 0,
}

_EXPLAIN_BODY = {
    "assessment_year": "2025_26",
    "income": TYPICAL_INCOME,
    "claims": [],
}


def test_explain_live_cites_fifth_schedule_and_act_02(client, monkeypatch) -> None:
    """Checkpoint: narrative cites Fifth Schedule / Act 02 of 2025; tax stays engine."""
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-not-real")
    get_oe_settings.cache_clear()
    client.post("/api/v1/index/refresh")

    def fake_complete(user_prompt: str, settings) -> dict:
        assert "Fifth Schedule" in user_prompt
        assert "Act No. 02 of 2025" in user_prompt
        return {
            "narrative": (
                "Personal relief follows the Fifth Schedule in Inland Revenue "
                "Amendment Act No. 02 of 2025. The engine applied the quoted cap."
            ),
            "cited_sections": ["Fifth Schedule"],
        }

    with patch("opt_explain_app.services.explain._complete_openai", side_effect=fake_complete):
        response = client.post("/api/v1/explain", json=_EXPLAIN_BODY)

    get_oe_settings.cache_clear()
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["insufficient_evidence"] is False
    assert body["tax_payable"] == 270_000
    assert "Fifth Schedule" in body["narrative"]
    assert "Act No. 02 of 2025" in body["narrative"]
    cites = " ".join(
        f"{c.get('act_name')} {c.get('section_ref')}" for c in body["citations"]
    )
    assert "Fifth Schedule" in cites
    assert "02 of 2025" in cites


def test_explain_does_not_take_tax_from_the_model(client, monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-not-real")
    get_oe_settings.cache_clear()
    client.post("/api/v1/index/refresh")

    def fake_complete(user_prompt: str, settings) -> dict:
        return {
            "narrative": "The tax payable is 9,999,999 according to this sentence.",
            "cited_sections": ["Fifth Schedule"],
        }

    with patch("opt_explain_app.services.explain._complete_openai", side_effect=fake_complete):
        response = client.post("/api/v1/explain", json=_EXPLAIN_BODY)

    get_oe_settings.cache_clear()
    assert response.status_code == 200
    body = response.json()
    assert body["tax_payable"] == 270_000
    assert body["tax_payable"] != 9_999_999


def test_collect_quotes_only_applied_reliefs_and_used_slabs() -> None:
    calc = {
        "relief_lines": [
            {
                "display_name": "Personal relief",
                "applied": 2_000_000,
                "quote": "Personal relief cap",
                "act_name": "Act A",
                "section_ref": "Fifth Schedule",
                "source_doc_id": "a",
            },
            {
                "display_name": "Solar panel",
                "applied": 0,
                "quote": "Solar quote should be excluded",
                "act_name": "Act B",
                "section_ref": "Other",
                "source_doc_id": "b",
            },
        ],
        "slab_lines": [
            {
                "band_label": "first",
                "slice": 100,
                "tax": 6,
                "quote": "Slab quote",
                "act_name": "Act C",
                "section_ref": "First Schedule",
                "source_doc_id": "c",
            },
            {
                "band_label": "unused",
                "slice": 0,
                "tax": 0,
                "quote": "Unused slab",
                "act_name": "Act D",
                "section_ref": "First Schedule",
                "source_doc_id": "d",
            },
        ],
    }
    quotes = collect_quotes(calc)
    assert len(quotes) == 2
    assert all("Solar" not in q["quote"] for q in quotes)
    assert all("Unused slab" not in q["quote"] for q in quotes)


def test_explain_insufficient_evidence_when_quotes_missing() -> None:
    calc = {
        "assessment_year": "2025_26",
        "gross_income": 100,
        "total_reliefs": 50,
        "taxable_income": 50,
        "tax_payable": 3,
        "exclude_source_doc_id": None,
        "relief_lines": [
            {
                "display_name": "Personal relief",
                "applied": 50,
                "quote": "",
                "act_name": "Unknown",
                "section_ref": "",
                "source_doc_id": "x",
            }
        ],
        "slab_lines": [
            {
                "band_label": "band",
                "applied": 0,
                "slice": 50,
                "tax": 3,
                "quote": "",
                "act_name": "",
                "section_ref": "",
                "source_doc_id": "",
            }
        ],
    }
    body = explain_from_calculation(calc)
    assert body["insufficient_evidence"] is True
    assert body["status"] == "insufficient_evidence"
    assert body["tax_payable"] == 3
    assert body["narrative"] == ""


def test_explain_missing_api_key_is_503(client, monkeypatch) -> None:
    class _NoKey:
        OPENAI_API_KEY = None
        COMP_OPTIMIZATION_EXPLAINABLE_OPENAI_EXPLAIN_MODEL = "gpt-4o-mini"

    monkeypatch.setattr(
        "opt_explain_app.services.explain.get_oe_settings",
        lambda: _NoKey(),
    )
    client.post("/api/v1/index/refresh")
    response = client.post("/api/v1/explain", json=_EXPLAIN_BODY)
    assert response.status_code == 503


def test_explain_respects_act_exclude(client, monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-not-real")
    get_oe_settings.cache_clear()
    client.post("/api/v1/index/refresh")

    def fake_complete(user_prompt: str, settings) -> dict:
        assert "1200000" in user_prompt or "1,200,000" in user_prompt
        assert "ird-amend-2022-45" in user_prompt
        return {
            "narrative": "Prior personal cap applies after excluding Act 02 of 2025.",
            "cited_sections": ["Fifth Schedule"],
        }

    with patch("opt_explain_app.services.explain._complete_openai", side_effect=fake_complete):
        response = client.post(
            "/api/v1/explain",
            json={**_EXPLAIN_BODY, "exclude_source_doc_id": "ird-amend-2025-02"},
        )

    get_oe_settings.cache_clear()
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["tax_payable"] != 270_000
    assert any(c.get("source_doc_id") == "ird-amend-2022-45" for c in body["citations"])