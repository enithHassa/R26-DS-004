"""Proof Map schemas for traceable advisory output."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

ProofStepKind = Literal[
    "user_query",
    "retrieval",
    "knowledge_graph",
    "evidence",
    "symbolic_validation",
    "advisory_output",
]


class ProofMapStep(BaseModel):
    step_id: str
    kind: ProofStepKind
    label: str
    detail: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class ProofMap(BaseModel):
    steps: list[ProofMapStep] = Field(default_factory=list)
    evidence_refs: list[dict[str, str | None]] = Field(default_factory=list)
    validation_status: str = Field(
        default="not_run",
        description="skipped | passed | corrected | not_run",
    )
    rule_engine_version: str | None = None
