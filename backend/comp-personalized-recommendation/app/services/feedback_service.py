"""Recommendation adoption feedback service layer.

Persists whether a user actually acted on a recommended strategy, against a
`recommendation_items` row created by `recommendation_service.generate_recommendations`.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from app.models.recommendation import RecommendationItem as RecommendationItemORM
from app.models.recommendation_feedback import RecommendationFeedback as RecommendationFeedbackORM
from app.schemas.recommendation import FeedbackCreate


class RecommendationItemNotFoundError(LookupError):
    """Raised when feedback references a recommendation item that doesn't exist."""


def submit_feedback(db: Session, payload: FeedbackCreate) -> RecommendationFeedbackORM:
    item = (
        db.query(RecommendationItemORM)
        .filter(RecommendationItemORM.id == payload.recommendation_item_id)
        .one_or_none()
    )
    if item is None:
        raise RecommendationItemNotFoundError(
            f"Recommendation item {payload.recommendation_item_id} not found"
        )

    row = RecommendationFeedbackORM(
        recommendation_item_id=payload.recommendation_item_id,
        accepted=payload.accepted,
        dismissed_reason=payload.dismissed_reason,
        user_rating=payload.user_rating,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row
