"""Shared Pydantic contracts — canonical JSON shapes between pipeline stages and APIs."""

from backend.shared.schemas.analyze import AnalyzeTransactionRequest, AnalyzeTransactionResponse
from backend.shared.schemas.confidence import ConfidenceReport
from backend.shared.schemas.enums import LabelSource, TaxabilityStatus, TxnDirection
from backend.shared.schemas.evidence import EvidenceChain, EvidenceStep
from backend.shared.schemas.taxability import TaxabilityOutput
from backend.shared.schemas.transaction import NormalizedTransaction, Transaction

__all__ = [
    "AnalyzeTransactionRequest",
    "AnalyzeTransactionResponse",
    "ConfidenceReport",
    "EvidenceChain",
    "EvidenceStep",
    "LabelSource",
    "NormalizedTransaction",
    "TaxabilityOutput",
    "TaxabilityStatus",
    "Transaction",
    "TxnDirection",
]
