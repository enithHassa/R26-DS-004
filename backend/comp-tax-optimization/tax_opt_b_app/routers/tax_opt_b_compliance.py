"""Function 1: compliance check API."""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, HTTPException, Request, status

from tax_opt_b_app.config import component_settings
from tax_opt_b_app.services.tax_opt_b_compliance_engine import evaluate_compliance
from tax_opt_b_app.services.tax_opt_b_explanation_builders import (
    build_compare_explanations,
    build_compute_explanations,
    build_search_explanations,
)
from tax_opt_b_app.services.tax_opt_b_income_snapshot_client import (
    IncomeSnapshotClientError,
    fetch_income_snapshot,
)
from tax_opt_b_app.services.tax_opt_b_compare_strategies import compare_strategies
from tax_opt_b_app.services.tax_opt_b_search_strategies import search_strategies_from_financial_inputs
from tax_opt_b_app.services.tax_opt_b_financial_inputs_mapper import (
    map_financial_inputs_to_profile_and_strategy,
    validate_relief_codes_used,
    validate_strategy_relief_codes,
)
from tax_opt_b_app.services.tax_opt_b_financial_strategy_presets import (
    PRESET_LABELS,
    PRESET_SUMMARY_NARRATIVES,
    build_preset_financial_inputs,
)
from tax_opt_b_app.services.tax_opt_b_tax_computation import run_compliance_and_compute_tax
from tax_opt_b_app.tax_opt_b_schemas_compliance_v1 import (
    TaxOptBComplianceCheckRequestV1,
    TaxOptBComplianceFromFinancialInputsRequestV1,
    TaxOptBComplianceFromTransactionsRequestV1,
    TaxOptBComplianceResultV1,
)
from tax_opt_b_app.tax_opt_b_schemas_compare_v1 import (
    MAPPED_INTAKE_VARIANT_ID,
    TaxOptBCompareFromFinancialInputsRequestV1,
    TaxOptBComparePresetsFromFinancialInputsRequestV1,
    TaxOptBCompareStrategiesRequestV1,
    TaxOptBCompareStrategiesResponseV1,
)
from tax_opt_b_app.tax_opt_b_schemas_search_v1 import (
    TaxOptBSearchStrategiesFromFinancialInputsRequestV1,
    TaxOptBSearchStrategiesResponseV1,
)
from tax_opt_b_app.tax_opt_b_schemas_explainability_v1 import (
    TaxOptBExplanationBulletKindV1,
    TaxOptBExplanationBulletV1,
    TaxOptBExplanationBundleV1,
    TaxOptBExplanationSectionV1,
)
from tax_opt_b_app.tax_opt_b_schemas_financial_inputs_v1 import TaxOptBFinancialInputsV1
from tax_opt_b_app.tax_opt_b_schemas_tax_computation_v1 import TaxOptBComputeTaxResponseV1
from tax_opt_b_app.tax_opt_b_schemas_profile_v1 import TaxOptBProfileV1
from tax_opt_b_app.tax_opt_b_schemas_strategy_v1 import TaxOptBStrategyProposalV1

router = APIRouter(tags=["tax-opt-b-compliance"])


def _rules_pack_or_503(request: Request):
    pack = getattr(request.app.state, "tax_opt_b_rules", None)
    if pack is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Rules pack not loaded.",
        )
    return pack


def _maybe_compute_explanations(
    out: TaxOptBComputeTaxResponseV1,
    *,
    include_explanations: bool,
    explanation_detail: Literal["summary", "detailed"],
) -> TaxOptBComputeTaxResponseV1:
    if not include_explanations:
        return out
    return out.model_copy(
        update={"explanations": build_compute_explanations(out, detail=explanation_detail)},
    )


def _maybe_compare_explanations(
    resp: TaxOptBCompareStrategiesResponseV1,
    *,
    include_explanations: bool,
    explanation_detail: Literal["summary", "detailed"],
) -> TaxOptBCompareStrategiesResponseV1:
    if not include_explanations:
        return resp
    return resp.model_copy(
        update={"explanations": build_compare_explanations(resp, detail=explanation_detail)},
    )


def _maybe_search_explanations(
    resp: TaxOptBSearchStrategiesResponseV1,
    *,
    include_explanations: bool,
    explanation_detail: Literal["summary", "detailed"],
) -> TaxOptBSearchStrategiesResponseV1:
    if not include_explanations:
        return resp
    return resp.model_copy(
        update={"explanations": build_search_explanations(resp, detail=explanation_detail)},
    )


