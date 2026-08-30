"""SQLAlchemy ORM models for Component 3 (Personalized Recommendation).

Importing this package is enough to register all tables on
``backend.shared.config.database.Base.metadata`` — which is what Alembic's
``env.py`` reflects on when running ``autogenerate``.

Populated in Phase 0 with the baseline schema: ``users``, ``financial_profiles``,
``tax_strategies``, ``recommendations``, ``recommendation_items``. Phase 2 adds
``simulation_runs`` and ``feedback``; those get their own Alembic revisions.
"""

from app.models.behavioural_answer import BehaviouralAnswer
from app.models.profile import FinancialProfile
from app.models.profile_history import ProfileHistorySnapshot
from app.models.recommendation import Recommendation, RecommendationItem
from app.models.recommendation_feedback import RecommendationFeedback
from app.models.strategy import TaxStrategy
from app.models.tax_computation_snapshot import TaxComputationSnapshot
from app.models.user import User
from app.models.user_transaction_flag import UserTransactionFlag

__all__ = [
    "BehaviouralAnswer",
    "FinancialProfile",
    "ProfileHistorySnapshot",
    "Recommendation",
    "RecommendationFeedback",
    "RecommendationItem",
    "TaxComputationSnapshot",
    "TaxStrategy",
    "User",
    "UserTransactionFlag",
]
