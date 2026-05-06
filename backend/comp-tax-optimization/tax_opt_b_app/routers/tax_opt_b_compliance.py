"""Function 1: compliance check API."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, status

from tax_opt_b_app.config import component_settings
from tax_opt_b_app.services.tax_opt_b_compliance_engine import evaluate_compliance
from tax_opt_b_app.services.tax_opt_b_income_snapshot_client import (
    IncomeSnapshotClientError,
    fetch_income_snapshot,
)
from tax_opt_b_app.services.tax_opt_b_financial_inputs_mapper import (
    map_financial_inputs_to_profile_and_strategy,
    validate_relief_codes_used,
)
from tax_opt_b_app.services.tax_opt_b_tax_computation import run_compliance_and_compute_tax
from tax_opt_b_app.tax_opt_b_schemas_compliance_v1 import (
    TaxOptBComplianceCheckRequestV1,
    TaxOptBComplianceFromFinancialInputsRequestV1,
    TaxOptBComplianceFromTransactionsRequestV1,
    TaxOptBComplianceResultV1,
)
from tax_opt_b_app.tax_opt_b_schemas_tax_computation_v1 import TaxOptBComputeTaxResponseV1
from tax_opt_b_app.tax_opt_b_schemas_profile_v1 import TaxOptBProfileV1

router = APIRouter(tags=["tax-opt-b-compliance"])


def _rules_pack_or_503(request: Request):
    pack = getattr(request.app.state, "tax_opt_b_rules", None)
    if pack is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Rules pack not loaded.",
        )
    return pack


@router.post(
    "/check",
    response_model=TaxOptBComplianceResultV1,
    summary="Evaluate profile + strategy against encoded IR MVP rules",
)
def compliance_check(request: Request, body: TaxOptBComplianceCheckRequestV1) -> TaxOptBComplianceResultV1:
    pack = _rules_pack_or_503(request)
    return evaluate_compliance(
        body.profile,
        body.strategy,
        pack=pack,
        rules_version_label=component_settings.COMP_OPTIMIZATION_RULES_VERSION,
    )


@router.post(
    "/check-from-financial-inputs",
    response_model=TaxOptBComplianceResultV1,
    summary="Structured financial questionnaire → profile + strategy → compliance",
)
def compliance_check_from_financial_inputs(
    request: Request,
    body: TaxOptBComplianceFromFinancialInputsRequestV1,
) -> TaxOptBComplianceResultV1:
    pack = _rules_pack_or_503(request)
    unknown = validate_relief_codes_used(body, pack.allowed_relief_codes)
    if unknown:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=(
                "Unknown or disallowed relief_code in deductions or investments "
                f"(not in active rules pack): {', '.join(repr(c) for c in unknown)}"
            ),
        )
    profile, strategy = map_financial_inputs_to_profile_and_strategy(body)
    result = evaluate_compliance(
        profile,
        strategy,
        pack=pack,
        rules_version_label=component_settings.COMP_OPTIMIZATION_RULES_VERSION,
    )
    return result.model_copy(
        update={
            "mapped_profile": profile,
            "mapped_strategy": strategy,
        },
    )


@router.post(
    "/check-from-transactions",
    response_model=TaxOptBComplianceResultV1,
    summary="Fetch Component 1 income snapshot, map to profile, then evaluate compliance",
)
async def compliance_check_from_transactions(
    request: Request,
    body: TaxOptBComplianceFromTransactionsRequestV1,
) -> TaxOptBComplianceResultV1:
    pack = _rules_pack_or_503(request)
    try:
        snap = await fetch_income_snapshot(
            user_id=body.user_id,
            assessment_year=body.tax_year,
        )
    except IncomeSnapshotClientError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc

    if snap.assessment_year != body.tax_year:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=(
                "Income snapshot assessment_year does not match request tax_year: "
                f"{snap.assessment_year!r} != {body.tax_year!r}"
            ),
        )

    profile = TaxOptBProfileV1(
        tax_year=body.tax_year,
        employment_type=body.employment_type,
        dependents=body.dependents,
        annual_gross_income=snap.annual_gross_income,
        estimated_annual_taxable_income=snap.estimated_annual_taxable_income,
    )
    result = evaluate_compliance(
        profile,
        body.strategy,
        pack=pack,
        rules_version_label=component_settings.COMP_OPTIMIZATION_RULES_VERSION,
    )
    return result.model_copy(
        update={"income_snapshot": snap.model_dump(mode="json")},
    )


@router.post(
    "/compute-tax",
    response_model=TaxOptBComputeTaxResponseV1,
    summary="Run compliance then MVP deterministic APIT-style tax when compliant",
)
def compute_tax(request: Request, body: TaxOptBComplianceCheckRequestV1) -> TaxOptBComputeTaxResponseV1:
    pack = _rules_pack_or_503(request)
    return run_compliance_and_compute_tax(
        body.profile,
        body.strategy,
        pack,
        rules_version_label=component_settings.COMP_OPTIMIZATION_RULES_VERSION,
    )


@router.post(
    "/compute-tax-from-financial-inputs",
    response_model=TaxOptBComputeTaxResponseV1,
    summary="Structured financial inputs → compliance + tax (MVP)",
)
def compute_tax_from_financial_inputs(
    request: Request,
    body: TaxOptBComplianceFromFinancialInputsRequestV1,
) -> TaxOptBComputeTaxResponseV1:
    pack = _rules_pack_or_503(request)
    unknown = validate_relief_codes_used(body, pack.allowed_relief_codes)
    if unknown:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=(
                "Unknown or disallowed relief_code in deductions or investments "
                f"(not in active rules pack): {', '.join(repr(c) for c in unknown)}"
            ),
        )
    profile, strategy = map_financial_inputs_to_profile_and_strategy(body)
    out = run_compliance_and_compute_tax(
        profile,
        strategy,
        pack,
        rules_version_label=component_settings.COMP_OPTIMIZATION_RULES_VERSION,
    )
    compliance = out.compliance.model_copy(
        update={
            "mapped_profile": profile,
            "mapped_strategy": strategy,
        },
    )
    return TaxOptBComputeTaxResponseV1(
        compliance=compliance,
        tax_computation=out.tax_computation,
        research_disclaimer=out.research_disclaimer,
    )
