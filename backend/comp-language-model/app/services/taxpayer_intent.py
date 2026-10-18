"""Intent routing for taxpayer-grounded chat turns.

A taxpayer question rarely needs every system data source. This module maps the
message to the minimal set of source keys (see ``CONTEXT_SOURCE_KEYS``) worth
loading for that turn, so prompts stay focused and cheap as more sources are
added. It is a deterministic keyword/regex classifier — no LLM call, no latency.

``"profile"`` is always included; the caller loads the base ``financial_profiles``
row regardless. When nothing else matches we fall back to the calculation-centric
sources (snapshot + monthly rollup), which cover the most common "how much tax do
I owe" style questions.
"""

from __future__ import annotations

import re

from app.services.taxpayer_data import CONTEXT_SOURCE_KEYS

# Each source key → regex of trigger terms. Ordering is irrelevant; all matches
# accumulate.
_ROUTES: dict[str, re.Pattern[str]] = {
    "transactions": re.compile(
        r"\b(transaction|txn|payment|deposit|withdrawal|receipt|invoice|statement line|"
        r"bank line|classif\w*|categor\w*|why is (this|that|it) (taxable|exempt|liable)|"
        r"economic event|tax rule code|semantic categor\w*)\b",
        re.I,
    ),
    "recommendations": re.compile(
        r"\b(recommend\w*|suggest\w*|strateg\w*|advice|advis\w*|should i (invest|contribute|"
        r"claim|switch)|savings? (plan|option)|why did you (recommend|suggest)|"
        r"accepted|dismiss\w*|optimi[sz]\w*)\b",
        re.I,
    ),
    "behavioural": re.compile(
        r"\b(risk (tolerance|appetite|profile)|behaviou?ral|my preferenc\w*|how much risk|"
        r"comfort\w* with risk|questionnaire|onboarding answer)\b",
        re.I,
    ),
    "history": re.compile(
        r"\b(history|historical|over time|trend|trajector\w*|past (months?|year)|"
        r"changed? over|compared to (last|previous)|month[- ]over[- ]month|progression)\b",
        re.I,
    ),
    "return_detail": re.compile(
        r"\b(return detail|tax return|filed return|filing|wizard|section \d|"
        r"section completion|schedule \w+|declaration|self[- ]assessment form)\b",
        re.I,
    ),
    "adaptive_amendments": re.compile(
        r"\b(amendment|rule change|law change|new rule|updated rate|rate change|"
        r"config(uration)? change|gazette|effective (from|date)|has the law changed|"
        r"recent(ly)? (changed|updated))\b",
        re.I,
    ),
    "snapshot": re.compile(
        r"\b(tax (payable|liability|due|owed)|how much (tax|do i owe|will i pay)|"
        r"assessable income|taxable income|computation|calculate|calculation|"
        r"my (tax|liability|refund)|reliefs? (claimed|applied)|APIT|PAYE|effective rate)\b",
        re.I,
    ),
    "monthly": re.compile(
        r"\b(monthly|per month|each month|this month|last month|month(ly)? breakdown|"
        r"income by month|monthly income|monthly tax)\b",
        re.I,
    ),
}

# When a turn asks about tax owed we want the monthly rollup alongside the
# snapshot, and vice versa — they are read together.
_COUPLED = {
    "snapshot": {"monthly"},
    "monthly": {"snapshot"},
    "recommendations": {"behavioural"},
}

_CALC_FALLBACK = {"snapshot", "monthly"}


def select_context_sources(message: str, *, routing_enabled: bool = True) -> set[str]:
    """Return the set of source keys to load for this turn (always includes 'profile')."""
    if not routing_enabled:
        return set(CONTEXT_SOURCE_KEYS)

    selected: set[str] = {"profile"}
    for key, pattern in _ROUTES.items():
        if pattern.search(message):
            selected.add(key)
            selected |= _COUPLED.get(key, set())

    if selected == {"profile"}:
        # No specific signal — cover the common "my tax" questions.
        selected |= _CALC_FALLBACK

    return selected
