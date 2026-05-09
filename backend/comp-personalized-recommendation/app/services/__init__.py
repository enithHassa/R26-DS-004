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

__all__ = [
    "ProfileNotFoundError",
    "compute_derived_features",
    "create_profile",
    "delete_profile",
    "get_profile",
    "list_profiles",
    "update_profile",
]
