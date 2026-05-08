"""Template-based FR5 explanations (deterministic; academically defensible MVP)."""

from __future__ import annotations

from decimal import Decimal
from typing import Any, Literal

from tax_opt_b_app.services.tax_opt_b_explanation_copy import (
    narrative_tier_blurb_compare,
    narrative_tier_blurb_compute,
    relief_display_name,
)
from tax_opt_b_app.tax_opt_b_schemas_compare_v1 import TaxOptBCompareStrategiesResponseV1
from tax_opt_b_app.tax_opt_b_schemas_compliance_v1 import TaxOptBRuleViolationV1
from tax_opt_b_app.tax_opt_b_schemas_explainability_v1 import (
    TaxOptBExplanationBulletKindV1,
    TaxOptBExplanationBulletV1,
    TaxOptBExplanationBundleV1,
    TaxOptBExplanationDetailLevelV1,
    TaxOptBExplanationSectionV1,
)
from tax_opt_b_app.tax_opt_b_schemas_tax_computation_v1 import (
    TaxOptBComputeTaxResponseV1,
    TaxOptBTaxComputationV1,
)

ExplanationDetail = Literal["summary", "detailed"]


class TemplateExplanationProviderV1:
    """Fills ``TaxOptBExplanationBundleV1`` from compliance + tax + compare structures."""

    @property
    def engine_id(self) -> str:
        return "template_v1"

    def explain_compute_response(
        self,
        resp: TaxOptBComputeTaxResponseV1,
        *,
        detail: ExplanationDetail = "summary",
    ) -> TaxOptBExplanationBundleV1:
        c = resp.compliance
        sections: list[TaxOptBExplanationSectionV1] = []
        summary_parts: list[str] = []

        if not c.passed:
            summary_parts.append(
                f"Compliance did not pass: {len(c.violations)} rule violation(s). "
                "MVP tax is not computed until all encoded checks pass.",
            )
            viol_bullets = self._violation_bullets(c.violations, detail)
            sections.append(
                TaxOptBExplanationSectionV1(title="Compliance outcome", bullets=viol_bullets),
            )
        else:
            summary_parts.append("Compliance passed for the proposed strategy under the active rules pack.")
            if c.applied_relief:
                relief_bullets = self._relief_bullets(c.applied_relief, detail)
                sections.append(
                    TaxOptBExplanationSectionV1(title="Applied reliefs (after caps)", bullets=relief_bullets),
                )
                if detail == "summary":
                    summary_parts.append(
                        f"{len(c.applied_relief)} relief code(s) were applied with capped allowable amounts.",
                    )
            else:
                summary_parts.append("No statutory relief claims were applied.")

        if resp.tax_computation is not None:
            tax = resp.tax_computation
            summary_parts.append(
                f"Estimated total tax (MVP progressive slabs): LKR {tax.total_tax}.",
            )
            sections.append(
                TaxOptBExplanationSectionV1(
                    title="Tax computation walk",
                    bullets=self._tax_bullets(tax, detail),
                ),
            )
        elif c.passed:
            summary_parts.append("Tax computation block was not returned.")

        sections.append(
            TaxOptBExplanationSectionV1(
                title="Research disclaimer",
                bullets=[
                    TaxOptBExplanationBulletV1(
                        kind=TaxOptBExplanationBulletKindV1.DISCLAIMER,
                        text=resp.research_disclaimer,
                        source_refs=["disclaimer:research_mvp"],
                    ),
                ],
            ),
        )

        return TaxOptBExplanationBundleV1(
            summary=" ".join([narrative_tier_blurb_compute(detail), *summary_parts]),
            sections=sections,
            detail_level=TaxOptBExplanationDetailLevelV1(detail),
            provenance={"engine": self.engine_id, "deterministic": True},
            rules_version_label=c.rules_version_label,
            ruleset_assessment_year=c.ruleset_assessment_year,
        )

    def explain_compare_response(
        self,
        resp: TaxOptBCompareStrategiesResponseV1,
        *,
        detail: ExplanationDetail = "summary",
    ) -> TaxOptBExplanationBundleV1:
        passing = [r for r in resp.rows if r.passed]
        failing = [r for r in resp.rows if not r.passed]
        summary_parts: list[str] = []

        if passing:
            best = min(passing, key=lambda r: Decimal(r.total_tax or "0"))
            summary_parts.append(
                f"Takeaway: among passing scenarios, {best.variant_id} has the lowest MVP tax "
                f"(LKR {best.total_tax}).",
            )
            summary_parts.append(
                f"Among passing strategies, lowest MVP tax is variant {best.variant_id!r} "
                f"(LKR {best.total_tax}).",
            )
        else:
            summary_parts.append("No strategy passed compliance; ranks reflect ordering after failures.")

        if resp.baseline_variant_id:
            summary_parts.append(
                f"Tax deltas are reported versus baseline variant {resp.baseline_variant_id!r} when available.",
            )

        comp_bullets: list[TaxOptBExplanationBulletV1] = []
        for row in resp.rows:
            if row.passed and row.total_tax is not None:
                delta_note = (
                    f" Δ vs baseline: LKR {row.delta_total_tax_vs_baseline}."
                    if row.delta_total_tax_vs_baseline is not None
                    else ""
                )
                text = (
                    f"Rank {row.rank}: {row.variant_id} — total tax LKR {row.total_tax}.{delta_note}"
                )
                refs = [f"compare:{row.variant_id}"]
                detail_txt: str | None = None
                if detail == "detailed" and row.result and row.result.tax_computation:
                    tc = row.result.tax_computation
                    detail_txt = (
                        f"Basis before personal relief LKR {tc.income_basis_before_personal_relief}; "
                        f"taxable after deductions LKR {tc.taxable_after_deductions}."
                    )
                comp_bullets.append(
                    TaxOptBExplanationBulletV1(
                        kind=TaxOptBExplanationBulletKindV1.COMPARISON,
                        text=text.strip(),
                        source_refs=refs,
                        detail_text=detail_txt,
                    ),
                )
            else:
                vids = ", ".join(row.violation_rule_ids) if row.violation_rule_ids else "n/a"
                comp_bullets.append(
                    TaxOptBExplanationBulletV1(
                        kind=TaxOptBExplanationBulletKindV1.COMPARISON,
                        text=f"{row.variant_id}: failed compliance (violations: {vids}).",
                        source_refs=[f"compare:{row.variant_id}"],
                    ),
                )

        sections = [
            TaxOptBExplanationSectionV1(title="Scenario comparison", bullets=comp_bullets),
        ]
        if detail == "detailed" and failing:
            sections.append(
                TaxOptBExplanationSectionV1(
                    title="Failed variants",
                    bullets=[
                        TaxOptBExplanationBulletV1(
                            kind=TaxOptBExplanationBulletKindV1.COMPLIANCE,
                            text=f"{r.variant_id}: {', '.join(r.violation_rule_ids)}",
                            source_refs=[f"compare:{r.variant_id}"],
                        )
                        for r in failing
                    ],
                ),
            )

        sections.append(
            TaxOptBExplanationSectionV1(
                title="Research disclaimer",
                bullets=[
                    TaxOptBExplanationBulletV1(
                        kind=TaxOptBExplanationBulletKindV1.DISCLAIMER,
                        text=resp.research_disclaimer,
                        source_refs=["disclaimer:research_mvp"],
                    ),
                ],
            ),
        )

        summary_parts.append(f"{len(passing)} passed, {len(failing)} failed out of {len(resp.rows)} scenarios.")

        return TaxOptBExplanationBundleV1(
            summary=" ".join([narrative_tier_blurb_compare(detail), *summary_parts]),
            sections=sections,
            detail_level=TaxOptBExplanationDetailLevelV1(detail),
            provenance={"engine": self.engine_id, "deterministic": True},
            rules_version_label=resp.rules_version_label,
            ruleset_assessment_year=resp.profile.tax_year,
        )

    def _violation_bullets(
        self,
        violations: list[TaxOptBRuleViolationV1],
        detail: ExplanationDetail,
    ) -> list[TaxOptBExplanationBulletV1]:
        out: list[TaxOptBExplanationBulletV1] = []
        for v in violations:
            text = v.message
            refs = [v.rule_id]
            if detail == "detailed":
                text = f"[{v.rule_id}] {v.message}"
                detail_txt = f"Reference: {v.reference}" if v.reference else None
            else:
                detail_txt = (
                    "Plain language: revise the highlighted claims (or income basis) so they fit "
                    "the encoded MVP caps for this assessment year."
                )
            out.append(
                TaxOptBExplanationBulletV1(
                    kind=TaxOptBExplanationBulletKindV1.COMPLIANCE,
                    text=text,
                    source_refs=refs,
                    detail_text=detail_txt,
                ),
            )
        return out

    def _relief_bullets(self, applied_relief: dict[str, Any], detail: ExplanationDetail) -> list[TaxOptBExplanationBulletV1]:
        out: list[TaxOptBExplanationBulletV1] = []
        for code in sorted(applied_relief.keys()):
            payload = applied_relief[code]
            ref = f"relief:{code}"
            if isinstance(payload, dict):
                allowed = payload.get("allowed", "")
                claimed = payload.get("claimed", "")
                cap = payload.get("cap", "")
                label = relief_display_name(code)
                if detail == "detailed":
                    text = (
                        f"{label} (relief code {code}): claimed LKR {claimed}, statutory cap LKR {cap}, "
                        f"allowed for tax LKR {allowed}."
                    )
                else:
                    text = (
                        f"{label}: LKR {allowed} is allowed against your taxable income after applying "
                        f"the statutory cap (you claimed LKR {claimed})."
                    )
                out.append(
                    TaxOptBExplanationBulletV1(
                        kind=TaxOptBExplanationBulletKindV1.RELIEF,
                        text=text,
                        source_refs=[ref],
                    ),
                )
            else:
                lbl = relief_display_name(code)
                out.append(
                    TaxOptBExplanationBulletV1(
                        kind=TaxOptBExplanationBulletKindV1.RELIEF,
                        text=f"{lbl}: applied per rules pack (see raw applied_relief).",
                        source_refs=[ref],
                    ),
                )
        return out

    def _tax_bullets(self, tax: TaxOptBTaxComputationV1, detail: ExplanationDetail) -> list[TaxOptBExplanationBulletV1]:
        # Defensive cap: YAML pack defines a small slab table; bound narrative size regardless.
        max_slab_lines = 40

        bullets: list[TaxOptBExplanationBulletV1] = [
            TaxOptBExplanationBulletV1(
                kind=TaxOptBExplanationBulletKindV1.SUMMARY,
                text=(
                    f"How the calculator got here: income before personal relief is LKR {tax.income_basis_before_personal_relief}. "
                    f"After personal relief (LKR {tax.personal_relief_annual}) that leaves LKR {tax.taxable_after_personal_relief} "
                    f"taxable; allowed reliefs total LKR {tax.total_allowed_deductions}, so the slab base is "
                    f"LKR {tax.taxable_after_deductions}."
                ),
                source_refs=["tax:basis_walk"],
            ),
        ]
        if detail == "detailed":
            slices = tax.slab_slices[:max_slab_lines]
            for sl in slices:
                cap = sl.slice_width_cap or "remainder"
                bullets.append(
                    TaxOptBExplanationBulletV1(
                        kind=TaxOptBExplanationBulletKindV1.SLAB,
                        text=(
                            f"Band {sl.slab_index}: LKR {sl.taxable_in_slice} taxed at {sl.rate} "
                            f"(width cap {cap}) → tax LKR {sl.tax_in_slice}."
                        ),
                        source_refs=[f"slab:{sl.slab_index}"],
                    ),
                )
            if len(tax.slab_slices) > max_slab_lines:
                bullets.append(
                    TaxOptBExplanationBulletV1(
                        kind=TaxOptBExplanationBulletKindV1.SLAB,
                        text=(
                            f"Further slab bands omitted ({len(tax.slab_slices) - max_slab_lines} more); "
                            "see raw tax_computation JSON."
                        ),
                        source_refs=["slab:truncated"],
                    ),
                )
        else:
            n_bands = len(tax.slab_slices)
            bullets.append(
                TaxOptBExplanationBulletV1(
                    kind=TaxOptBExplanationBulletKindV1.SLAB,
                    text=(
                        f"In short, the MVP progressive rates were applied to that taxable amount "
                        f"({n_bands} rate band{'s' if n_bands != 1 else ''}); total tax is LKR {tax.total_tax}. "
                        f"Switch to detailed for a line-by-line slab breakdown."
                    ),
                    source_refs=["slab:aggregate"],
                ),
            )
        return bullets


_default: TemplateExplanationProviderV1 | None = None


def get_template_explanation_provider() -> TemplateExplanationProviderV1:
    global _default
    if _default is None:
        _default = TemplateExplanationProviderV1()
    return _default


__all__ = ["ExplanationDetail", "TemplateExplanationProviderV1", "get_template_explanation_provider"]
