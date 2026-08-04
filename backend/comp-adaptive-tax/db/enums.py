"""Enum types specific to the Adaptive Tax amendment pipeline."""

from __future__ import annotations

import enum

from sqlalchemy.dialects.postgresql import ENUM


class AmendmentJobStatus(str, enum.Enum):
    UPLOADED = "uploaded"
    EXTRACTING = "extracting"
    EXTRACTED = "extracted"
    APPROVED = "approved"
    REJECTED = "rejected"
    FAILED = "failed"


class AmendmentExtractRunStatus(str, enum.Enum):
    STARTED = "started"
    COMPLETED = "completed"
    FAILED = "failed"


class RuleSourceStatus(str, enum.Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class RuleType(str, enum.Enum):
    DEDUCTION = "deduction"
    EXEMPTION = "exemption"
    RATE = "rate"
    DEFINITION = "definition"
    LIMIT = "limit"
    CONDITION = "condition"


def _values(obj: type[enum.Enum]) -> list[str]:
    return [e.value for e in obj]


amendment_job_status_enum = ENUM(
    AmendmentJobStatus,
    name="amendment_job_status",
    create_type=True,
    values_callable=_values,
)

amendment_extract_run_status_enum = ENUM(
    AmendmentExtractRunStatus,
    name="amendment_extract_run_status",
    create_type=True,
    values_callable=_values,
)

rule_source_status_enum = ENUM(
    RuleSourceStatus,
    name="rule_source_status",
    create_type=True,
    values_callable=_values,
)

rule_type_enum = ENUM(
    RuleType,
    name="adaptive_tax_rule_type",
    create_type=True,
    values_callable=_values,
)
