"""Block off-topic or weakly matched questions before retrieval answers are shown."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

DomainStatus = Literal["in_domain", "off_topic", "weak_match"]

_STOPWORDS = frozenset(
    {
        "what",
        "when",
        "where",
        "which",
        "who",
        "whom",
        "whose",
        "why",
        "how",
        "does",
        "do",
        "did",
        "can",
        "could",
        "should",
        "would",
        "will",
        "the",
        "this",
        "that",
        "these",
        "those",
        "about",
        "with",
        "from",
        "into",
        "your",
        "have",
        "has",
        "been",
        "were",
        "was",
        "are",
        "for",
        "and",
        "but",
        "not",
        "you",
        "tell",
        "give",
        "explain",
        "much",
        "many",
        "more",
        "most",
        "some",
        "such",
        "than",
        "then",
        "them",
        "they",
        "their",
        "there",
    }
)

_OFF_TOPIC_PATTERNS: tuple[re.Pattern[str], ...] = tuple(
    re.compile(pattern, re.IGNORECASE)
    for pattern in (
        r"\bweather\b",
        r"\bforecast\b",
        r"\btemperature\b",
        r"\brain(?:ing)?\b",
        r"\bsun(?:light|rise|set|shine)?\b",
        r"\bmoon\b",
        r"\bstar[s]?\b",
        r"\bplanet\b",
        r"\bcolor\b",
        r"\bcolour\b",
        r"\bsky\b",
        r"\bocean\b",
        r"\bmountain\b",
        r"\bchemistry\b",
        r"\bphysics\b",
        r"\bbiology\b",
        r"\bscience\b",
        r"\balgebra\b",
        r"\bgeometry\b",
        r"\bcalculus\b",
        r"\bmathematics\b",
        r"\banimal\b",
        r"\bdog\b",
        r"\bcat\b",
        r"\bbird\b",
        r"\bfootball\b",
        r"\bcricket\b",
        r"\bbasketball\b",
        r"\bsoccer\b",
        r"\bmovie\b",
        r"\bfilm\b",
        r"\bmusic\b",
        r"\bsong\b",
        r"\bdance\b",
        r"\bgame\b",
        r"\bvideo game\b",
        r"\brecipe\b",
        r"\bcook(?:ing)?\b",
        r"\bfood\b",
        r"\brestaurant\b",
        r"\bjoke\b",
        r"\bfunny\b",
        r"\bhello\b",
        r"\bhi there\b",
        r"\bhow are you\b",
        r"\bwho are you\b",
        r"\bwhat time is it\b",
        r"\bwhat is your name\b",
        r"\btell me a\b",
        r"\bstock price\b",
        r"\bcrypto\b",
        r"\bbitcoin\b",
        r"\bethereum\b",
        r"\bforex\b",
        r"\btrading\b",
        r"\bhistory of\b",
        r"\bworld war\b",
        r"\bking\b",
        r"\bqueen\b",
        r"\bcapital city\b",
        r"\bpopulation of\b",
    )
)

_TAX_HINT_PATTERNS: tuple[re.Pattern[str], ...] = tuple(
    re.compile(pattern, re.IGNORECASE)
    for pattern in (
        r"\btax(?:es)?\b",
        r"\brelief\b",
        r"\bincome\b",
        r"\bresident\b",
        r"\bnon[- ]resident\b",
        r"\bassessment year\b",
        r"\bdeduction\b",
        r"\bwithholding\b",
        r"\bvat\b",
        r"\bira\b",
        r"\binland revenue\b",
        r"\bemploy(?:ment|ee|er)\b",
        r"\bbusiness income\b",
        r"\bpaye\b",
        r"\bwht\b",
        r"\bsri lanka\b",
        r"\breturn\b",
        r"\bfiling\b",
        r"\bstatute\b",
        r"\bact\b",
        r"\bexempt(?:ion)?\b",
        r"\bslab\b",
        r"\brate\b",
        r"\bpenalt(?:y|ies)\b",
        r"\baudit\b",
        r"\bclaim(?:ed|ing)?\b",
        r"\bpayable\b",
        r"\binstallment\b",
        r"\bassess(?:ment|able)?\b",
        r"\bdividend\b",
        r"\binterest\b",
        r"\brent\b",
        r"\broyalt(?:y|ies)\b",
        r"\bremuneration\b",
        r"\bsalary\b",
        r"\bwage[s]?\b",
    )
)

_OFF_TOPIC_MESSAGE = (
    "This tool only answers Sri Lankan income-tax questions. "
    "Try a tax topic such as personal relief, residency, or filing deadlines."
)


@dataclass(frozen=True, slots=True)
class DomainAssessment:
    status: DomainStatus
    message: str | None = None


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip().lower())


def _content_tokens(text: str) -> set[str]:
    return {
        token
        for token in re.findall(r"[a-z0-9]+", text.lower())
        if len(token) >= 4 and token not in _STOPWORDS
    }


def _has_tax_hints(text: str) -> bool:
    return any(pattern.search(text) for pattern in _TAX_HINT_PATTERNS)


def _off_topic_match(text: str) -> bool:
    return any(pattern.search(text) for pattern in _OFF_TOPIC_PATTERNS)


def _question_corpus_overlap(question: str, excerpt: str | None) -> float | None:
    if not excerpt or not excerpt.strip():
        return None
    question_tokens = _content_tokens(question)
    if not question_tokens:
        return None
    excerpt_tokens = _content_tokens(excerpt)
    if not excerpt_tokens:
        return 0.0
    return len(question_tokens & excerpt_tokens) / len(question_tokens)


def assess_domain(
    text: str,
    top_score: float | None,
    *,
    enabled: bool,
    min_retrieval_score: float,
    require_tax_hints: bool = True,
    top_excerpt: str | None = None,
    min_question_overlap: float = 0.15,
) -> DomainAssessment:
    if not enabled:
        return DomainAssessment(status="in_domain")

    normalized = _normalize(text)
    if not normalized:
        return DomainAssessment(
            status="off_topic",
            message="Enter a Sri Lankan income-tax question to search the legal corpus.",
        )

    has_tax_hints = _has_tax_hints(normalized)
    if _off_topic_match(normalized) and not has_tax_hints:
        return DomainAssessment(status="off_topic", message=_OFF_TOPIC_MESSAGE)

    if require_tax_hints and not has_tax_hints:
        return DomainAssessment(status="off_topic", message=_OFF_TOPIC_MESSAGE)

    if top_score is None:
        return DomainAssessment(
            status="weak_match",
            message="No legal sources were found for this question.",
        )

    # Skip overlap check for short/general questions — they have too few tokens
    # to measure meaningfully, and tax hints already confirm they are on-topic.
    question_tokens = _content_tokens(normalized)
    if len(question_tokens) >= 3:
        overlap = _question_corpus_overlap(normalized, top_excerpt)
        if overlap is not None and overlap < min_question_overlap:
            return DomainAssessment(
                status="off_topic",
                message=(
                    "The retrieved legal passages do not appear to answer this question. "
                    "Ask a Sri Lankan income-tax question instead."
                ),
            )

    if top_score < min_retrieval_score:
        return DomainAssessment(
            status="weak_match",
            message=(
                "The legal corpus does not appear to contain a strong match for this question. "
                "Rephrase it as a Sri Lankan income-tax question."
            ),
        )

    return DomainAssessment(status="in_domain")
