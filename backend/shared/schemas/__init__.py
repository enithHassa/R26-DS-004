"""Shared Pydantic contracts — canonical JSON shapes across APIs and pipelines."""

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
