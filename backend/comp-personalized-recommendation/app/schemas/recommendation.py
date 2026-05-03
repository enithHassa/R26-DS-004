"""Ranked recommendation + explanation contracts (FR5, FR6, FR9, FR10 — Component 3)."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field

from app.schemas.strategy import Strategy
from backend.shared.schemas.common import ORMBase


class ScoreBreakdown(BaseModel):
    """Per-component score pieces fed to the multi-objective fusion."""

    tax_savings_norm: float = Field(ge=0, le=1)
    adoption_prob: float = Field(ge=0, le=1)
    feasibility: float = Field(ge=0, le=1)
    risk_penalty: float = Field(ge=0, le=1)
    final_score: float


class FeatureAttribution(BaseModel):
    feature: str
    shap_value: float
    direction: str = Field(description="positive|negative")


class RecommendationExplanation(BaseModel):
    top_reasons: list[FeatureAttribution]
    bottom_reasons: list[FeatureAttribution]
    narrative: str | None = None


class RecommendationItem(ORMBase):
    id: UUID
    rank: int = Field(ge=1)
    strategy: Strategy
    estimated_annual_savings: Decimal
    adoption_probability: float = Field(ge=0, le=1)
    risk_score: float = Field(ge=0, le=1)
    confidence: float = Field(ge=0, le=1)
    scores: ScoreBreakdown
    explanation: RecommendationExplanation | None = None


class RecommendationRequest(BaseModel):
    profile_id: UUID
    top_k: int = Field(ge=1, le=25, default=5)
    regenerate_candidates: bool = False


class RecommendationResponse(BaseModel):
    id: UUID
    profile_id: UUID
    generated_at: datetime
    model_version: str
    items: list[RecommendationItem]


class FeedbackCreate(BaseModel):
    recommendation_item_id: UUID
    accepted: bool
    dismissed_reason: str | None = None
    user_rating: int | None = Field(default=None, ge=1, le=5)


__all__ = [
    "FeatureAttribution",
    "FeedbackCreate",
    "RecommendationExplanation",
    "RecommendationItem",
    "RecommendationRequest",
    "RecommendationResponse",
    "ScoreBreakdown",
]
