from __future__ import annotations

from app.services.domain_gate import assess_domain


def test_weather_question_is_off_topic() -> None:
    result = assess_domain("what is the weather today?", 0.2, enabled=True, min_retrieval_score=0.04)
    assert result.status == "off_topic"
    assert result.message


def test_sun_color_question_is_off_topic() -> None:
    result = assess_domain(
        "what color is the sun",
        0.2,
        enabled=True,
        min_retrieval_score=0.04,
        require_tax_hints=True,
        top_excerpt="Investment income includes dividends, interest, and rent.",
    )
    assert result.status == "off_topic"
    assert result.message


def test_tax_question_stays_in_domain() -> None:
    result = assess_domain(
        "What is personal relief for the year of assessment?",
        0.12,
        enabled=True,
        min_retrieval_score=0.04,
        require_tax_hints=True,
        top_excerpt="Personal relief for the year of assessment is allowed under the IRA.",
    )
    assert result.status == "in_domain"


def test_general_question_without_tax_hints_is_off_topic() -> None:
    result = assess_domain(
        "who won the match yesterday",
        0.2,
        enabled=True,
        min_retrieval_score=0.04,
        require_tax_hints=True,
    )
    assert result.status == "off_topic"
