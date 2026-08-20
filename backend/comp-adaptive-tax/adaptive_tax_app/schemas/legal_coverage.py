"""Phase 6.8 — legal coverage dashboard DTOs."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

AssessmentYear = Literal["2024_25", "2025_26"]


class CoverageComponentRow(BaseModel):
    """One catalog component within a section grain."""

    model_config = ConfigDict(str_strip_whitespace=True)

    component_id: str
    display_name: str
    section: str | None = None
    status: str
    engine_support: str
    approved: bool
    engine_wired: bool
    provenance_complete: bool
    covered: bool


class SectionCoverageRow(BaseModel):
    """Section-grain coverage: covered / planned catalog components."""

    model_config = ConfigDict(str_strip_whitespace=True)

    section_key: str
    label: str
    n_planned: int
    n_covered: int
    coverage: float
    coverage_pct: float
    checklist_area_id: str | None = None
    checklist_covered: bool | None = None
    components: list[CoverageComponentRow] = Field(default_factory=list)


class ChecklistAreaSummary(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    area_id: str
    meaning: str
    covered: bool
    harvested: bool
    approved: bool
    engine_wired: bool
    provenance_complete: bool
    optional: bool = False


class AreaCoverageSummary(BaseModel):
    """Phase 5 checklist rollup (from score_coverage)."""

    model_config = ConfigDict(str_strip_whitespace=True)

    n_planned: int
    n_covered: int
    coverage: float
    coverage_pct: float
    covered_area_ids: list[str] = Field(default_factory=list)
    pending_area_ids: list[str] = Field(default_factory=list)
    areas: list[ChecklistAreaSummary] = Field(default_factory=list)


class LegalCoverageResponseV1(BaseModel):
    """GET /api/v1/knowledge/legal-coverage — viva / Chapter 4 export."""

    model_config = ConfigDict(str_strip_whitespace=True)

    spec_version: str = "6.8.0"
    catalog_version: str
    act_version_label: str
    assessment_years: list[AssessmentYear] = Field(default_factory=list)
    area_summary: AreaCoverageSummary
    sections: list[SectionCoverageRow] = Field(default_factory=list)
    definition: str = (
        "Section coverage = components where (approved ∧ engine_wired ∧ "
        "provenance_complete) / planned catalog components for that section. "
        "Schedule rows without catalog components use the Phase 5 checklist area."
    )
