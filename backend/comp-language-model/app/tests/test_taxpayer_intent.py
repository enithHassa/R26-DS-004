"""Unit tests for taxpayer chat intent routing (no DB required)."""

from __future__ import annotations

from app.services.taxpayer_data import CONTEXT_SOURCE_KEYS
from app.services.taxpayer_intent import select_context_sources


def test_profile_is_always_included():
    assert "profile" in select_context_sources("anything at all")


def test_transaction_question_routes_to_transactions():
    got = select_context_sources("Why is this bank deposit taxable for me?")
    assert "transactions" in got
    assert "recommendations" not in got


def test_recommendation_question_pulls_recommendations_and_behavioural():
    got = select_context_sources("Why did you recommend the EPF top-up strategy?")
    assert {"recommendations", "behavioural"} <= got


def test_tax_owed_question_couples_snapshot_and_monthly():
    got = select_context_sources("How much income tax do I owe this year?")
    assert {"snapshot", "monthly"} <= got


def test_history_question_routes_to_history():
    assert "history" in select_context_sources("How has my income changed over the past months?")


def test_amendment_question_routes_to_adaptive():
    assert "adaptive_amendments" in select_context_sources(
        "Has the law changed recently in a way that affects my rate?"
    )


def test_no_signal_falls_back_to_calc_sources():
    got = select_context_sources("Tell me about my situation.")
    assert got == {"profile", "snapshot", "monthly"}


def test_routing_disabled_loads_everything():
    got = select_context_sources("Why is this deposit taxable?", routing_enabled=False)
    assert got == set(CONTEXT_SOURCE_KEYS)
