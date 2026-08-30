"""Pydantic schemas owned by Component 3 (Personalized Recommendation).

These contracts are deliberately local to this component. Only generic
primitives (``RiskTolerance``, ``Currency``, ``PaginatedResponse``,
``ErrorResponse``, ``ORMBase``, ``TimestampedSchema``) live in
``backend.shared.schemas``.
"""

from app.schemas.auth import LoginRequest, LoginResponse, SignupRequest, SignupResponse
from app.schemas.behavioural_answer import (
    BehaviouralAnswer,
    BehaviouralAnswerBatchCreate,
    BehaviouralAnswerCreate,
)
from app.schemas.history import ProfileHistorySnapshot
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
    EligibilityOverrideUpdate,
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
    ExplainRequest,
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
    "BehaviouralAnswer",
    "BehaviouralAnswerBatchCreate",
    "BehaviouralAnswerCreate",
    "DerivedFeatures",
    "EligibilityCheck",
    "EligibilityOverrideUpdate",
    "ExplainRequest",
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
    "LoginRequest",
    "LoginResponse",
    "MaritalStatus",
    "Occupation",
    "ProfileHistorySnapshot",
    "ProjectionBand",
    "RecommendationExplanation",
    "RecommendationItem",
    "RecommendationRequest",
    "RecommendationResponse",
    "Scenario",
    "ScoreBreakdown",
    "SignupRequest",
    "SignupResponse",
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
