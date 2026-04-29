"""Confidence and uncertainty diagnostics (WP7 — softmax, calibration, OOD)."""

from pydantic import BaseModel, Field


class ConfidenceReport(BaseModel):
    """Structured confidence bundle accompanying a classification / taxability decision."""

    top_label: str | None = Field(None, description="Winning semantic or rule label.")
    top_probability: float | None = Field(None, ge=0.0, le=1.0)
    calibrated_probability: float | None = Field(
        None,
        ge=0.0,
        le=1.0,
        description="Temperature-scaled or Platt-scaled probability when fitted.",
    )
    entropy: float | None = Field(None, ge=0.0, description="Predictive entropy (optional).")
    mc_dropout_variance: float | None = Field(
        None,
        ge=0.0,
        description="Variance across MC-dropout forward passes when enabled.",
    )
    is_ood: bool | None = Field(
        None,
        description="True if flagged out-of-distribution / novelty routing to review.",
    )
