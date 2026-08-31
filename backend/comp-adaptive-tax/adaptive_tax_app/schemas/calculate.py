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

AssessmentYear = Literal["2024_25", "2025_26"]
ResidentStatus = Literal["resident", "non_resident"]
ParamSet = Literal["current", "pre_amend_2025"]
FilingTreatment = Literal["include", "exempt", "final_withholding"]
UnresolvedClaimReason = Literal["concept_missing_in_kg", "no_deducted_from_edge"]


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


class FilingLineV1(BaseModel):
    """Catalog-keyed filing line (Phase 6). Prefer over hardcoded field names."""

    model_config = ConfigDict(str_strip_whitespace=True)

    component_id: str = Field(
        ...,
        min_length=1,
        max_length=128,
        description="Stable catalog id, e.g. emp_salary, emp_housing_allowance.",
    )
    amount: MoneyLkr = Field(
        default=Decimal("0"),
        description="Line amount (LKR string on the wire).",
    )
    treatment: FilingTreatment | None = Field(
        default=None,
        description="Override catalog default_treatment when user_overridable.",
    )
    label_override: str | None = Field(
        default=None,
        max_length=256,
        description="Optional display label (custom other-income sources in later phases).",
    )

    @field_validator("amount", mode="before")
    @classmethod
    def _line_amount(cls, v: Any) -> Decimal:
        return _as_nonneg_decimal(v)

    @field_validator("component_id", mode="before")
    @classmethod
    def _component_id(cls, v: Any) -> str:
        text = str(v or "").strip()
        if not text:
            raise ValueError("component_id is required")
        return text


class KnowledgeVersionsV1(BaseModel):
    """Provenance stamps for dissertation 'Calculated Using' strip (Phase 6.0)."""

    model_config = ConfigDict(str_strip_whitespace=True)

    act_version: str = ""
    act_version_label: str = ""
    catalog_version: str = ""
    rule_pack_version: str = ""
    knowledge_graph_version: str = ""
    extraction_version: str = ""


class ComponentTraceItemV1(BaseModel):
    """Per-line aggregation audit (Phase 6.0 skeleton; filled when filing_lines used)."""

    model_config = ConfigDict(str_strip_whitespace=True)

    component_id: str
    display_name: str
    amount: str
    treatment_applied: str
    section: str | None = None
    paragraph: str | None = None
    reason_short: str | None = None
    rule_source_ids: list[str] = Field(default_factory=list)
    included_in_assessable: bool = False
    legal_confidence: str | None = None
    card_id: str | None = None


class QualifyingPaymentCategoryResultV1(BaseModel):
    """Per Fifth Schedule category claimed vs allowable + Sec 52 allocation (Phase 6.3)."""

    model_config = ConfigDict(str_strip_whitespace=True)

    component_id: str
    display_name: str
    claimed: str
    allowable: str
    disallowed: str
    status: str
    legal_reference: str
    section: str | None = None
    paragraph: str | None = None
    reason: str | None = None
    formula: str | None = None
    legal_confidence: str | None = None
    rule_source_ids: list[str] = Field(default_factory=list)
    # Allocation / Sec 52(4) proof fields
    claimed_amount: str | None = None
    allowable_amount: str | None = None
    deducted_this_year: str = "0"
    undeducted_amount: str = "0"
    sec52_4_eligible: bool = False
    carry_forward_amount: str = "0"
    carry_forward_basis: str | None = None  # sec52_4 | fifth_sch_1f | none


class QualifyingPaymentSummaryV1(BaseModel):
    """Roll-up after category rules and Sec 52 aggregate limitation."""

    model_config = ConfigDict(str_strip_whitespace=True)

    total_claimed: str = "0"
    total_allowable_before_sec52: str = "0"
    section_52_cap: str | None = None
    final_allowable_deduction: str = "0"
    unused_after_sec52: str | None = None
    carry_forward_out: str | None = None
    carry_forward_not_eligible: str | None = None
    sec52_4_applicable: bool = False
    total_needs_review: str = "0"


