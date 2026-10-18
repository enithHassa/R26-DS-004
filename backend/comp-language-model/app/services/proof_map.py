"""Proof Map — auditable reasoning trail for advisory responses (Phase 6 MVP)."""

from __future__ import annotations

from dataclasses import asdict, is_dataclass

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
    """Build structured paper trail from query to final output.

    Evidence steps keep **verbatim** corpus text (not Gemini paraphrase) so the
    map stays auditable. Gemini belongs only in the advisory_output step.
    """
    top_score = citations[0].score if citations else None
    retrieval_detail = (
        f"Searched the IRD law corpus with {retrieval_model}. "
        f"Returned {len(citations)} grounded passage(s)"
        + (f" (best score {top_score:.3f})." if top_score is not None else ".")
    )
    steps: list[ProofMapStep] = [
        ProofMapStep(
            step_id="input",
            kind="user_query",
            label="1. Your question",
            detail=question,
            metadata={"normalized": normalized_question},
        ),
        ProofMapStep(
            step_id="retrieval",
            kind="retrieval",
            label="2. Find matching law passages",
            detail=retrieval_detail,
            metadata={
                "chunk_ids": [c.chunk_id for c in citations],
                "top_score": top_score,
                "retrieval_model": retrieval_model,
            },
        ),
    ]

    if graph_context is not None:
        concept_names = [
            (c.canonical_name or c.concept_id)
            for c in (graph_context.concepts or [])[:5]
            if (c.canonical_name or c.concept_id)
        ]
        relief_names = [
            (r.display_name or r.relief_id)
            for r in (graph_context.reliefs or [])[:5]
            if (r.display_name or r.relief_id)
        ]
        graph_detail_parts: list[str] = []
        if concept_names:
            graph_detail_parts.append("Concepts: " + ", ".join(concept_names))
        elif graph_context.concepts:
            graph_detail_parts.append(f"{len(graph_context.concepts)} concept(s)")
        if relief_names:
            graph_detail_parts.append("Reliefs: " + ", ".join(relief_names))
        elif graph_context.reliefs:
            graph_detail_parts.append(f"{len(graph_context.reliefs)} relief(s)")
        if graph_context.lex_notes:
            graph_detail_parts.append(f"{len(graph_context.lex_notes)} Lex override note(s)")
        if graph_context.superseded_by:
            graph_detail_parts.append(
                "Superseded-by links: " + ", ".join(graph_context.superseded_by[:4])
            )
        steps.append(
            ProofMapStep(
                step_id="graph",
                kind="knowledge_graph",
                label="3. Knowledge graph context",
                detail="; ".join(graph_detail_parts) or "No linked graph entities for these passages.",
                metadata={
                    "superseded_by": graph_context.superseded_by,
                    "lex_notes": [n.model_dump() for n in graph_context.lex_notes],
                    "concept_ids": [c.concept_id for c in (graph_context.concepts or [])],
                    "relief_ids": [r.relief_id for r in (graph_context.reliefs or [])],
                },
            )
        )

    for index, citation in enumerate(citations[:6], start=1):
        source = citation.source_doc_id or "unknown-source"
        section = citation.section_label or citation.section_uid
        score_bit = f" · score {citation.score:.3f}" if citation.score is not None else ""
        tier_bit = f" · tier {citation.tier}" if citation.tier else ""
        label = f"Evidence {index}: {source}"
        if section:
            label = f"Evidence {index}: {source} — {section}"
        excerpt = (citation.text or "").strip()
        if len(excerpt) > 320:
            excerpt = excerpt[:317].rstrip() + "…"
        header = f"Verbatim excerpt from the law corpus{tier_bit}{score_bit}."
        detail = f"{header}\n\n{excerpt}" if excerpt else header
        steps.append(
            ProofMapStep(
                step_id=f"evidence_{index}",
                kind="evidence",
                label=label,
                detail=detail,
                metadata={
                    "chunk_id": citation.chunk_id,
                    "source_doc_id": citation.source_doc_id,
                    "section_uid": citation.section_uid,
                    "section_label": citation.section_label,
                    "tier": citation.tier,
                    "score": citation.score,
                    "evidence_index": index,
                },
            )
        )

    if validation is not None:
        issue_rows = [
            i.model_dump()
            if hasattr(i, "model_dump")
            else (asdict(i) if is_dataclass(i) else dict(i))
            for i in validation.issues
        ]
        errors = [i for i in issue_rows if i.get("severity") == "error"]
        warnings = [i for i in issue_rows if i.get("severity") != "error"]
        if validation.passed and not errors:
            detail = (
                "Think Twice passed. The draft answer is consistent with the symbolic "
                "tax rule schedule."
            )
            if warnings:
                detail += " Notes: " + "; ".join(
                    str(w.get("message") or w.get("code")) for w in warnings[:3]
                )
        else:
            detail = (
                f"Think Twice status: {validation_status}. "
                + (
                    "; ".join(str(e.get("message") or e.get("code")) for e in errors[:3])
                    or "Symbolic checks did not pass."
                )
            )
        steps.append(
            ProofMapStep(
                step_id="symbolic_validation",
                kind="symbolic_validation",
                label="4. Think Twice rule check",
                detail=detail,
                metadata={
                    "rule_engine_version": validation.rule_engine_version,
                    "issues": issue_rows,
                    "passed": validation.passed,
                },
            )
        )

    if plain_answer:
        steps.append(
            ProofMapStep(
                step_id="advisory_output",
                kind="advisory_output",
                label="5. Plain-language answer (Gemini + validation)",
                detail=plain_answer[:500] + ("..." if len(plain_answer) > 500 else ""),
                metadata={"generated_by": "gemini", "validated": validation_status},
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
