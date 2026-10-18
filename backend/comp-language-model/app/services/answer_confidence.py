"""Answer-level grounding / confidence score for UI (supervisor demo metric).

Not BLEU (that's an offline eval metric). This is a transparent 0–100 score from:
retrieval strength + citation support + Think Twice validation.
"""

from __future__ import annotations

from app.schemas.query_v1 import Citation


def compute_answer_confidence(
    citations: list[Citation],
    *,
    validation_status: str | None,
    has_plain_answer: bool,
) -> tuple[int, str]:
    """Return (score_0_to_100, label) for the advisory answer."""
    if not citations:
        return 0, "No sources"

    top = max(c.score for c in citations)
    # TF-IDF cosine scores are typically ~0.1–0.6; map into a readable band.
    retrieval_pts = min(55, int(round(top * 100)))
    # Extra support from having several grounded passages.
    support_pts = min(20, len(citations) * 4)

    validation_pts = 0
    status = (validation_status or "").lower()
    if status == "passed":
        validation_pts = 20
    elif status == "corrected":
        validation_pts = 8
    elif status == "skipped":
        validation_pts = 10
    elif status == "not_run":
        validation_pts = 5

    answer_pts = 5 if has_plain_answer else 0
    score = max(0, min(100, retrieval_pts + support_pts + validation_pts + answer_pts))

    if score >= 80:
        label = "High confidence"
    elif score >= 60:
        label = "Medium confidence"
    elif score >= 40:
        label = "Low confidence"
    else:
        label = "Weak grounding"

    return score, label
