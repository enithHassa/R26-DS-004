"""Shared Pydantic contracts used across APIs and pipelines.

Includes framework primitives (pagination, errors) and canonical JSON shapes
for cross-component data (e.g. transactions). Component-specific schemas live
under ``backend/<component>/app/schemas/``.
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
from backend.shared.schemas.taxability import TaxabilityOutput
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
    "LabelSource",
    "NormalizedTransaction",
    "ORMBase",
    "PaginatedResponse",
    "RiskTolerance",
    "TaxabilityOutput",
    "TaxabilityStatus",
    "TimestampedSchema",
    "Transaction",
    "TxnDirection",
]
