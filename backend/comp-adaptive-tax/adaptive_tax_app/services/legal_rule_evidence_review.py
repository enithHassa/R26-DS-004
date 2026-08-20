"""Phase 11b — Human approval stub for LegalRuleEvidence (future engine path).

Path (aligned with amendment ``rule_source`` approve/reject review UX)::

    RAG finds provision
      → LegalRuleEvidence (structured legal evidence)
      → Human/admin validation
      → RAG-grounded rule candidate approved
      → (future) Incorporated into calculation engine

Dissertation claim
------------------
Current system provides RAG-grounded legal evidence and explanation.
The LLM/RAG does not automatically change the tax calculation.
Future RAG-grounded rule candidates require validation before incorporation
into the calculation engine.

**Wire into live ``POST /calculate`` is out of scope.** Approving a candidate
never mutates param packs, Neo4j executable edges, or the Rule Engine.
``executable`` remains ``False`` even after ``status=approved``.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Literal

from adaptive_tax_app.schemas.legal_rule_evidence import (
    LegalEvidenceStatus,
    LegalRuleEvidence,
)

DISSERTATION_CLAIM = (
    "Current system provides RAG-grounded legal evidence and explanation. "
    "The LLM/RAG does not automatically change the tax calculation. "
    "Future RAG-grounded rule candidates require validation before "
    "incorporation into the calculation engine."
)

APPROVAL_PATH_STEPS: tuple[str, ...] = (
    "rag_finds_provision",
    "legal_rule_evidence_candidate",
    "human_admin_validation",
    "rag_grounded_rule_candidate_approved",
    "future_incorporation_into_calculation_engine",
)

FUTURE_INCORPORATION_NOTE = (
    "Incorporation into the Rule Engine / param packs is FUTURE work. "
    "Approved candidates remain non-executable evidence until a separate, "
    "explicit engine-wiring phase. No silent RAG→calc path."
)


class LegalRuleEvidenceReviewError(RuntimeError):
    """Raised when review state transition is invalid."""


@dataclass
class LegalRuleEvidenceReviewRecord:
    """In-memory review envelope (stub — mirrors amendment job review shape)."""

    review_id: str
    evidence: LegalRuleEvidence
    created_at: str
    updated_at: str
    reviewer_note: str | None = None
    rejection_reason: str | None = None
    # Always false until a future incorporation phase.
    incorporated_into_engine: bool = False


# Process-local stub store (tests / admin dry-run). Not Postgres.
_REVIEW_STORE: dict[str, LegalRuleEvidenceReviewRecord] = {}


def clear_review_store() -> None:
    """Test helper — empty the in-memory stub store."""
    _REVIEW_STORE.clear()


def list_reviews(
    *,
    status: LegalEvidenceStatus | None = None,
) -> list[LegalRuleEvidenceReviewRecord]:
    rows = list(_REVIEW_STORE.values())
    if status is not None:
        rows = [r for r in rows if r.evidence.status == status]
    return rows


def get_review(review_id: str) -> LegalRuleEvidenceReviewRecord | None:
    return _REVIEW_STORE.get(review_id)


def submit_candidate(
    evidence: LegalRuleEvidence,
    *,
    reviewer_note: str | None = None,
) -> LegalRuleEvidenceReviewRecord:
    """Queue structured legal evidence for human review (status → needs_review)."""
    if evidence.executable is not False:
        raise LegalRuleEvidenceReviewError(
            "LegalRuleEvidence must be non-executable (Phase 11)"
        )
    now = datetime.now(timezone.utc).isoformat()
    updated = evidence.model_copy(
        update={"status": "needs_review", "executable": False}
    )
    review_id = str(uuid.uuid4())
    rec = LegalRuleEvidenceReviewRecord(
        review_id=review_id,
        evidence=updated,
        created_at=now,
        updated_at=now,
        reviewer_note=reviewer_note,
        incorporated_into_engine=False,
    )
    _REVIEW_STORE[review_id] = rec
    return rec


def approve_candidate(
    review_id: str,
    *,
    reviewer_note: str | None = None,
) -> LegalRuleEvidenceReviewRecord:
    """Mark candidate approved for *future* engine incorporation — does not calculate.

    Aligns with amendment ``POST .../approve`` terminology, but deliberately does
    **not** call param overrides, Neo4j merge, or ``rule_engine.calculate``.
    """
    rec = _REVIEW_STORE.get(review_id)
    if rec is None:
        raise LegalRuleEvidenceReviewError(f"review not found: {review_id}")
    if rec.evidence.status == "rejected":
        raise LegalRuleEvidenceReviewError("cannot approve a rejected candidate")
    now = datetime.now(timezone.utc).isoformat()
    evidence = rec.evidence.model_copy(
        update={
            "status": "approved",
            "executable": False,
            "applicability_note": (
                (rec.evidence.applicability_note or "")
                + (" " if rec.evidence.applicability_note else "")
                + FUTURE_INCORPORATION_NOTE
            ).strip(),
        }
    )
    updated = LegalRuleEvidenceReviewRecord(
        review_id=rec.review_id,
        evidence=evidence,
        created_at=rec.created_at,
        updated_at=now,
        reviewer_note=reviewer_note or rec.reviewer_note,
        rejection_reason=None,
        incorporated_into_engine=False,
    )
    _REVIEW_STORE[review_id] = updated
    return updated


def reject_candidate(
    review_id: str,
    *,
    reason: str,
) -> LegalRuleEvidenceReviewRecord:
    """Reject a candidate (parallel to amendment reject) — no engine effect."""
    rec = _REVIEW_STORE.get(review_id)
    if rec is None:
        raise LegalRuleEvidenceReviewError(f"review not found: {review_id}")
    reason_clean = (reason or "").strip()
    if not reason_clean:
        raise LegalRuleEvidenceReviewError("rejection reason is required")
    now = datetime.now(timezone.utc).isoformat()
    evidence = rec.evidence.model_copy(
        update={"status": "rejected", "executable": False}
    )
    updated = LegalRuleEvidenceReviewRecord(
        review_id=rec.review_id,
        evidence=evidence,
        created_at=rec.created_at,
        updated_at=now,
        reviewer_note=rec.reviewer_note,
        rejection_reason=reason_clean,
        incorporated_into_engine=False,
    )
    _REVIEW_STORE[review_id] = updated
    return updated


def incorporate_into_engine_stub(
    review_id: str,
) -> Literal["blocked_future_only"]:
    """Explicit no-op: live calculate wiring is out of scope.

    Call sites that attempt incorporation receive a blocked sentinel rather than
    mutating the Rule Engine.
    """
    rec = _REVIEW_STORE.get(review_id)
    if rec is None:
        raise LegalRuleEvidenceReviewError(f"review not found: {review_id}")
    if rec.evidence.status != "approved":
        raise LegalRuleEvidenceReviewError(
            "only approved candidates may be considered for future incorporation"
        )
    # Never set incorporated_into_engine=True in this phase.
    return "blocked_future_only"


def approval_path_documentation() -> dict[str, object]:
    """Machine-readable CURRENT vs FUTURE approval path for docs/coverage."""
    return {
        "dissertation_claim": DISSERTATION_CLAIM,
        "path_steps": list(APPROVAL_PATH_STEPS),
        "aligns_with": [
            "amendment POST /{job_id}/approve",
            "amendment POST /{job_id}/reject",
            "rule_source status approved|rejected review UX",
        ],
        "current": {
            "rag": "legal evidence + explain",
            "rule_engine": "sole tax calculator",
            "legal_rule_evidence": "candidate/needs_review/approved stub; executable=false",
            "calculate_wiring": False,
        },
        "future": {
            "after_human_approval": "validated rule candidate may be incorporated into engine",
            "requires": "explicit separate phase — no silent RAG→calc",
        },
        "future_incorporation_note": FUTURE_INCORPORATION_NOTE,
        "is_rag_calculation": False,
    }
