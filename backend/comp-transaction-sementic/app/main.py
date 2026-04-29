"""Transaction Semantic component — FastAPI entry point.

Phase 0 stub: `/health` and `/v1/transactions/analyze` return mocked structured
output until WP9 wires in the real pipeline.
"""

from decimal import Decimal
from uuid import uuid4

from fastapi import FastAPI
from loguru import logger

from backend.shared.config.settings import settings
from backend.shared.logging import configure_logging
from backend.shared.middleware.request_id import RequestIDMiddleware
from backend.shared.schemas import (
    AnalyzeTransactionRequest,
    AnalyzeTransactionResponse,
    ConfidenceReport,
    EvidenceChain,
    EvidenceStep,
    TaxabilityOutput,
    TaxabilityStatus,
)

configure_logging(settings)

app = FastAPI(
    title="Transaction Semantic Reasoning API",
    description="Explainable taxable-income inference from bank transactions (Component 1).",
    version="0.1.0",
)
app.add_middleware(RequestIDMiddleware)


@app.get("/health")
def health() -> dict[str, str]:
    logger.debug("health_check_ok")
    return {"status": "ok"}


@app.post("/v1/transactions/analyze", response_model=AnalyzeTransactionResponse)
def analyze_transaction(payload: AnalyzeTransactionRequest) -> AnalyzeTransactionResponse:
    """Stub analysis — replace with preprocessor + classifier + rule map (WP4–WP7)."""
    _ = payload  # unused until pipeline exists
    tid = uuid4()
    logger.bind(transaction_id=str(tid)).info(
        "analyze_transaction_stub_completed semantic_category=salary",
    )
    return AnalyzeTransactionResponse(
        transaction_id=tid,
        semantic_category="salary",
        economic_event="recurring_income",
        tax_rule_code="IRD_SEC_123_STUB",
        taxability=TaxabilityOutput(
            tx_id=tid,
            taxability_status=TaxabilityStatus.TAXABLE,
            taxable_amount=Decimal("45000.00"),
            confidence=0.87,
            evidence=EvidenceChain(
                steps=[
                    EvidenceStep(
                        step="normalize",
                        detail="Whitespace stripped; bank ref masked (stub).",
                    ),
                    EvidenceStep(
                        step="semantic_classifier",
                        detail="Predicted category=salary with softmax prob 0.87 (stub).",
                    ),
                    EvidenceStep(
                        step="tax_rule_mapping",
                        detail="Mapped to stub IRD clause placeholder (stub).",
                    ),
                ],
            ),
            model_version="stub-0.1.0",
            model_run_id=None,
        ),
        confidence_report=ConfidenceReport(
            top_label="salary",
            top_probability=0.87,
            calibrated_probability=0.87,
            entropy=None,
            mc_dropout_variance=None,
            is_ood=False,
        ),
    )
