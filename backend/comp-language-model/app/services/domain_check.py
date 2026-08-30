"""Domain gating — classify whether a query is about Sri Lankan income tax.

Returns one of three statuses:
  in_domain    — question is clearly about SL income tax / related topics
  weak_match   — borderline; results shown with a caution banner
  off_topic    — clearly unrelated; results are suppressed on the frontend
"""

from __future__ import annotations

import re

# ---------------------------------------------------------------------------
# Keyword lists
# ---------------------------------------------------------------------------

_STRONG_KEYWORDS: frozenset[str] = frozenset({
    # Core tax terms
    "tax", "taxes", "taxation", "taxable", "taxed",
    "income", "salary", "wages", "employment", "employer", "employee",
    "relief", "deduction", "exemption", "allowance",
    "assessment", "year of assessment", "return", "filing",
    "ira", "inland revenue", "ird", "commissioner",
    "resident", "residency", "non-resident",
    "withholding", "paye", "apit",
    "gross income", "assessable income", "net income",
    "rate", "slab", "band", "percent", "%",
    "penalty", "surcharge", "fine",
    "dividend", "interest", "rent", "royalt",
    "capital gain", "disposal", "asset",
    "partnership", "company", "corporation", "business",
    "profit", "loss", "expense", "deductible",
    "investment", "shares", "securities",
    "schedule", "section", "act", "statute", "regulation",
    "lkr", "rupee", "rs.",
    "donation", "charity", "contribution",
    "insurance", "pension", "retirement",
    "home loan", "mortgage",
    "appeal", "objection", "assessment",
    "quarter", "installment", "payment",
    "sri lanka", "sri lankan", "ceylon",
    "ita", "irda", "income tax act",
})

_STOP_TOPICS: frozenset[str] = frozenset({
    "weather", "color", "colour", "sun", "moon", "star", "planet",
    "recipe", "food", "cook", "sport", "game", "movie", "film",
    "music", "song", "dance", "art", "paint",
    "animal", "dog", "cat", "bird",
    "history", "war", "battle", "king", "queen",
    "science", "chemistry", "physics", "biology",
    "math", "algebra", "geometry", "calculus",
    "language", "grammar", "spell",
    "country", "geography", "capital city",
    "joke", "funny", "humor",
})

# Minimum top-1 retrieval score to be considered meaningful
_SCORE_THRESHOLD_IN_DOMAIN: float = 0.06
_SCORE_THRESHOLD_WEAK: float = 0.03


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def check_domain(
    query: str,
    top_score: float | None = None,
) -> tuple[str, str | None]:
    """Return (status, message) for a query.

    status is one of: "in_domain", "weak_match", "off_topic"
    message is None when in_domain.
    """
    q = query.lower()
    tokens = set(re.split(r"[\s,;.?!\"'()\[\]]+", q))

    # Hard stop — obviously off-topic words with no tax keywords
    has_stop = bool(tokens & _STOP_TOPICS)
    has_tax = any(kw in q for kw in _STRONG_KEYWORDS)

    if has_stop and not has_tax:
        return (
            "off_topic",
            "This system only answers questions about Sri Lankan income tax. "
            "Please ask about tax rates, reliefs, filing deadlines, residency rules, "
            "or related topics.",
        )

    # Score-based weak match (corpus didn't return a meaningful hit)
    if top_score is not None and top_score < _SCORE_THRESHOLD_WEAK and not has_tax:
        return (
            "off_topic",
            "Your question doesn't appear to be about Sri Lankan income tax. "
            "No relevant law passages were found. Try rephrasing your question "
            "using tax terms.",
        )

    if top_score is not None and top_score < _SCORE_THRESHOLD_IN_DOMAIN and not has_tax:
        return (
            "weak_match",
            "The retrieved passages have a low relevance score — your question may not "
            "be directly about Sri Lankan income tax. Results are shown but may not be "
            "accurate for your query.",
        )

    return "in_domain", None
