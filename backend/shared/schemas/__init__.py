"""Shared Pydantic contracts across components.

Includes framework primitives (pagination, errors, currency, risk profile) and
canonical JSON shapes for cross-component data exchange. Component-specific
request/response models should stay under ``backend/<component>/app/schemas/``.
"""

from backend.shared.schemas.analyze import AnalyzeTransactionRequest, AnalyzeTransactionResponse
from backend.shared.schemas.common import (
    Currency,
    ErrorDetail,
    ErrorResponse,
    ORMBase,
    PaginatedResponse,
    RiskTolerance,
    TimestampedSchema,
)
from backend.shared.schemas.confidence import ConfidenceReport
from backend.shared.schemas.enums import LabelSource, TaxabilityStatus, TxnDirection
from backend.shared.schemas.evidence import EvidenceChain, EvidenceStep
from backend.shared.schemas.income_snapshot import IncomeSnapshotV1
from backend.shared.schemas.taxability import TaxabilityOutput
from backend.shared.schemas.traceability import (
    EvidenceBackedAnswer,
    EvidenceReference,
    TraceabilityMetadata,
)
from backend.shared.schemas.transaction import NormalizedTransaction, Transaction

__all__ = [
    "AnalyzeTransactionRequest",
    "AnalyzeTransactionResponse",
    "ConfidenceReport",
    "Currency",
    "ErrorDetail",
    "ErrorResponse",
    "EvidenceChain",
    "EvidenceStep",
    "IncomeSnapshotV1",
    "LabelSource",
    "NormalizedTransaction",
    "ORMBase",
    "PaginatedResponse",
    "RiskTolerance",
    "TaxabilityOutput",
    "TaxabilityStatus",
    "TraceabilityMetadata",
    "TimestampedSchema",
    "Transaction",
    "TxnDirection",
    "EvidenceReference",
    "EvidenceBackedAnswer",
]
