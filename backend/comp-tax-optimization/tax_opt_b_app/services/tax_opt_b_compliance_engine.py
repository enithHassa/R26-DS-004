"""Deterministic compliance evaluation (Function 1, no ML).

``evaluate_compliance`` is pure over ``(profile, strategy, pack)``: no disk I/O,
no randomness, no network. Pass a :class:`TaxOptBRulePack` built by the loader
(or :func:`parse_tax_opt_b_rules_dict` in tests).
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from tax_opt_b_app.services.tax_opt_b_rules_loader import TaxOptBRulePack, TaxOptBRuleSpec
from tax_opt_b_app.services.tax_opt_b_rules_scope import rules_pack_for_tax_year
from tax_opt_b_app.tax_opt_b_schemas_compliance_v1 import (
    TaxOptBComplianceResultV1,
    TaxOptBRuleViolationV1,
    TaxOptBViolationSeverityV1,
)
from tax_opt_b_app.tax_opt_b_schemas_profile_v1 import TaxOptBProfileV1
from tax_opt_b_app.tax_opt_b_schemas_strategy_v1 import TaxOptBStrategyProposalV1


def _claim_by_code(strategy: TaxOptBStrategyProposalV1) -> dict[str, Decimal]:
    out: dict[str, Decimal] = {}
    for c in strategy.claims:
        out[c.relief_code] = out.get(c.relief_code, Decimal("0")) + c.claimed_amount_annual
    return out


def _rule_first_of_type(rules: tuple[TaxOptBRuleSpec, ...], rtype: str) -> TaxOptBRuleSpec | None:
    for r in rules:
        if r.rule_type == rtype:
            return r
    return None


def evaluate_compliance(
    profile: TaxOptBProfileV1,
    strategy: TaxOptBStrategyProposalV1,
    pack: TaxOptBRulePack,
    *,
    rules_version_label: str | None = None,
) -> TaxOptBComplianceResultV1:
    # Align rules pack with profile.tax_year (personal relief schedule + assessment_year label).
    # Ensures older API layers that pass only the YAML-default pack still evaluate correctly.
    if profile.tax_year != pack.assessment_year:
        try:
            pack = rules_pack_for_tax_year(pack, profile.tax_year)
        except ValueError:
            pass

    violations: list[TaxOptBRuleViolationV1] = []
    applied: dict[str, Any] = {}

    deductions = pack.thresholds.deductions
    allowed = pack.allowed_relief_codes
    claims_by_code = _claim_by_code(strategy)
    assessment_year = pack.assessment_year
    rules_list = pack.rules

    meta_year = _rule_first_of_type(rules_list, "tax_year_match")
    if profile.tax_year != assessment_year:
        violations.append(
            TaxOptBRuleViolationV1(
                rule_id=meta_year.rule_id if meta_year else "it22064486_optb_year_001",
                severity=TaxOptBViolationSeverityV1.ERROR,
                message=(
                    "The assessment year you selected does not match the rules bundle "
                    f"for this request (profile: {profile.tax_year!r}, rules: {assessment_year!r}). "
                    "Choose an assessment year from the supported list and try again."
                ),
                reference=meta_year.reference if meta_year else "",
            )
        )

    meta_unknown = _rule_first_of_type(rules_list, "unknown_relief_code")
    for code, _total in claims_by_code.items():
        if code not in allowed:
            violations.append(
                TaxOptBRuleViolationV1(
                    rule_id=meta_unknown.rule_id if meta_unknown else "it22064486_optb_unknown_relief_001",
                    severity=TaxOptBViolationSeverityV1.ERROR,
                    message=(
                        f"This relief type is not allowed under the current rules: {code!r}. "
                        "Remove it or pick a relief from the supported list."
                    ),
                    reference=meta_unknown.reference if meta_unknown else "",
                )
            )

    for rule in rules_list:
        rtype = rule.rule_type
        if rtype == "deduction_cap":
            relief_code = rule.relief_code or ""
            if relief_code not in claims_by_code:
                continue
            cap_field = rule.cap_field
            cap_val = deductions.get(cap_field) if cap_field else None
            if cap_val is None:
                continue
            cap = cap_val
            claimed = claims_by_code[relief_code]
            msg = rule.message or "Claim exceeds cap."
            if claimed > cap:
                violations.append(
                    TaxOptBRuleViolationV1(
                        rule_id=rule.rule_id,
                        severity=TaxOptBViolationSeverityV1.ERROR,
                        message=msg,
                        reference=rule.reference,
                    )
                )
            allowed_amt = min(claimed, cap)
            applied[relief_code] = {
                "relief_code": relief_code,
                "claimed": str(claimed),
                "cap": str(cap),
                "allowed": str(allowed_amt),
            }

        elif rtype == "charitable_donation_cap":
            relief_code = rule.relief_code or "charitable_donations"
            if relief_code not in claims_by_code:
                continue
            pct_field = rule.cap_pct_field
            pct = deductions.get(pct_field, Decimal("0")) if pct_field else Decimal("0")
            basis = profile.estimated_annual_taxable_income
            if basis is None:
                basis = profile.annual_gross_income
            cap = (basis * pct).quantize(Decimal("1"))
            claimed = claims_by_code[relief_code]
            msg = rule.message or "Donations exceed cap."
            if claimed > cap:
                violations.append(
                    TaxOptBRuleViolationV1(
                        rule_id=rule.rule_id,
                        severity=TaxOptBViolationSeverityV1.ERROR,
                        message=msg,
                        reference=rule.reference,
                    )
                )
            allowed_amt = min(claimed, cap)
            applied[relief_code] = {
                "relief_code": relief_code,
                "claimed": str(claimed),
                "cap": str(cap),
                "allowed": str(allowed_amt),
                "taxable_basis": str(basis),
                "pct": str(pct),
            }

        elif rtype == "retirement_contribution_cap":
            relief_code = rule.relief_code or "retirement_contribution"
            if relief_code not in claims_by_code:
                continue
            pct_field = rule.cap_pct_field
            ann_field = rule.cap_annual_field
            pct_g = deductions.get(pct_field, Decimal("0")) if pct_field else Decimal("0")
            cap_ann = deductions.get(ann_field, Decimal("0")) if ann_field else Decimal("0")
            cap = min(profile.annual_gross_income * pct_g, cap_ann).quantize(Decimal("1"))
            claimed = claims_by_code[relief_code]
            msg = rule.message or "Retirement contribution exceeds cap."
            if claimed > cap:
                violations.append(
                    TaxOptBRuleViolationV1(
                        rule_id=rule.rule_id,
                        severity=TaxOptBViolationSeverityV1.ERROR,
                        message=msg,
                        reference=rule.reference,
                    )
                )
            allowed_amt = min(claimed, cap)
            applied[relief_code] = {
                "relief_code": relief_code,
                "claimed": str(claimed),
                "cap": str(cap),
                "allowed": str(allowed_amt),
            }

    passed = len(violations) == 0
    return TaxOptBComplianceResultV1(
        passed=passed,
        violations=violations,
        applied_relief=applied if passed else {},
        ruleset_assessment_year=assessment_year or None,
        ruleset_schema_version=pack.schema_version or None,
        rules_version_label=rules_version_label,
    )


__all__ = ["evaluate_compliance"]
