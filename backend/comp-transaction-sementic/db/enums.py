"""Enum types specific to the transaction-semantic component."""

import enum

from sqlalchemy.dialects.postgresql import ENUM


class LabelSource(str, enum.Enum):
    SYNTHETIC = "synthetic"
    WEAK = "weak"
    MANUAL = "manual"


class TaxabilityStatus(str, enum.Enum):
    TAXABLE = "taxable"
    EXEMPT = "exempt"
    PARTIALLY_TAXABLE = "partially_taxable"
    UNKNOWN = "unknown"


class ReviewStatus(str, enum.Enum):
    PENDING = "pending"
    IN_REVIEW = "in_review"
    RESOLVED = "resolved"
    DISMISSED = "dismissed"


def _values(obj: type[enum.Enum]) -> list[str]:
    return [e.value for e in obj]


label_source_enum = ENUM(
    LabelSource,
    name="label_source",
    create_type=True,
    values_callable=_values,
)

taxability_status_enum = ENUM(
    TaxabilityStatus,
    name="taxability_status",
    create_type=True,
    values_callable=_values,
)

review_status_enum = ENUM(
    ReviewStatus,
    name="review_status",
    create_type=True,
    values_callable=_values,
)
