"""Lex Specialis-inspired reranking for retrieved chunk hits."""

from __future__ import annotations

import re

# Higher authority tiers and instrument types score better during reranking.
# Keys match corpus / KG join `instrument_type` values (base_act, amendment_act, …).
_TIER_BOOST: dict[str, float] = {
    "A": 0.14,
    "B": 0.04,
    "C": -0.02,
}

_INSTRUMENT_BOOST: dict[str, float] = {
    "amendment_act": 0.12,
    "amendment": 0.12,
    "base_act": 0.10,
    "act": 0.10,
    "consolidated": 0.11,
    "circular": 0.07,
    "regulation": 0.05,
    "guide": -0.03,
    "hub_summary": -0.05,
}

# Navigational / TOC-like passages pollute TF-IDF for short legal questions.
_DOT_LEADER = re.compile(r"\.{4,}|…{2,}")
_TOC_CHAPTER = re.compile(r"CHAPTER\s+\d+.{0,40}\.{4,}", re.IGNORECASE)
_PAGE_DOTTED = re.compile(r"\d+\s*\.{5,}\s*\d+")


def is_navigational_noise(text: str | None) -> bool:
    """True for TOC / dotted-leader / near-empty chunks that should not cite."""
    t = (text or "").strip()
    if not t:
        return True
    alpha = sum(1 for c in t if c.isalpha())
    # Empty / punctuation-only crumbs — keep short alphabetic sentences.
    if alpha < 12:
        return True
    if _DOT_LEADER.search(t) and t.count(".") >= 8:
        return True
    if _TOC_CHAPTER.search(t) or _PAGE_DOTTED.search(t):
        return True
    if alpha < 45 and len(t) > 80:
        return True
    # Long dotted leaders relative to letters (classic TOC layout).
    if t.count(".") > max(25, alpha // 3):
        return True
    return False


def navigational_penalty(text: str | None) -> float:
    """Soft score penalty when a chunk looks navigational but is still usable."""
    if is_navigational_noise(text):
        return -0.20
    t = text or ""
    if _DOT_LEADER.search(t):
        return -0.08
    return 0.0


_STOP = frozenset(
    {
        "what",
        "when",
        "where",
        "which",
        "that",
        "this",
        "with",
        "from",
        "have",
        "does",
        "about",
        "into",
        "your",
        "their",
        "for",
        "the",
        "and",
        "are",
        "was",
        "were",
        "been",
        "being",
        "assessment",
        "year",
        "income",
        "tax",
    }
)


def query_overlap_boost(query: str | None, text: str | None) -> float:
    """Reward chunks that literally contain distinctive query terms (e.g. dividend + withhold)."""
    if not query or not text:
        return 0.0
    terms = {
        w
        for w in re.findall(r"[a-z0-9%]{4,}", query.lower())
        if w not in _STOP
    }
    if not terms:
        return 0.0
    lowered = text.lower()
    hits = sum(1 for w in terms if w in lowered)
    if hits == 0:
        return 0.0
    # Cap so overlap cannot overwhelm Lex Specialis / TF-IDF.
    return min(0.18, 0.045 * hits)


def lex_specialis_boost(meta: dict[str, str | None]) -> float:
    """Return a small score boost from corpus / KG metadata."""
    boost = 0.0
    tier = (meta.get("tier") or "").strip().upper()
    if tier in _TIER_BOOST:
        boost += _TIER_BOOST[tier]
    instrument = (meta.get("instrument_type") or "").strip().lower()
    if instrument in _INSTRUMENT_BOOST:
        boost += _INSTRUMENT_BOOST[instrument]
    else:
        # Unknown instrument types: slight preference for Tier A docs only.
        if tier == "A":
            boost += 0.05
    return boost


def rerank_hits(
    hits: list[tuple[str, float]],
    join_map: dict[str, dict[str, str | None]],
    chunk_texts: dict[str, str] | None = None,
    *,
    query: str | None = None,
    drop_navigational: bool = True,
    apply_lex_boost: bool = True,
) -> list[tuple[str, float]]:
    """Rerank (chunk_id, score) pairs using Lex Specialis metadata + text quality."""
    if not hits:
        return hits

    texts = chunk_texts or {}
    kept: list[tuple[str, float]] = []
    for cid, score in hits:
        text = texts.get(cid)
        if drop_navigational and text is not None and is_navigational_noise(text):
            continue
        meta = join_map.get(cid) or {}
        adjusted = (
            score
            + navigational_penalty(text)
            + query_overlap_boost(query, text)
        )
        if apply_lex_boost:
            adjusted += lex_specialis_boost(meta)
        kept.append((cid, adjusted))

    # If aggressive filtering emptied the list, fall back without dropping.
    if not kept:
        kept = []
        for cid, score in hits:
            meta = join_map.get(cid) or {}
            text = texts.get(cid)
            adjusted = score + query_overlap_boost(query, text)
            if apply_lex_boost:
                adjusted += lex_specialis_boost(meta)
            kept.append((cid, adjusted))

    kept.sort(key=lambda x: x[1], reverse=True)
    return kept