def _core_financial_inputs(body: TaxOptBComparePresetsFromFinancialInputsRequestV1) -> TaxOptBFinancialInputsV1:
    keys = set(TaxOptBFinancialInputsV1.model_fields.keys())
    return TaxOptBFinancialInputsV1.model_validate(body.model_dump(include=keys))


def _profile_identity_tuple(p: TaxOptBProfileV1) -> tuple:
    et = p.employment_type.value if hasattr(p.employment_type, "value") else str(p.employment_type)
    return (
        p.tax_year,
        et,
        p.dependents,
        p.annual_gross_income,
        p.estimated_annual_taxable_income,
    )


def _resolved_preset_baseline(presets: list[str], requested: str | None) -> str | None:
    if requested is not None:
        return requested
    if "no_claims" in presets:
        return "no_claims"
    if "user_proposed" in presets:
        return "user_proposed"
    return None


def _merge_preset_explanation_section(
    bundle: TaxOptBExplanationBundleV1 | None,
    preset_ids: list[str],
) -> TaxOptBExplanationBundleV1 | None:
    if bundle is None:
        return None
    bullets = [
        TaxOptBExplanationBulletV1(
            kind=TaxOptBExplanationBulletKindV1.SUMMARY,
            text=f"{pid}: {PRESET_SUMMARY_NARRATIVES[pid]}",
            source_refs=[f"preset:{pid}"],
        )
        for pid in preset_ids
    ]
    extra = TaxOptBExplanationSectionV1(title="Strategy presets (MVP)", bullets=bullets)
    return bundle.model_copy(
        update={"sections": [*bundle.sections, extra]},
    )


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
def compute_tax(
    request: Request,
    body: TaxOptBComplianceCheckRequestV1,
) -> TaxOptBComputeTaxResponseV1:
    pack = _rules_pack_or_503(request)
    out = run_compliance_and_compute_tax(
        body.profile,
        body.strategy,
        pack,
        rules_version_label=component_settings.COMP_OPTIMIZATION_RULES_VERSION,
    )
    return _maybe_compute_explanations(
        out,
        include_explanations=body.include_explanations,
        explanation_detail=body.explanation_detail,
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
    computed = run_compliance_and_compute_tax(
        profile,
        strategy,
        pack,
        rules_version_label=component_settings.COMP_OPTIMIZATION_RULES_VERSION,
    )
    compliance = computed.compliance.model_copy(
        update={
            "mapped_profile": profile,
            "mapped_strategy": strategy,
        },
    )
    response = TaxOptBComputeTaxResponseV1(
        compliance=compliance,
        tax_computation=computed.tax_computation,
        research_disclaimer=computed.research_disclaimer,
    )
    return _maybe_compute_explanations(
        response,
        include_explanations=body.include_explanations,
        explanation_detail=body.explanation_detail,
    )


def _unknown_relief_http_detail(unknown: list[str]) -> str:
    return (
        "Unknown or disallowed relief_code in strategy claims "
        f"(not in active rules pack): {', '.join(repr(c) for c in unknown)}"
    )


@router.post(
    "/compare-strategies",
    response_model=TaxOptBCompareStrategiesResponseV1,
    summary="Compare multiple strategies for one profile; rank by total tax (FR6)",
)
def compare_strategies_route(
    request: Request,
    body: TaxOptBCompareStrategiesRequestV1,
) -> TaxOptBCompareStrategiesResponseV1:
    pack = _rules_pack_or_503(request)
    for v in body.variants:
        unknown = validate_strategy_relief_codes(v.strategy, pack.allowed_relief_codes)
        if unknown:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=_unknown_relief_http_detail(unknown),
            )
    tuples = [(x.variant_id, x.label, x.strategy) for x in body.variants]
    resp = compare_strategies(
        body.profile,
        tuples,
        pack,
        baseline_variant_id=body.baseline_variant_id,
        rules_version_label=component_settings.COMP_OPTIMIZATION_RULES_VERSION,
        include_result_detail=body.include_result_detail,
    )
    return _maybe_compare_explanations(
        resp,
        include_explanations=body.include_explanations,
        explanation_detail=body.explanation_detail,
    )


