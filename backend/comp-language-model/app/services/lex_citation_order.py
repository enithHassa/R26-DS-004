"""Soft Lex Specialis citation reordering (safe — never drops hits)."""

from __future__ import annotations

from app.schemas.graph_v1 import LexNote
from app.schemas.query_v1 import Citation


def soft_prefer_override_winners(
    citations: list[Citation],
    lex_notes: list[LexNote] | None,
) -> list[Citation]:
    """Reorder citations so OVERRIDES winners rank above overridden sections.

    Does not remove any citation. Ties keep original relative order by score.
    """
    if not citations or not lex_notes:
        return citations

    winners = {n.winner_section_uid for n in lex_notes if n.winner_section_uid}
    overridden = {n.overridden_section_uid for n in lex_notes if n.overridden_section_uid}
    if not winners and not overridden:
        return citations

    def _rank(citation: Citation) -> tuple[int, float, str]:
        uid = citation.section_uid or ""
        if uid in winners:
            bucket = 0
        elif uid in overridden:
            bucket = 2
        else:
            bucket = 1
        # Higher score first within a bucket.
        return (bucket, -float(citation.score), citation.chunk_id)

    return sorted(citations, key=_rank)
