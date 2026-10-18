from __future__ import annotations

from app.schemas.graph_v1 import ConceptNode, GraphContext, LexNote, RateBandNode, ReliefNode
from app.schemas.query_v1 import Citation
from app.services.answer_synthesis import build_synthesis_prompt


def test_build_synthesis_prompt_includes_question_citations_and_graph() -> None:
    prompt = build_synthesis_prompt(
        "What is personal relief?",
        [
            Citation(
                chunk_id="t::1",
                score=0.9,
                text="Personal relief reduces tax for residents.",
                section_label="Relief section",
            )
        ],
        GraphContext(
            concepts=[ConceptNode(concept_id="tax_resident", canonical_name="Tax Resident")],
            reliefs=[
                ReliefNode(
                    relief_id="relief_personal",
                    display_name="Personal Relief",
                    description="LKR 1,800,000 for 2025/26",
                )
            ],
            rate_bands=[
                RateBandNode(
                    rate_band_id="band1",
                    band_label="First band",
                    lower_bound=0,
                    upper_bound=500000,
                    rate_percent=6.0,
                    currency="LKR",
                )
            ],
            lex_notes=[
                LexNote(
                    winner_section_uid="amend::sec::10",
                    overridden_section_uid="act::sec::10",
                )
            ],
        ),
        max_citations=4,
        max_chars_per_citation=500,
    )
    assert "What is personal relief?" in prompt
    assert "[Match 1] Relief section" in prompt
    assert "Tax Resident" in prompt
    assert "MUST-USE FACTS" in prompt
    assert "OVERRIDE: prefer amend::sec::10 over act::sec::10" in prompt
    assert "RATE BAND: First band" in prompt
    assert "RELIEF: Personal Relief" in prompt
