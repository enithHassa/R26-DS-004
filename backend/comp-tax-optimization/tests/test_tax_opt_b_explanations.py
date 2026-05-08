"""FR5 template explainability — unit and HTTP coverage."""

from __future__ import annotations

from decimal import Decimal

from fastapi.testclient import TestClient

from tax_opt_b_app.config import component_settings
from tax_opt_b_app.services.tax_opt_b_compare_strategies import compare_strategies
from tax_opt_b_app.services.tax_opt_b_explanation_builders import (
    build_compare_explanations,
    build_compute_explanations,
)
from tax_opt_b_app.services.tax_opt_b_rules_loader import load_tax_opt_b_rules
from tax_opt_b_app.services.tax_opt_b_tax_computation import run_compliance_and_compute_tax
from tax_opt_b_app.tax_opt_b_schemas_explainability_v1 import TaxOptBExplanationBulletKindV1
from tax_opt_b_app.tax_opt_b_schemas_profile_v1 import TaxOptBProfileV1
from tax_opt_b_app.tax_opt_b_schemas_strategy_v1 import TaxOptBReliefClaimV1, TaxOptBStrategyProposalV1


def test_build_compute_explanations_passing_includes_provenance_and_slab_refs() -> None:
    pack = load_tax_opt_b_rules(component_settings.COMP_OPTIMIZATION_RULES_PATH)
    profile = TaxOptBProfileV1(
        tax_year="2024_25",
        annual_gross_income=Decimal("2400000"),
    )
    strategy = TaxOptBStrategyProposalV1(
        claims=[TaxOptBReliefClaimV1(relief_code="life_insurance_premium", claimed_amount_annual=Decimal("50000"))],
    )
    out = run_compliance_and_compute_tax(profile, strategy, pack, rules_version_label="test")
    bundle = build_compute_explanations(out, detail="detailed")
    assert bundle.provenance.get("engine") == "template_v1"
    assert bundle.provenance.get("deterministic") is True
    assert "Compliance passed" in bundle.summary
    assert "LKR" in bundle.summary
    slab_section = next((s for s in bundle.sections if s.title == "Tax computation walk"), None)
    assert slab_section is not None
    assert any("Band 0" in b.text for b in slab_section.bullets if b.kind == "slab")


def test_build_compute_explanations_failed_compliance() -> None:
    pack = load_tax_opt_b_rules(component_settings.COMP_OPTIMIZATION_RULES_PATH)
    profile = TaxOptBProfileV1(
        tax_year="2024_25",
        annual_gross_income=Decimal("2400000"),
    )
    strategy = TaxOptBStrategyProposalV1(
        claims=[
            TaxOptBReliefClaimV1(relief_code="life_insurance_premium", claimed_amount_annual=Decimal("500000")),
        ],
    )
    out = run_compliance_and_compute_tax(profile, strategy, pack, rules_version_label="test")
    assert out.tax_computation is None
    bundle = build_compute_explanations(out, detail="summary")
    assert "did not pass" in bundle.summary.lower()
    viol = next((s for s in bundle.sections if s.title == "Compliance outcome"), None)
    assert viol is not None
    assert any(b.kind.value == "compliance" for b in viol.bullets)


def test_build_compute_explanations_failed_compliance_multiple_violations() -> None:
    """Template builder lists each cap violation (detailed tier prefixes rule_id)."""
    pack = load_tax_opt_b_rules(component_settings.COMP_OPTIMIZATION_RULES_PATH)
    profile = TaxOptBProfileV1(
        tax_year="2024_25",
        annual_gross_income=Decimal("2400000"),
    )
    strategy = TaxOptBStrategyProposalV1(
        claims=[
            TaxOptBReliefClaimV1(relief_code="life_insurance_premium", claimed_amount_annual=Decimal("500000")),
            TaxOptBReliefClaimV1(relief_code="health_insurance_premium", claimed_amount_annual=Decimal("150000")),
        ],
    )
    out = run_compliance_and_compute_tax(profile, strategy, pack, rules_version_label="test")
    assert not out.compliance.passed
    assert len(out.compliance.violations) >= 2
    bundle = build_compute_explanations(out, detail="detailed")
    viol = next(s for s in bundle.sections if s.title == "Compliance outcome")
    compliance_bullets = [b for b in viol.bullets if b.kind == TaxOptBExplanationBulletKindV1.COMPLIANCE]
    assert len(compliance_bullets) >= 2
    assert all("it22064486" in b.text or "cap" in b.text.lower() for b in compliance_bullets)


