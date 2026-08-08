"""Behavioural-question answer service layer.

A small fixed set of question keys map onto existing `FinancialProfile`
fields that the recommendation model already consumes (`risk_tolerance`,
`investment_horizon_years`) — answering those takes effect on the very next
`generate_recommendations` call, since recommendations are always computed
live from the current profile state (no caching to invalidate).

Any other question key is stored here only. It does NOT yet influence
scoring — the training scripts (`scripts/train_phase4_ranking_adoption.py`)
would need a matching feature added before that becomes true. This is
intentional, not an oversight: see the "answers -> retrain" plan.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.behavioural_answer import BehaviouralAnswer as BehaviouralAnswerORM
from app.schemas.behavioural_answer import BehaviouralAnswerCreate
from app.schemas.profile import FinancialProfileUpdate
from app.services.profile_service import ProfileNotFoundError, get_profile, update_profile

# question_key -> FinancialProfile field name this answer's value is written to.
PROFILE_MAPPED_QUESTIONS: dict[str, str] = {
    "risk_comfort": "risk_tolerance",
    "investment_horizon": "investment_horizon_years",
}


def _apply_profile_mapping(db: Session, profile_id: UUID, answer: BehaviouralAnswerCreate) -> None:
    field = PROFILE_MAPPED_QUESTIONS.get(answer.question_key)
    if field is None:
        return
    value: str | int = answer.answer_value
    if field == "investment_horizon_years":
        value = int(answer.answer_value)
    update_profile(db, profile_id, FinancialProfileUpdate(**{field: value}))


def upsert_answers(
    db: Session, profile_id: UUID, answers: list[BehaviouralAnswerCreate]
) -> list[BehaviouralAnswerORM]:
    # Raises ProfileNotFoundError if the profile doesn't exist.
    get_profile(db, profile_id)

    rows: list[BehaviouralAnswerORM] = []
    for answer in answers:
        existing = db.execute(
            select(BehaviouralAnswerORM).where(
                BehaviouralAnswerORM.profile_id == profile_id,
                BehaviouralAnswerORM.question_key == answer.question_key,
            )
        ).scalar_one_or_none()
        if existing is not None:
            existing.answer_value = answer.answer_value
            rows.append(existing)
        else:
            row = BehaviouralAnswerORM(
                profile_id=profile_id,
                question_key=answer.question_key,
                answer_value=answer.answer_value,
            )
            db.add(row)
            rows.append(row)

        _apply_profile_mapping(db, profile_id, answer)

    db.commit()
    for row in rows:
        db.refresh(row)
    return rows


def list_answers(db: Session, profile_id: UUID) -> list[BehaviouralAnswerORM]:
    get_profile(db, profile_id)
    return list(
        db.execute(
            select(BehaviouralAnswerORM)
            .where(BehaviouralAnswerORM.profile_id == profile_id)
            .order_by(BehaviouralAnswerORM.question_key.asc())
        )
        .scalars()
        .all()
    )


__all__ = [
    "PROFILE_MAPPED_QUESTIONS",
    "ProfileNotFoundError",
    "list_answers",
    "upsert_answers",
]