class CalculateTaxRequestV1(BaseModel):
    """Inputs for ``POST /api/v1/calculate``."""

    model_config = ConfigDict(str_strip_whitespace=True)

    assessment_year: AssessmentYear = Field(
        default="2024_25",
        description=(
            "Assessment year label (underscore form). "
            "YA 2024/25 uses Sec 52 cap 1.2M by default; YA 2025/26 uses 1.8M (Act 02/2025)."
        ),
    )
    resident_status: ResidentStatus = Field(
        default="resident",
        description="Taxpayer residency; personal relief applies to residents only.",
    )
    employment_income: MoneyLkr = Field(
        default=Decimal("0"),
        description="Annual employment income (LKR string on the wire).",
    )
    employment_final_withholding: MoneyLkr = Field(
        default=Decimal("0"),
        description=(
            "Employment amounts excluded under Sec 5(3)(a) as exempt amounts / "
            "final withholding payments (Phase 5.1). Applied only when Act-backed "
            "exclude_if_final_wht provenance resolves."
        ),
    )
    business_income: MoneyLkr = Field(
        default=Decimal("0"),
        description=(
            "Net assessable business profits for the year (LKR string on the wire). "
            "Phase 5.6a simplified input: supply profits after allowable expenses "
            "as a single amount. When business_gross is supplied with Act-backed "
            "provenance, this field is ignored in favour of the gross-minus-deductions path."
        ),
    )
    business_gross: MoneyLkr = Field(
        default=Decimal("0"),
        description=(
            "Optional gross business receipts for Phase 5.6b. Applied only when "
            "compute_business_net provenance resolves; net = gross minus approved "
            "deductions and capital allowances."
        ),
    )
    business_deductions: MoneyLkr = Field(
        default=Decimal("0"),
        description=(
            "Allowable business expenses (Sec 11 main deduction). Subtracted from "
            "business_gross only when deduct_business_expenses provenance resolves."
        ),
    )
    capital_allowances: MoneyLkr = Field(
        default=Decimal("0"),
        description=(
            "Capital allowances claimed (Sec 16). Subtracted from remaining gross "
            "only when deduct_capital_allowances provenance resolves."
        ),
    )
    investment_income: MoneyLkr = Field(
        default=Decimal("0"),
        description=(
            "Annual investment income (LKR string on the wire). Phase 5.7: "
            "contributes to assessable under Sec 7; final-WHT / exempt amounts "
            "use investment_final_withholding when Act-backed provenance resolves."
        ),
    )
    investment_final_withholding: MoneyLkr = Field(
        default=Decimal("0"),
        description=(
            "Investment amounts excluded under Sec 7(3)(a) as exempt amounts / "
            "final withholding payments (e.g. final-WHT interest). Applied only "
            "when Act-backed exclude_investment_final_wht provenance resolves; "
            "otherwise investment is summed as entered."
        ),
    )
    other_income: MoneyLkr = Field(
        default=Decimal("0"),
        description=(
            "Annual other-source income under Sec 8 (LKR string on the wire). "
            "Phase 6.5: residual gains/profits not included under employment, "
            "business, or investment; casual and non-recurring profits are out "
            "of scope for this head."
        ),
    )
    other_final_withholding: MoneyLkr = Field(
        default=Decimal("0"),
        description=(
            "Other-source amounts excluded under Sec 8(2)(a) as exempt amounts / "
            "final withholding payments. Applied only when Act-backed "
            "exclude_other_final_wht provenance resolves; otherwise other_income "
            "is summed as entered."
        ),
    )
    qualifying_payments: MoneyLkr = Field(
        default=Decimal("0"),
        description="Claimed Section 52 qualifying payments (LKR string on the wire).",
    )
    qualifying_payment_brought_forward: MoneyLkr = Field(
        default=Decimal("0"),
        description=(
            "Qualifying payments brought forward under Sec 52(4) from a prior YA "
            "(Phase 5.4b). Applied only when carry_forward_qp provenance resolves."
        ),
    )
    donations: MoneyLkr = Field(
        default=Decimal("0"),
        description=(
            "Legacy scalar charitable donations. Normalized into Fifth Sch 1(a) "
            "qp_approved_charitable (min(claimed, 75000, floor(assessable/3))); "
            "never a second 33% deduct."
        ),
    )
    apit_already_paid: MoneyLkr = Field(
        default=Decimal("0"),
        description=(
            "APIT / non-final withholding tax already paid for the year "
            "(Phase 5.8). Credited against gross liability only when Act-backed "
            "tax_credit provenance resolves; final_tax_lkr stays the gross liability."
        ),
    )
    other_reliefs: dict[str, MoneyLkr] = Field(
        default_factory=dict,
        description=(
            "Optional extra relief concept_id → claimed amount (string LKR). "
            "Unknown concept ids are not deducted; they appear on unresolved_claims."
        ),
    )
    solar_panel_relief: MoneyLkr = Field(
        default=Decimal("0"),
        description=(
            "Fifth Schedule 2(g) solar panel relief claimed (LKR). "
            "Resident only; capped at Rs 600,000. Also accepted via filing_lines "
            "component_id relief_solar_panel."
        ),
    )
    rent_relief: MoneyLkr = Field(
        default=Decimal("0"),
        description=(
            "Fifth Schedule 2(c) rent relief claimed (LKR). Capped at "
            "min(claimed, floor(0.25 × included inv_rents)); the 25% base is "
            "the rent include line, not post-Sec 7(3)(a) net investment. "
            "Also accepted via filing_lines component_id relief_rent."
        ),
    )
    senior_citizen_interest_relief: MoneyLkr = Field(
        default=Decimal("0"),
        description=(
            "Fifth Schedule 2(d) senior citizen interest relief claimed (LKR). "
            "Resident only; capped at min(claimed, 1_500_000, included "
            "inv_interest). Also accepted via filing_lines component_id "
            "relief_senior_citizen_interest."
        ),
    )
    param_set: ParamSet = Field(
        default="current",
        description=(
            "Relief/param snapshot: ``current`` (post Act 02/2025 Sec 52 cap) "
            "or ``pre_amend_2025`` (ex08 A/B compare)."
        ),
    )
    filing_lines: list[FilingLineV1] = Field(
        default_factory=list,
        description=(
            "Phase 6 catalog-keyed lines (component_id + amount). When employment "
            "lines are present they take precedence over scalar employment_income / "
            "employment_final_withholding. Other heads land in later Phase 6.x steps."
        ),
    )

    @field_validator(
        "employment_income",
        "employment_final_withholding",
        "business_income",
        "business_gross",
        "business_deductions",
        "capital_allowances",
        "investment_income",
        "investment_final_withholding",
        "other_income",
        "other_final_withholding",
        "qualifying_payments",
        "qualifying_payment_brought_forward",
        "donations",
        "apit_already_paid",
        "solar_panel_relief",
        "rent_relief",
        "senior_citizen_interest_relief",
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

    @field_validator("filing_lines", mode="before")
    @classmethod
    def _filing_lines(cls, v: Any) -> list[Any]:
        if v is None:
            return []
        if not isinstance(v, list):
            raise TypeError("filing_lines must be an array")
        return v


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
        description=(
            "Provenance ids (bootstrap / relief_id / rate_band_id / source_doc_id). "
            "Each id should resolve to an approved Act quote in strict mode."
        ),
    )
    provenance: str | None = Field(
        default=None,
        description="approved | legacy_seed | missing (Phase 5.0b provenance gate).",
    )