def test_build_compute_explanations_passing_applied_relief_multiple_codes() -> None:
    """Passing run surfaces capped allowed amounts per relief in template section."""
    pack = load_tax_opt_b_rules(component_settings.COMP_OPTIMIZATION_RULES_PATH)
    profile = TaxOptBProfileV1(
        tax_year="2024_25",
        annual_gross_income=Decimal("2400000"),
    )
    strategy = TaxOptBStrategyProposalV1(
        claims=[
            TaxOptBReliefClaimV1(relief_code="life_insurance_premium", claimed_amount_annual=Decimal("50000")),
            TaxOptBReliefClaimV1(relief_code="health_insurance_premium", claimed_amount_annual=Decimal("30000")),
        ],
    )
    out = run_compliance_and_compute_tax(profile, strategy, pack, rules_version_label="test")
    assert out.compliance.passed
    assert len(out.compliance.applied_relief) >= 2
    bundle = build_compute_explanations(out, detail="detailed")
    relief_sec = next(s for s in bundle.sections if s.title == "Applied reliefs (after caps)")
    relief_bullets = [b for b in relief_sec.bullets if b.kind == TaxOptBExplanationBulletKindV1.RELIEF]
    assert any("Life insurance premiums" in b.text and "life_insurance_premium" in b.text for b in relief_bullets)
    assert any("Health insurance premiums" in b.text and "health_insurance_premium" in b.text for b in relief_bullets)


def test_build_compute_explanations_slab_walk_multiple_bands_detailed() -> None:
    """Tax walk in detailed tier includes one SLAB bullet per band used (2+ bands for MVP YAML)."""
    pack = load_tax_opt_b_rules(component_settings.COMP_OPTIMIZATION_RULES_PATH)
    profile = TaxOptBProfileV1(
        tax_year="2024_25",
        annual_gross_income=Decimal("2400000"),
    )
    strategy = TaxOptBStrategyProposalV1(claims=[])
    out = run_compliance_and_compute_tax(profile, strategy, pack, rules_version_label="test")
    assert out.tax_computation is not None
    assert len(out.tax_computation.slab_slices) >= 2
    bundle = build_compute_explanations(out, detail="detailed")
    walk = next(s for s in bundle.sections if s.title == "Tax computation walk")
    slab_lines = [b for b in walk.bullets if b.kind == TaxOptBExplanationBulletKindV1.SLAB]
    assert len(slab_lines) >= 2
    assert any("Band 0" in b.text for b in slab_lines)
    assert any("Band 1" in b.text for b in slab_lines)


def test_build_compare_explanations_ranking_and_baseline_delta_text() -> None:
    pack = load_tax_opt_b_rules(component_settings.COMP_OPTIMIZATION_RULES_PATH)
    profile = TaxOptBProfileV1(
        tax_year="2024_25",
        annual_gross_income=Decimal("2400000"),
        estimated_annual_taxable_income=Decimal("1800000"),
    )
    variants = [
        (
            "none",
            None,
            TaxOptBStrategyProposalV1(claims=[]),
        ),
        (
            "life50",
            None,
            TaxOptBStrategyProposalV1(
                claims=[
                    TaxOptBReliefClaimV1(
                        relief_code="life_insurance_premium",
                        claimed_amount_annual=Decimal("50000"),
                    ),
                ],
            ),
        ),
    ]
    resp = compare_strategies(
        profile,
        variants,
        pack,
        baseline_variant_id="none",
        rules_version_label="test",
    )
    bundle = build_compare_explanations(resp, detail="summary")
    assert "Summary comparison" in bundle.summary
    assert "takeaway" in bundle.summary.lower()
    assert "baseline variant" in bundle.summary.lower() and "none" in bundle.summary
    scenario = next(s for s in bundle.sections if s.title == "Scenario comparison")
    texts = " ".join(b.text for b in scenario.bullets)
    assert "Δ vs baseline" in texts or "baseline" in texts.lower()
    assert any("Rank" in b.text and "life50" in b.text for b in scenario.bullets if b.kind == TaxOptBExplanationBulletKindV1.COMPARISON)


