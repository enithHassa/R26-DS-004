"""Act-only promote terminus. Guide / Consolidated return 400."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from oe_engine_app.deps import get_session
from oe_engine_app.services.fixtures import load_promote_run
from oe_engine_app.services.terminus import (
    ChunkCoverageError,
    PromoteForbidden,
    assert_promote_allowed,
    document_tier,
    promote_act_run,
)

router = APIRouter(tags=["extract"])


class PromoteRequest(BaseModel):
    source_doc_id: str
    extraction_run_id: str | None = None


@router.post("/promote")
def post_promote(body: PromoteRequest) -> dict[str, Any]:
    session = get_session()
    try:
        try:
            tier = document_tier(session, body.source_doc_id)
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
        try:
            assert_promote_allowed(tier)
        except PromoteForbidden as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
        try:
            run = load_promote_run(body.source_doc_id, body.extraction_run_id)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
        try:
            result = promote_act_run(session, run)
        except ChunkCoverageError as exc:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
        session.commit()
        return result
    finally:
        session.close()
