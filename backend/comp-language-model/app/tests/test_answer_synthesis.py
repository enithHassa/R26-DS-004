from __future__ import annotations

from app.schemas.graph_v1 import ConceptNode, GraphContext
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
        GraphContext(concepts=[ConceptNode(concept_id="tax_resident", canonical_name="Tax Resident")]),
        max_citations=4,
        max_chars_per_citation=500,
    )
    assert "What is personal relief?" in prompt
    assert "[Match 1] Relief section" in prompt
    assert "Tax Resident" in prompt
