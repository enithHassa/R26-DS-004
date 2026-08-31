"""Phase 4 runtime param override — personal relief adaptivity for viva T1≠T2."""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from adaptive_tax_app.config import get_adaptive_tax_settings
from adaptive_tax_app.db_loader import (
    AmendmentJob,
    AmendmentJobStatus,
    RuleSource,
    RuleSourceStatus,
    RuleType,
)
from adaptive_tax_app.schemas.calculate import CalculateTaxRequestV1
from adaptive_tax_app.services.amendment_review import approve_amendment
from adaptive_tax_app.services.param_store import (
    _is_sec52_cap_rule_legacy,
    is_sec52_cap_rule,
    load_tax_param_pack,
    read_param_override,
    reset_param_override,
    seed_pre_amend_override,
    write_sec52_override_from_rules,
)
from adaptive_tax_app.services.rule_engine import calculate, default_file_kg

# Viva T1≠T2: YA 2025/26 salary only — pre-amend 1.2M PR vs post-amend 1.8M PR.
_VIVA_INPUTS = CalculateTaxRequestV1(
    assessment_year="2025_26",
    resident_status="resident",
    employment_income=Decimal("3000000"),
    qualifying_payments=Decimal("0"),
    param_set="current",
)


def test_is_sec52_cap_rule_deprecated_always_false() -> None:
    assert not is_sec52_cap_rule(
        concept_id="qualifying_payment_cap",
        section="52",
        amends_section=None,
        maximum=1_800_000,
    )


def test_legacy_sec52_cap_matcher_for_reference() -> None:
    assert _is_sec52_cap_rule_legacy(
        concept_id="qualifying_payment_cap",
        section="52",
        amends_section=None,
        maximum=1_800_000,
    )
    assert not _is_sec52_cap_rule_legacy(
        concept_id="personal_relief",
        section="First Schedule",
        amends_section=None,
        maximum=1_200_000,
    )


def test_seed_pre_amend_override_changes_personal_relief() -> None:
    settings = get_adaptive_tax_settings()
    assert not settings.param_override_path.is_file()

    baseline = load_tax_param_pack(
        assessment_year="2025_26", param_set="current", settings=settings
    )
    assert baseline.relief_for_concept("personal_relief").cap_amount == Decimal(
        "1800000"
    )

    result = seed_pre_amend_override(settings=settings)
    assert result.cap_amount == Decimal("1200000")
    assert result.concept_id == "personal_relief"
    assert result.path.is_file()

    overridden = load_tax_param_pack(
        assessment_year="2025_26", param_set="current", settings=settings
    )
    assert overridden.relief_for_concept("personal_relief").cap_amount == Decimal("1200000")
    pre = load_tax_param_pack(param_set="pre_amend_2025", settings=settings)
    assert pre.relief_for_concept("personal_relief").cap_amount == Decimal("1200000")


def test_reset_param_override_restores_ontology_current() -> None:
    settings = get_adaptive_tax_settings()
    seed_pre_amend_override(settings=settings)
    assert load_tax_param_pack(
        assessment_year="2025_26", param_set="current", settings=settings
    ).relief_for_concept("personal_relief").cap_amount == Decimal("1200000")

    assert reset_param_override(settings=settings) is True
    assert not settings.param_override_path.is_file()
    assert load_tax_param_pack(
        assessment_year="2025_26", param_set="current", settings=settings
    ).relief_for_concept("personal_relief").cap_amount == Decimal("1800000")


def test_approve_writes_personal_relief_override_and_tax_changes() -> None:
    """Reset → T1; approve personal relief Act 02/2025 → T2 ≠ T1."""
    settings = get_adaptive_tax_settings()
    seed_pre_amend_override(settings=settings)

    t1 = calculate(_VIVA_INPUTS, kg=default_file_kg())
    assert t1.final_tax_lkr == "222000"

    job = AmendmentJob(
        original_filename="act.pdf",
        content_type="application/pdf",
        size_bytes=10,
        file_hash="abc",
        storage_path="/tmp/act.pdf",
        status=AmendmentJobStatus.EXTRACTED,
    )
    job.id = uuid.uuid4()
    rule = RuleSource(
        amendment_job_id=job.id,
        sort_order=0,
        section="Fifth Schedule",
        rule_type=RuleType.LIMIT,
        concept_id="personal_relief",
        maximum=1_800_000.0,
        effective_date=date(2025, 4, 1),
        amends_section="Fifth Schedule",
        source_quote=(
            "Personal relief for a resident individual shall be one million "
            "eight hundred thousand rupees for the year of assessment."
        ),
        status=RuleSourceStatus.PENDING,
    )
    rule.id = uuid.uuid4()

    db = MagicMock()
    db.get.return_value = job

    with (
        patch(
            "adaptive_tax_app.services.amendment_review.get_job_rule_sources",
            return_value=[rule],
        ),
        patch(
            "adaptive_tax_app.services.amendment_review.merge_approved_amendment",
        ) as merge_fn,
    ):
        from adaptive_tax_app.merge.amendment_merge import AmendmentMergeResult

        merge_fn.return_value = AmendmentMergeResult(
            merged=False,
            reason="neo4j_unavailable",
            amendment_job_id=job.id,
            details={},
        )
        result = approve_amendment(db=db, job_id=job.id)

    assert result.param_override is None
    assert result.personal_relief_override is not None
    assert result.personal_relief_override.cap_amount == Decimal("1800000")
    assert result.personal_relief_override.rule_source_id == str(rule.id)

    t2 = calculate(_VIVA_INPUTS, kg=default_file_kg())
    assert t2.final_tax_lkr == "96000"
    assert t2.final_tax_lkr != t1.final_tax_lkr


def test_write_sec52_override_skips_non_matching_rules() -> None:
    settings = get_adaptive_tax_settings()
    rule = RuleSource(
        amendment_job_id=uuid.uuid4(),
        sort_order=0,
        section="5",
        rule_type=RuleType.DEFINITION,
        concept_id="employment_income",
        maximum=None,
        source_quote="Employment income is defined in Section 5 of the principal enactment.",
        status=RuleSourceStatus.PENDING,
    )
    rule.id = uuid.uuid4()
    assert write_sec52_override_from_rules([rule], settings=settings) is None
    assert not settings.param_override_path.is_file()


def test_reset_to_pre_amend_api(client: TestClient) -> None:
    response = client.post("/api/v1/admin/params/reset-to-pre-amend")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["ok"] is True
    assert body["personal_relief_cap"] == "1200000"
    assert body["concept_id"] == "personal_relief"
    assert Path(body["override_path"]).is_file()

    calc = client.post(
        "/api/v1/calculate",
        json={
            "assessment_year": "2025_26",
            "resident_status": "resident",
            "employment_income": "3000000",
            "qualifying_payments": "0",
            "param_set": "current",
        },
    )
    assert calc.status_code == 200, calc.text
    assert calc.json()["final_tax_lkr"] == "222000"
