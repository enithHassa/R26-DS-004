"""Calculate-tax request/response DTOs (Phase 3 rule engine — no GPT).

Money on the JSON wire is **string** LKR amounts (Comp 2 / frontend pattern).
Python-side fields remain ``Decimal`` for exact arithmetic.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Annotated, Any, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    PlainSerializer,
    WithJsonSchema,
    field_validator,
)

AssessmentYear = Literal["2024_25"]
ResidentStatus = Literal["resident", "non_resident"]
ParamSet = Literal["current", "pre_amend_2025"]


def _as_nonneg_decimal(value: Any) -> Decimal:
    """Coerce JSON string/number/null → non-negative Decimal."""
    if value is None or value == "":
        return Decimal("0")
    if isinstance(value, Decimal):
        d = value
    elif isinstance(value, bool):
        raise ValueError("boolean is not a valid money amount")
    else:
        text = str(value).strip()
        if text == "":
            return Decimal("0")
        try:
            d = Decimal(text)
        except (InvalidOperation, ValueError) as exc:
            raise ValueError(f"invalid money amount: {value!r}") from exc
    if d < 0:
        raise ValueError("must be >= 0")
    return d


def _decimal_to_wire(value: Decimal) -> str:
    """Serialize Decimal without scientific notation (stable JSON strings)."""
    return format(value, "f")


# Internal Decimal; JSON schema + dump use strings.
MoneyLkr = Annotated[
    Decimal,
    PlainSerializer(_decimal_to_wire, return_type=str, when_used="json"),
    WithJsonSchema({"type": "string", "examples": ["1800000"]}, mode="serialization"),
    WithJsonSchema(
        {
            "anyOf": [
                {"type": "string", "examples": ["1800000"]},
                {"type": "number", "minimum": 0},
            ]
        },
        mode="validation",
    ),
]


class CalculateTaxRequestV1(BaseModel):
    """Inputs for ``POST /api/v1/calculate``."""

    model_config = ConfigDict(str_strip_whitespace=True)

    assessment_year: AssessmentYear = Field(
        default="2024_25",
        description="Assessment year label (underscore form). Extend later for 2025_26+.",
    )
    resident_status: ResidentStatus = Field(
        default="resident",
        description="Taxpayer residency; personal relief applies to residents only.",
    )
    employment_income: MoneyLkr = Field(
        default=Decimal("0"),
        description="Annual employment income (LKR string on the wire).",
    )
    business_income: MoneyLkr = Field(
        default=Decimal("0"),
        description="Annual business / profession income (LKR string on the wire).",
    )
    investment_income: MoneyLkr = Field(
        default=Decimal("0"),
        description="Annual investment income (LKR string on the wire).",
    )
    qualifying_payments: MoneyLkr = Field(
        default=Decimal("0"),
        description="Claimed Section 52 qualifying payments (LKR string on the wire).",
    )
    donations: MoneyLkr = Field(
        default=Decimal("0"),
        description="Claimed charitable donations (LKR string on the wire).",
    )
    other_reliefs: dict[str, MoneyLkr] = Field(
        default_factory=dict,
        description="Optional extra relief concept_id → claimed amount (string LKR).",
    )
    param_set: ParamSet = Field(
        default="current",
        description=(
            "Relief/param snapshot: ``current`` (post Act 02/2025 Sec 52 cap) "
            "or ``pre_amend_2025`` (ex08 A/B compare)."
        ),
    )

    @field_validator(
        "employment_income",
        "business_income",
        "investment_income",
        "qualifying_payments",
        "donations",
        mode="before",
    )
    @classmethod
    def _money_fields(cls, v: Any) -> Decimal:
        return _as_nonneg_decimal(v)

    @field_validator("other_reliefs", mode="before")
    @classmethod
    def _other_reliefs(cls, v: Any) -> dict[str, Decimal]:
        if v is None:
            return {}
        if not isinstance(v, dict):
            raise TypeError("other_reliefs must be an object")
        return {str(k): _as_nonneg_decimal(val) for k, val in v.items()}


class CalculationTraceStep(BaseModel):
    """One ordered explainability step from the rule engine."""

    model_config = ConfigDict(str_strip_whitespace=True)

    step_id: str = Field(description="Stable step id, e.g. sum_assessable, slab_band_1.")
    description: str
    formula: str
    inputs: dict[str, str] = Field(
        default_factory=dict,
        description="Named inputs with Decimal amounts already stringified.",
    )
    output: str = Field(description="Step output as a string (usually LKR).")
    concept_ids: list[str] = Field(default_factory=list)
    section_uids: list[str] = Field(default_factory=list)
    rule_source_ids: list[str] = Field(
        default_factory=list,
        description="Stable ontology ids (source_doc_id / relief_id / rate_band_id).",
    )


class RuleSourceRef(BaseModel):
    """Deduped rule/source reference surfaced alongside the trace."""

    model_config = ConfigDict(str_strip_whitespace=True)

    id: str
    kind: str = Field(description="e.g. source_doc, relief, rate_band")
    section_uid: str | None = None
    concept_id: str | None = None


class CalculateTaxResponseV1(BaseModel):
    """Result of ``POST /api/v1/calculate``."""

    model_config = ConfigDict(str_strip_whitespace=True)

    final_tax_lkr: str = Field(description="Total tax liability in whole LKR (string).")
    calculation_trace: list[CalculationTraceStep]
    rules_applied: list[str] = Field(
        description=(
            "Ordered rule ids, e.g. sum_assessable, cap_qualifying_payment_cap, "
            "slab_band_1, final_tax."
        ),
    )
    rule_source_refs: list[RuleSourceRef]
    calc_id: str = Field(
        default="",
        description=(
            "UUID of the persisted calculation (filled by the calculate API / calc store). "
            "Empty when returned directly from the rule engine without persistence."
        ),
    )


class StoredCalculationV1(BaseModel):
    """On-disk record under ``COMP_ADAPTIVE_TAX_CALC_STORE_DIR/{calc_id}.json``."""

    model_config = ConfigDict(str_strip_whitespace=True)

    calc_id: str
    created_at: datetime
    request: CalculateTaxRequestV1
    response: CalculateTaxResponseV1
    param_set_effective: ParamSet
    amendment_context: dict[str, Any] | None = Field(
        default=None,
        description="Optional Sec 52 / approve metadata (filled in Phase 4 Step 2+).",
    )
