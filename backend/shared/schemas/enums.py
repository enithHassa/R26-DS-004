"""String enums for JSON/API contracts.

Member values mirror PostgreSQL ENUM labels from Alembic (``txn_*``, ``label_*``,
``taxability_*``, …). Keep literals aligned whenever you alter a migration — ORM
enums under ``backend/shared/db`` and ``backend/comp-transaction-sementic/db``
embed the same strings.

``TxnDirection`` intentionally parallels ``backend.shared.db.enums.TxnDirection``
so FastAPI/Pydantic layers never depend on SQLAlchemy dialect helpers."""

from enum import StrEnum


class TxnDirection(StrEnum):
    CR = "CR"
    DR = "DR"


class TaxabilityStatus(StrEnum):
    TAXABLE = "taxable"
    EXEMPT = "exempt"
    PARTIALLY_TAXABLE = "partially_taxable"
    UNKNOWN = "unknown"


class LabelSource(StrEnum):
    SYNTHETIC = "synthetic"
    WEAK = "weak"
    MANUAL = "manual"
