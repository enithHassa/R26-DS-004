"""ML-based strategy ranking schemas."""

from pydantic import BaseModel, Field
from typing import List, Dict, Any


class MLRankRequestV1(BaseModel):
    """Request for ML-based strategy ranking."""

    tax_year: str = Field(..., description="Tax year (e.g., '2024_25', '2025_26')")

    # Income
    salary: float = Field(..., ge=0, description="Annual salary in LKR")
    rental_income: float = Field(default=0, ge=0, description="Rental income in LKR")
    interest_income: float = Field(default=0, ge=0, description="Interest income in LKR")
    business_income: float = Field(default=0, ge=0, description="Business income in LKR")

    # Relief claims (amounts)
    life_insurance_premium: float = Field(default=0, ge=0, description="Life insurance amount claimed")
    health_insurance_premium: float = Field(default=0, ge=0, description="Health insurance amount claimed")
    home_loan_interest: float = Field(default=0, ge=0, description="Home loan interest amount claimed")
    rent_relief: float = Field(default=0, ge=0, description="Rent relief amount claimed")
    charitable_donations: float = Field(default=0, ge=0, description="Charitable donations amount claimed")
    retirement_contribution: float = Field(default=0, ge=0, description="Retirement contribution amount claimed")

    # User preferences
    complexity_tolerance: int = Field(default=3, ge=1, le=5, description="1=prefer simple, 5=comfortable with complex")
    audit_risk_tolerance: int = Field(default=3, ge=1, le=5, description="1=risk-averse, 5=aggressive")
    time_available: int = Field(default=2, ge=1, le=3, description="1=minimal, 3=plenty of time")


class RankedStrategyV1(BaseModel):
    """A ranked strategy with ML utility score."""

    strategy_id: int = Field(..., description="Strategy identifier")
    strategy_name: str = Field(..., description="Human-readable strategy name")

    # Reliefs in this strategy
    reliefs_claimed: List[str] = Field(default_factory=list, description="Relief codes claimed")
    num_reliefs: int = Field(..., description="Number of reliefs in strategy")

    # ML Ranking
    utility_score: float = Field(..., ge=0, le=1, description="ML utility score (0-1)")
    rank: int = Field(..., ge=1, description="Rank among all strategies (1=best)")

    # Tax Impact
    estimated_tax_liability: float = Field(..., ge=0, description="Estimated tax liability in LKR")
    estimated_tax_savings: float = Field(default=0, description="Estimated tax savings vs baseline")

    # Compliance & Risk
    compliance_status: str = Field(..., description="'COMPLIANT' or 'VIOLATION'")
    audit_risk_level: str = Field(..., description="'LOW', 'MEDIUM', or 'HIGH'")

    # Legal Explanation
    legal_summary: str = Field(..., description="Brief legal explanation of reliefs claimed")


class MLRankResponseV1(BaseModel):
    """Response with ML-ranked strategies and legal explanations."""

    tax_year: str = Field(..., description="Tax year requested")

    # User profile confirmation
    gross_income: float = Field(..., description="Total gross income calculated")
    taxable_basis: float = Field(..., description="Taxable income basis")

    # Baseline (no reliefs)
    baseline_tax_liability: float = Field(..., description="Tax without any reliefs")

    # Ranked strategies (top 10)
    ranked_strategies: List[RankedStrategyV1] = Field(..., description="Top 10 ranked strategies")

    # Best strategy recommendation
    best_strategy_index: int = Field(..., ge=0, description="Index in ranked_strategies list of best strategy")

    # Additional info
    personalization_note: str = Field(default="", description="Note about personalization to user preferences")
    timestamp: str = Field(..., description="ISO timestamp of ranking")


class MLHealthCheckResponseV1(BaseModel):
    """Health check for ML service."""

    status: str = Field(..., description="'ready' or 'not_ready'")
    model_version: str = Field(default="", description="Model version/date")
    num_features: int = Field(default=0, description="Number of input features")
    model_size_mb: float = Field(default=0, description="Model size in MB")
