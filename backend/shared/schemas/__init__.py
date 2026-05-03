"""Generic, framework-wide schema primitives shared across all 4 research components.

IMPORTANT: Do NOT add component-specific contracts (profile, strategy,
recommendation, impact, transaction, etc.) here. Each component owns its
Pydantic schemas under ``backend/<comp-folder>/app/schemas/``.
"""

from backend.shared.schemas.common import (
    Currency,
    ErrorDetail,
    ErrorResponse,
    ORMBase,
    PaginatedResponse,
    RiskTolerance,
    TimestampedSchema,
)

__all__ = [
    "Currency",
    "ErrorDetail",
    "ErrorResponse",
    "ORMBase",
    "PaginatedResponse",
    "RiskTolerance",
    "TimestampedSchema",
]
