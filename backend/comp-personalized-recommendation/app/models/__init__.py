"""SQLAlchemy ORM models for Component 3 (Personalized Recommendation).

Importing this package is enough to register all tables on
``backend.shared.config.database.Base.metadata`` — which is what Alembic's
``env.py`` reflects on when running ``autogenerate``.

Populated in Phase 0 with the baseline schema: ``users``, ``financial_profiles``,
``tax_strategies``, ``recommendations``, ``recommendation_items``. Phase 2 adds
``simulation_runs`` and ``feedback``; those get their own Alembic revisions.
"""

from app.models.profile import FinancialProfile
from app.models.recommendation import Recommendation, RecommendationItem
from app.models.strategy import TaxStrategy
from app.models.user import User

__all__ = [
    "FinancialProfile",
    "Recommendation",
    "RecommendationItem",
    "TaxStrategy",
    "User",
]
