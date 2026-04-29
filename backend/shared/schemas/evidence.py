"""Explainability chain — ordered reasoning trace for auditors (WP7)."""


from pydantic import BaseModel, Field


class EvidenceStep(BaseModel):
    """One hop in the reasoning pipeline."""

    step: str = Field(..., description="Stage key, e.g. normalize, semantic_classifier.")
    detail: str = Field(..., description="Human-readable explanation for this hop.")


class EvidenceChain(BaseModel):
    """Ordered list of evidence steps from raw input to taxability decision."""

    steps: list[EvidenceStep] = Field(default_factory=list)
