"""Pydantic schemas owned by Component 3 (Personalized Recommendation).

These contracts are deliberately local to this component. Only generic
primitives (``RiskTolerance``, ``Currency``, ``PaginatedResponse``,
``ErrorResponse``, ``ORMBase``, ``TimestampedSchema``) live in
``backend.shared.schemas``.
"""

from app.schemas.impact import (
    ImpactSimulationRequest,
    ImpactSimulationResponse,
    ImpactSummary,
    ProjectionBand,
    Scenario,
    StrategyComparisonRequest,
    YearlyProjection,
)
from app.schemas.profile import (
    DerivedFeatures,
    FinancialProfile,
    FinancialProfileBase,
    FinancialProfileCreate,
    FinancialProfileUpdate,
    Gender,
    IncomeSource,
    MaritalStatus,
    Occupation,
)
from app.schemas.recommendation import (
    FeatureAttribution,
    FeedbackCreate,
    RecommendationExplanation,
    RecommendationItem,
    RecommendationRequest,
    RecommendationResponse,
    ScoreBreakdown,
)
from app.schemas.strategy import (
    EligibilityCheck,
    Strategy,
    StrategyBase,
    StrategyCandidate,
    StrategyCategory,
    StrategyCreate,
    StrategyGenerationRequest,
    StrategyGenerationResponse,
)

__all__ = [
    "DerivedFeatures",
    "EligibilityCheck",
    "FeatureAttribution",
    "FeedbackCreate",
    "FinancialProfile",
    "FinancialProfileBase",
    "FinancialProfileCreate",
    "FinancialProfileUpdate",
    "Gender",
    "ImpactSimulationRequest",
    "ImpactSimulationResponse",
    "ImpactSummary",
    "IncomeSource",
    "MaritalStatus",
    "Occupation",
    "ProjectionBand",
    "RecommendationExplanation",
    "RecommendationItem",
    "RecommendationRequest",
    "RecommendationResponse",
    "Scenario",
    "ScoreBreakdown",
    "Strategy",
    "StrategyBase",
    "StrategyCandidate",
    "StrategyCategory",
    "StrategyComparisonRequest",
    "StrategyCreate",
    "StrategyGenerationRequest",
    "StrategyGenerationResponse",
    "YearlyProjection",
]
