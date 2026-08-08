"""Service layer for the recommendation component.

Routers stay thin — orchestration, transactions, and the rules-engine
hand-off live in this package.
"""

from app.services.profile_service import (
    ProfileNotFoundError,
    compute_derived_features,
    create_profile,
    delete_profile,
    get_profile,
    list_profiles,
    update_profile,
)
from app.services.inference_assets import (
    ArtifactLoadError,
    InferenceArtifacts,
    load_inference_artifacts,
    resolve_artifacts_dir,
)
from app.services.recommendation_service import (
    RecommendationGenerationError,
    generate_recommendations,
)
from app.services.impact_service import (
    ImpactSimulationError,
    StrategyNotFoundError,
    compare_strategies,
    simulate_impact,
)
from app.services.explanation_service import (
    ExplanationError,
    explain_strategy_for_profile,
)
from app.services.feedback_service import (
    RecommendationItemNotFoundError,
    submit_feedback,
)

__all__ = [
    "ProfileNotFoundError",
    "compute_derived_features",
    "create_profile",
    "delete_profile",
    "get_profile",
    "ArtifactLoadError",
    "InferenceArtifacts",
    "RecommendationGenerationError",
    "list_profiles",
    "load_inference_artifacts",
    "generate_recommendations",
    "ImpactSimulationError",
    "StrategyNotFoundError",
    "compare_strategies",
    "simulate_impact",
    "ExplanationError",
    "explain_strategy_for_profile",
    "resolve_artifacts_dir",
    "update_profile",
    "RecommendationItemNotFoundError",
    "submit_feedback",
]
