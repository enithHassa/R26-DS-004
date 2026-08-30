"""Normalize user queries (Singlish / informal phrasing) before NLU and retrieval."""

from __future__ import annotations

import re

# Common informal Sri Lankan English / Sinhala-mix → standard tax phrasing (case-insensitive).
_SINGLISH_REPLACEMENTS: tuple[tuple[re.Pattern[str], str], ...] = tuple(
    (re.compile(pattern, re.IGNORECASE), repl)
    for pattern, repl in (
        # ── Tax / payment ──────────────────────────────────────────────────
        (r"\btax ekak\b", "tax"),
        (r"\btax eka\b", "tax"),
        (r"\btax ekata\b", "for tax"),
        (r"\bdenna one\b", "need to pay"),
        (r"\bdenna\b", "pay"),
        (r"\bgevanawa\b", "pay"),
        (r"\bkathanawa\b", "deduct"),
        (r"\bkapanawa\b", "deduct"),
        # ── Filing / returns ────────────────────────────────────────────────
        (r"\bhadanna\b", "file"),
        (r"\bhadannada\b", "need to file"),
        (r"\breturn ekak\b", "tax return"),
        (r"\breturn eka\b", "tax return"),
        (r"\bsubmit karanna\b", "submit"),
        # ── Income / salary ─────────────────────────────────────────────────
        (r"\bsalary ekak\b", "salary"),
        (r"\bsalary eka\b", "salary"),
        (r"\bincome ekak\b", "income"),
        (r"\bincome eka\b", "income"),
        (r"\bwage earner ekekuta\b", "wage earner"),
        (r"\bwage ekekuta\b", "wage earner"),
        (r"\bekekuta\b", "for individual"),
        (r"\bekek\b", "individual"),
        # ── Relief / deductions ─────────────────────────────────────────────
        (r"\brelief eka\b", "personal relief"),
        (r"\brelief ekak\b", "personal relief"),
        (r"\brelief ekata\b", "for personal relief"),
        (r"\bdeduction ekak\b", "deduction"),
        # ── Residency ───────────────────────────────────────────────────────
        (r"\bresident da\b", "am I resident"),
        (r"\bresident kෙnekda\b", "am I resident"),
        (r"\bnon resident\b", "non-resident"),
        (r"\bnonresident\b", "non-resident"),
        # ── Question words ──────────────────────────────────────────────────
        (r"\bmokakda\b", "what is"),
        (r"\bmokada\b", "what"),
        (r"\bkohomada\b", "how"),
        (r"\bkohomath\b", "how much"),
        (r"\baiyya\b", ""),
        (r"\bneda\b", "isn't it"),
        (r"\bda\b(?=\s|$)", ""),          # sentence-final 'da' (question particle)
        # ── Pronouns ────────────────────────────────────────────────────────
        (r"\bapan\b", "our"),
        (r"\bmama\b", "I"),
        (r"\bmamath\b", "I also"),
        (r"\boya\b", "you"),
        # ── Freelance / employment type ─────────────────────────────────────
        (r"\bfree lance\b", "freelance"),
        (r"\bfreelance ekek\b", "freelancer"),
        (r"\bself employed\b", "self-employed"),
        # ── Assessment year informal ────────────────────────────────────────
        (r"\bthis year\b", "current assessment year"),
        (r"\bnext year\b", "next assessment year"),
        (r"\blast year\b", "previous assessment year"),
    )
)


def normalize_query(text: str) -> str:
    """Return cleaned query text suitable for retrieval and intent models."""
    t = text.replace("\r\n", "\n").strip()
    t = re.sub(r"\s+", " ", t)
    for pattern, repl in _SINGLISH_REPLACEMENTS:
        t = pattern.sub(repl, t)
    # Clean up any double spaces left after removals
    t = re.sub(r"\s{2,}", " ", t)
    return t.strip()
