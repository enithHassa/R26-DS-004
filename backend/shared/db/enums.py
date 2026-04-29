"""Enum types shared across all components."""

import enum

from sqlalchemy.dialects.postgresql import ENUM


class TxnDirection(str, enum.Enum):
    """Direction of fund flow on a bank transaction."""

    CR = "CR"
    DR = "DR"


txn_direction_enum = ENUM(
    TxnDirection,
    name="txn_direction",
    create_type=True,
    values_callable=lambda obj: [e.value for e in obj],
)
