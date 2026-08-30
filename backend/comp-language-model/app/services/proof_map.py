"""Proof Map — auditable reasoning trail for advisory responses (Phase 6 MVP)."""

from __future__ import annotations

from app.schemas.graph_v1 import GraphContext
from app.schemas.proof_map_v1 import ProofMap, ProofMapStep
from app.schemas.query_v1 import Citation
from app.services.symbolic_engine import SymbolicValidationResult


def build_proof_map(
    *,
    question: str,
    normalized_question: str,
    retrieval_model: str,
    citations: list[Citation],
    graph_context: GraphContext | None,
    validation: SymbolicValidationResult | None,
    validation_status: str,
    plain_answer: str | None,
) -> ProofMap:
    """Build structured paper trail from query to final output."""
    steps: list[ProofMapStep] = [
        ProofMapStep(
            step_id="input",
            kind="user_query",
            label="User question",
            detail=question,
            metadata={"normalized": normalized_question},
        ),
        ProofMapStep(
            step_id="retrieval",
            kind="retrieval",
            label="Law corpus retrieval",
            detail=f"Model: {retrieval_model}; {len(citations)} citation(s).",
            metadata={
                "chunk_ids": [c.chunk_id for c in citations],
                "top_score": citations[0].score if citations else None,
            },
        ),
    ]

    if graph_context is not None:
        graph_detail_parts: list[str] = []
        if graph_context.concepts:
            graph_detail_parts.append(f"{len(graph_context.concepts)} concept(s)")
        if graph_context.reliefs:
            graph_detail_parts.append(f"{len(graph_context.reliefs)} relief(s)")
        if graph_context.lex_notes:
            graph_detail_parts.append(f"{len(graph_context.lex_notes)} override note(s)")
        steps.append(
            ProofMapStep(
                step_id="graph",
                kind="knowledge_graph",
                label="Knowledge graph enrichment",
                detail=", ".join(graph_detail_parts) or "No linked graph entities.",
                metadata={
                    "superseded_by": graph_context.superseded_by,
                    "lex_notes": [n.model_dump() for n in graph_context.lex_notes],
                },
            )
        )

    for index, citation in enumerate(citations[:6], start=1):
        steps.append(
            ProofMapStep(
                step_id=f"evidence_{index}",
                kind="evidence",
                label=citation.section_label or citation.source_doc_id or citation.chunk_id,
                detail=(citation.text[:240] + "...") if len(citation.text) > 240 else citation.text,
                metadata={
                    "chunk_id": citation.chunk_id,
                    "source_doc_id": citation.source_doc_id,
                    "section_uid": citation.section_uid,
                    "tier": citation.tier,
                    "score": citation.score,
                },
            )
        )

    if validation is not None:
        steps.append(
            ProofMapStep(
                step_id="symbolic_validation",
                kind="symbolic_validation",
                label="Think Twice symbolic check",
                detail=f"Status: {validation_status}; passed={validation.passed}.",
                metadata={
                    "rule_engine_version": validation.rule_engine_version,
                    "issues": [i.model_dump() for i in validation.issues],
                },
            )
        )

    if plain_answer:
        steps.append(
            ProofMapStep(
                step_id="advisory_output",
                kind="advisory_output",
                label="Verified advisory output",
                detail=plain_answer[:500] + ("..." if len(plain_answer) > 500 else ""),
            )
        )

    evidence_refs = [
        {
            "chunk_id": c.chunk_id,
            "source_doc_id": c.source_doc_id,
            "section_uid": c.section_uid,
        }
        for c in citations
        if c.source_doc_id or c.section_uid
    ]

    return ProofMap(
        steps=steps,
        evidence_refs=evidence_refs,
        validation_status=validation_status,
        rule_engine_version=validation.rule_engine_version if validation else None,
    )