def test_compute_explanations_summary_vs_detailed_top_line_differs() -> None:
    pack = load_tax_opt_b_rules(component_settings.COMP_OPTIMIZATION_RULES_PATH)
    profile = TaxOptBProfileV1(tax_year="2024_25", annual_gross_income=Decimal("2400000"))
    strategy = TaxOptBStrategyProposalV1(claims=[])
    out = run_compliance_and_compute_tax(profile, strategy, pack, rules_version_label="test")
    s = build_compute_explanations(out, detail="summary")
    d = build_compute_explanations(out, detail="detailed")
    assert "Summary narrative" in s.summary
    assert "Detailed narrative" in d.summary
    assert s.summary.split()[0:2] != d.summary.split()[0:2]

    s_walk = next(sec for sec in s.sections if sec.title == "Tax computation walk")
    d_walk = next(sec for sec in d.sections if sec.title == "Tax computation walk")
    s_slabs = [b for b in s_walk.bullets if b.kind == TaxOptBExplanationBulletKindV1.SLAB]
    d_slabs = [b for b in d_walk.bullets if b.kind == TaxOptBExplanationBulletKindV1.SLAB]
    assert len(s_slabs) == 1
    assert len(d_slabs) >= 2


def test_summary_relief_uses_conversational_wording() -> None:
    pack = load_tax_opt_b_rules(component_settings.COMP_OPTIMIZATION_RULES_PATH)
    profile = TaxOptBProfileV1(tax_year="2024_25", annual_gross_income=Decimal("2400000"))
    strategy = TaxOptBStrategyProposalV1(
        claims=[TaxOptBReliefClaimV1(relief_code="life_insurance_premium", claimed_amount_annual=Decimal("50000"))],
    )
    out = run_compliance_and_compute_tax(profile, strategy, pack, rules_version_label="test")
    bundle = build_compute_explanations(out, detail="summary")
    relief_sec = next(s for s in bundle.sections if s.title == "Applied reliefs (after caps)")
    life = next(b for b in relief_sec.bullets if "Life insurance premiums" in b.text)
    assert "allowed against your taxable income" in life.text.lower()


def test_http_compute_tax_include_explanations_body(client: TestClient) -> None:
    body = {
        "profile": {
            "tax_year": "2024_25",
            "employment_type": "employee",
            "dependents": 0,
            "annual_gross_income": "2400000",
        },
        "strategy": {"claims": []},
        "include_explanations": True,
        "explanation_detail": "summary",
    }
    resp = client.post("/api/v1/compliance/compute-tax", json=body)
    assert resp.status_code == 200
    data = resp.json()
    assert data.get("explanations") is not None
    assert data["explanations"]["provenance"]["engine"] == "template_v1"
    assert len(data["explanations"]["summary"]) > 20


def test_http_compare_include_explanations(client: TestClient) -> None:
    body = {
        "profile": {
            "tax_year": "2024_25",
            "employment_type": "employee",
            "dependents": 0,
            "annual_gross_income": "2400000",
        },
        "variants": [
            {
                "variant_id": "a",
                "label": "None",
                "strategy": {"claims": []},
            },
            {
                "variant_id": "b",
                "label": "Life",
                "strategy": {
                    "claims": [
                        {"relief_code": "life_insurance_premium", "claimed_amount_annual": "50000"},
                    ],
                },
            },
        ],
        "baseline_variant_id": "a",
        "include_result_detail": False,
        "include_explanations": True,
    }
    resp = client.post(
        "/api/v1/compliance/compare-strategies",
        json=body,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data.get("explanations") is not None
    assert "lowest mvp tax" in data["explanations"]["summary"].lower()
