"""Save and reload Optimization Engine snapshots per financial profile."""

from __future__ import annotations

import uuid
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.models.tax_computation_snapshot import TaxComputationSnapshot
from app.schemas.tax_computation_snapshot import (
    TaxComputationSnapshotDetail,
    TaxComputationSnapshotSummary,
    TaxComputationSnapshotUpsert,
)


class SnapshotNotFoundError(LookupError):
    """Raised when a snapshot id does not belong to the profile."""


def _to_summary(row: TaxComputationSnapshot) -> TaxComputationSnapshotSummary:
    return TaxComputationSnapshotSummary(
        id=row.id,
        financial_profile_id=row.financial_profile_id,
        assessment_year=row.assessment_year,
        status=row.status,  # type: ignore[arg-type]
        taxpayer_name=row.taxpayer_name,
        tin=row.tin,
        source=row.source,  # type: ignore[arg-type]
        created_at=row.created_at,
        updated_at=row.updated_at,
        has_calculate_result=row.calculate_result is not None,
    )


def _to_detail(row: TaxComputationSnapshot) -> TaxComputationSnapshotDetail:
    return TaxComputationSnapshotDetail(
        **_to_summary(row).model_dump(),
        income_state=row.income_state,
        relief_answers=list(row.relief_answers or []),
        evidence_checks=dict(row.evidence_checks or {}),
        session_meta=row.session_meta,
        calculate_result=row.calculate_result,
        explain_narrative=row.explain_narrative,
        created_by=row.created_by,
    )


def _apply_payload(row: TaxComputationSnapshot, payload: TaxComputationSnapshotUpsert) -> None:
    row.assessment_year = payload.assessment_year
    row.status = payload.status
    row.taxpayer_name = payload.taxpayer_name
    row.tin = payload.tin
    row.income_state = payload.income_state
    row.relief_answers = payload.relief_answers
    row.evidence_checks = payload.evidence_checks
    row.session_meta = payload.session_meta
    row.calculate_result = payload.calculate_result
    row.explain_narrative = payload.explain_narrative
    row.source = payload.source
    row.created_by = payload.created_by


def save_snapshot(
    db: Session,
    *,
    profile_id: uuid.UUID,
    payload: TaxComputationSnapshotUpsert,
) -> TaxComputationSnapshotDetail:
    # Upsert draft and finalized so the same profile+YA has one official row each.
    if payload.status in ("draft", "finalized"):
        existing = db.scalar(
            select(TaxComputationSnapshot).where(
                TaxComputationSnapshot.financial_profile_id == profile_id,
                TaxComputationSnapshot.assessment_year == payload.assessment_year,
                TaxComputationSnapshot.status == payload.status,
            ),
        )
        if existing is not None:
            _apply_payload(existing, payload)
            db.commit()
            db.refresh(existing)
            return _to_detail(existing)

    row = TaxComputationSnapshot(financial_profile_id=profile_id)
    _apply_payload(row, payload)
    db.add(row)
    db.commit()
    db.refresh(row)
    return _to_detail(row)


def list_snapshots(
    db: Session,
    *,
    profile_id: uuid.UUID,
    assessment_year: str | None = None,
    limit: int = 20,
) -> list[TaxComputationSnapshotSummary]:
    stmt = select(TaxComputationSnapshot).where(
        TaxComputationSnapshot.financial_profile_id == profile_id,
    )
    if assessment_year is not None:
        stmt = stmt.where(TaxComputationSnapshot.assessment_year == assessment_year)
    rows = list(
        db.scalars(
            stmt.order_by(
                desc(TaxComputationSnapshot.updated_at),
                desc(TaxComputationSnapshot.created_at),
            ).limit(limit),
        ).all(),
    )
    return [_to_summary(row) for row in rows]


def get_latest_snapshot(
    db: Session,
    *,
    profile_id: uuid.UUID,
    assessment_year: str | None = None,
    prefer_status: str | None = None,
) -> TaxComputationSnapshotDetail | None:
    base = select(TaxComputationSnapshot).where(
        TaxComputationSnapshot.financial_profile_id == profile_id,
    )
    if assessment_year is not None:
        base = base.where(TaxComputationSnapshot.assessment_year == assessment_year)

    # Taxpayer view wants finalized first; auditor draft reload prefers calculated.
    if prefer_status == "finalized":
        status_order = ("finalized", "calculated", "draft")
    elif prefer_status == "draft":
        status_order = ("draft", "calculated", "finalized")
    else:
        status_order = ("calculated", "draft", "finalized")

    for status in status_order:
        row = db.scalar(
            base.where(TaxComputationSnapshot.status == status).order_by(
                desc(TaxComputationSnapshot.updated_at),
                desc(TaxComputationSnapshot.created_at),
            ),
        )
        if row is not None:
            return _to_detail(row)

    row = db.scalar(
        base.order_by(
            desc(TaxComputationSnapshot.updated_at),
            desc(TaxComputationSnapshot.created_at),
        ),
    )
    return _to_detail(row) if row is not None else None


def get_snapshot(
    db: Session,
    *,
    profile_id: uuid.UUID,
    snapshot_id: uuid.UUID,
) -> TaxComputationSnapshotDetail:
    row = db.scalar(
        select(TaxComputationSnapshot).where(
            TaxComputationSnapshot.id == snapshot_id,
            TaxComputationSnapshot.financial_profile_id == profile_id,
        ),
    )
    if row is None:
        raise SnapshotNotFoundError(f"Snapshot {snapshot_id} not found for profile {profile_id}")
    return _to_detail(row)


def update_snapshot_status(
    db: Session,
    *,
    profile_id: uuid.UUID,
    snapshot_id: uuid.UUID,
    status: str,
) -> TaxComputationSnapshotDetail:
    row = db.scalar(
        select(TaxComputationSnapshot).where(
            TaxComputationSnapshot.id == snapshot_id,
            TaxComputationSnapshot.financial_profile_id == profile_id,
        ),
    )
    if row is None:
        raise SnapshotNotFoundError(f"Snapshot {snapshot_id} not found for profile {profile_id}")
    row.status = status
    db.commit()
    db.refresh(row)
    return _to_detail(row)