@router.post(
    "/compare-strategies-from-financial-inputs",
    response_model=TaxOptBCompareStrategiesResponseV1,
    summary="Compare strategies using structured intake profile + explicit variant list (FR6)",
)
def compare_strategies_from_financial_inputs(
    request: Request,
    body: TaxOptBCompareFromFinancialInputsRequestV1,
) -> TaxOptBCompareStrategiesResponseV1:
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
    profile, mapped_strategy = map_financial_inputs_to_profile_and_strategy(body)
    tuples: list[tuple[str, str | None, TaxOptBStrategyProposalV1]] = []
    if body.include_mapped_strategy:
        tuples.append(
            (MAPPED_INTAKE_VARIANT_ID, "From structured intake", mapped_strategy),
        )
    for v in body.strategy_variants:
        unknown_s = validate_strategy_relief_codes(v.strategy, pack.allowed_relief_codes)
        if unknown_s:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=_unknown_relief_http_detail(unknown_s),
            )
        tuples.append((v.variant_id, v.label, v.strategy))
    resp = compare_strategies(
        profile,
        tuples,
        pack,
        baseline_variant_id=body.baseline_variant_id,
        rules_version_label=component_settings.COMP_OPTIMIZATION_RULES_VERSION,
        include_result_detail=body.include_result_detail,
    )
    return _maybe_compare_explanations(
        resp,
        include_explanations=body.include_explanations,
        explanation_detail=body.explanation_detail,
    )


@router.post(
    "/compare-presets-from-financial-inputs",
    response_model=TaxOptBCompareStrategiesResponseV1,
    summary="Compare MVP strategy presets (user form, no claims, max caps) in one call",
)
def compare_presets_from_financial_inputs(
    request: Request,
    body: TaxOptBComparePresetsFromFinancialInputsRequestV1,
) -> TaxOptBCompareStrategiesResponseV1:
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
    base = _core_financial_inputs(body)
    tuples: list[tuple[str, str | None, TaxOptBStrategyProposalV1]] = []
    ref_profile: TaxOptBProfileV1 | None = None

    for preset_id in body.presets:
        fin_inputs = build_preset_financial_inputs(base, preset_id, pack)
        bad_preset = validate_relief_codes_used(fin_inputs, pack.allowed_relief_codes)
        if bad_preset:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=(
                    f"preset {preset_id!r}: unknown or disallowed relief_code "
                    f"(not in active rules pack): {', '.join(repr(c) for c in bad_preset)}"
                ),
            )
        profile, strategy = map_financial_inputs_to_profile_and_strategy(fin_inputs)
        if ref_profile is None:
            ref_profile = profile
        elif _profile_identity_tuple(profile) != _profile_identity_tuple(ref_profile):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=(
                    "Preset mapping produced profiles that differ on "
                    "(tax_year, employment_type, dependents, annual_gross_income, "
                    "estimated_annual_taxable_income). "
                    f"baseline identity={_profile_identity_tuple(ref_profile)!r}, "
                    f"preset={preset_id!r} identity={_profile_identity_tuple(profile)!r}."
                ),
            )
        tuples.append((preset_id, PRESET_LABELS[preset_id], strategy))

    assert ref_profile is not None
    baseline = _resolved_preset_baseline(list(body.presets), body.baseline_variant_id)
    resp = compare_strategies(
        ref_profile,
        tuples,
        pack,
        baseline_variant_id=baseline,
        rules_version_label=component_settings.COMP_OPTIMIZATION_RULES_VERSION,
        include_result_detail=body.include_result_detail,
    )
    resp = _maybe_compare_explanations(
        resp,
        include_explanations=body.include_explanations,
        explanation_detail=body.explanation_detail,
    )
    if body.include_explanations:
        resp = resp.model_copy(
            update={
                "explanations": _merge_preset_explanation_section(
                    resp.explanations,
                    list(body.presets),
                ),
            },
        )
    return resp


@router.post(
    "/search-strategies-from-financial-inputs",
    response_model=TaxOptBSearchStrategiesResponseV1,
    summary="Enumerate MVP max-cap subsets; top_k passing strategies (Function 2)",
)
def search_strategies_from_financial_inputs_route(
    request: Request,
    body: TaxOptBSearchStrategiesFromFinancialInputsRequestV1,
) -> TaxOptBSearchStrategiesResponseV1:
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
    try:
        resp = search_strategies_from_financial_inputs(
            body,
            pack,
            rules_version_label=component_settings.COMP_OPTIMIZATION_RULES_VERSION,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(exc),
        ) from exc
    return _maybe_search_explanations(
        resp,
        include_explanations=body.include_explanations,
        explanation_detail=body.explanation_detail,
    )
