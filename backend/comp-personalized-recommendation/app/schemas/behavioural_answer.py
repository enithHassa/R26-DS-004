"""Behavioural-question answer contracts (taxpayer click-through questions)."""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, Field

from backend.shared.schemas.common import TimestampedSchema


class BehaviouralAnswerCreate(BaseModel):
    question_key: str = Field(min_length=1, max_length=80)
    answer_value: str = Field(min_length=1, max_length=80)


class BehaviouralAnswerBatchCreate(BaseModel):
    answers: list[BehaviouralAnswerCreate] = Field(min_length=1)


class BehaviouralAnswer(TimestampedSchema):
    profile_id: UUID
    question_key: str
    answer_value: str


__all__ = [
    "BehaviouralAnswer",
    "BehaviouralAnswerBatchCreate",
    "BehaviouralAnswerCreate",
]
