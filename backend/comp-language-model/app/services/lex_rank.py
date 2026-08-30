"""Lex Specialis-inspired reranking for retrieved chunk hits."""

from __future__ import annotations

# Higher authority tiers and instrument types score better during reranking.
_TIER_BOOST: dict[str, float] = {
    "A": 0.12,
    "B": 0.06,
    "C": 0.0,
}

_INSTRUMENT_BOOST: dict[str, float] = {
    "act": 0.08,
    "amendment": 0.10,
    "circular": 0.07,
    "regulation": 0.05,
    "guide": 0.02,
    "hub_summary": 0.0,
}


def lex_specialis_boost(meta: dict[str, str | None]) -> float:
    """Return a small score boost from corpus / KG metadata."""
    boost = 0.0
    tier = (meta.get("tier") or "").strip().upper()
    if tier in _TIER_BOOST:
        boost += _TIER_BOOST[tier]
    instrument = (meta.get("instrument_type") or "").strip().lower()
    if instrument in _INSTRUMENT_BOOST:
        boost += _INSTRUMENT_BOOST[instrument]
    return boost


def rerank_hits(
    hits: list[tuple[str, float]],
    join_map: dict[str, dict[str, str | None]],
) -> list[tuple[str, float]]:
    """Rerank (chunk_id, score) pairs using Lex Specialis metadata boosts."""
    if not hits:
        return hits

    def adjusted(item: tuple[str, float]) -> tuple[str, float]:
        cid, score = item
        meta = join_map.get(cid) or {}
        return cid, score + lex_specialis_boost(meta)

    adjusted_hits = [adjusted(h) for h in hits]
    adjusted_hits.sort(key=lambda x: x[1], reverse=True)
    return adjusted_hits