class RuleSourceRef(BaseModel):
    """Deduped rule/source reference surfaced alongside the trace."""

    model_config = ConfigDict(str_strip_whitespace=True)

    id: str
    kind: str = Field(description="e.g. source_doc, relief, rate_band")
    section_uid: str | None = None
    concept_id: str | None = None
    section: str | None = Field(
        default=None,
        description="Statutory section label, e.g. '52' or 'First Schedule'.",
    )
    source_quote: str | None = Field(
        default=None,
        description="Verbatim official Act quote backing this ref (when resolved).",
    )
    source_doc_id: str | None = Field(
        default=None,
        description="Official IRD source_doc_id (Act / amendment), never Master PDF.",
    )
    status: str | None = Field(
        default=None,
        description="approved when Act-backed provenance resolved.",
    )


class UnresolvedClaimV1(BaseModel):
    """A claimed deduction the knowledge graph could not apply."""

    model_config = ConfigDict(str_strip_whitespace=True)

    concept_id: str
    component_id: str | None = None
    claimed_lkr: str
    reason: UnresolvedClaimReason


class CalculateTaxResponseV1(BaseModel):
    """Result of ``POST /api/v1/calculate``."""

    model_config = ConfigDict(str_strip_whitespace=True)

    final_tax_lkr: str = Field(
        description=(
            "Gross income tax liability in whole LKR (string) — sum of First Schedule "
            "slab tax before credits (Phase 5.8)."
        ),
    )
    tax_payable_lkr: str = Field(
        default="",
        description=(
            "Net tax payable after approved credits: max(0, final_tax_lkr − credits). "
            "Equals final_tax_lkr when no Act-backed credit is applied."
        ),
    )
    tax_credits_applied_lkr: str = Field(
        default="0",
        description=(
            "Credits actually applied against gross liability (whole LKR string). "
            "Zero when no Act-backed credit step runs."
        ),
    )
    calculation_trace: list[CalculationTraceStep]
    rules_applied: list[str] = Field(
        description=(
            "Ordered rule ids, e.g. sum_assessable, cap_qualifying_payment_cap, "
            "slab_band_1, final_tax, apply_tax_credit."
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
    provenance_complete: bool = Field(
        default=False,
        description=(
            "True when every tax-affecting trace step has non-empty Act-backed "
            "rule_source_ids (Phase 5.0b)."
        ),
    )
    qualifying_payment_carry_forward_out: str | None = Field(
        default=None,
        description=(
            "Unused Sec 52 aggregate cap remaining after current-year qualifying "
            "payments and deductions (Phase 5.4b). Omitted when carry-forward "
            "handler is not enabled or provenance does not resolve."
        ),
    )
    knowledge_versions: KnowledgeVersionsV1 | None = Field(
        default=None,
        description=(
            "Phase 6 Act/catalog/rule-pack/KG/extraction stamps for the "
            "'Calculated Using' provenance strip."
        ),
    )
    head_subtotals: dict[str, str] = Field(
        default_factory=dict,
        description="Optional head-level subtotals (string LKR) from filing_lines normalize.",
    )
    component_trace: list[ComponentTraceItemV1] = Field(
        default_factory=list,
        description="Per filing-line include/exclude audit when filing_lines were used.",
    )
    qualifying_payment_categories: list[QualifyingPaymentCategoryResultV1] = Field(
        default_factory=list,
        description=(
            "Phase 6.3 per-category claimed/allowable results for Fifth Schedule QP lines."
        ),
    )
    qualifying_payment_summary: QualifyingPaymentSummaryV1 | None = Field(
        default=None,
        description="Phase 6.3 roll-up of claimed, category-allowable, Sec 52 final deduction.",
    )
    normalize_warnings: list[str] = Field(
        default_factory=list,
        description="Non-fatal normalize notes (unknown ids, precedence, deferred heads).",
    )
    unresolved_claims: list[UnresolvedClaimV1] = Field(
        default_factory=list,
        description=(
            "Claimed deductions that the KG did not resolve. Amounts are not deducted. "
            "reason is concept_missing_in_kg or no_deducted_from_edge."
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
