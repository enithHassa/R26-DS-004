from __future__ import annotations

from app.schemas.graph_v1 import LexNote
from app.schemas.query_v1 import Citation
from app.services.lex_citation_order import soft_prefer_override_winners


def test_soft_prefer_puts_winner_before_overridden() -> None:
    citations = [
        Citation(
            chunk_id="old",
            score=0.95,
            text="old base act text",
            section_uid="act::sec::10",
        ),
        Citation(
            chunk_id="new",
            score=0.70,
            text="amendment text",
            section_uid="amend::sec::10",
        ),
        Citation(
            chunk_id="other",
            score=0.80,
            text="unrelated",
            section_uid="act::sec::99",
        ),
    ]
    notes = [
        LexNote(
            winner_section_uid="amend::sec::10",
            overridden_section_uid="act::sec::10",
        )
    ]
    ordered = soft_prefer_override_winners(citations, notes)
    assert [c.chunk_id for c in ordered] == ["new", "other", "old"]


def test_soft_prefer_noop_without_notes() -> None:
    citations = [
        Citation(chunk_id="a", score=0.9, text="a", section_uid="x"),
        Citation(chunk_id="b", score=0.8, text="b", section_uid="y"),
    ]
    assert soft_prefer_override_winners(citations, None) is citations
    assert soft_prefer_override_winners(citations, []) is citations
