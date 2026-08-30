"""Load-new-act review surfaces: fixtures, Guide display, mismatch queue.

Live GPT extract is Phase 6 — this router refuses it.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from db.mismatch import OeEngineMismatchFlag
from oe_engine_app.deps import get_session
from oe_engine_app.services.fixtures import (
    list_extract_fixtures,
    load_extract_fixture,
    load_promote_run,
    seed_act_document,
)
from oe_engine_app.services.mismatch_queue import list_flags, set_flag_status
from oe_engine_app.services.terminus import (
    accept_guide_display,
    apply_extract_terminus,
    guide_notes_for,
    list_guide_displays,
    load_guide_display,
)

router = APIRouter(tags=["load-act"])


class ExtractRequest(BaseModel):
    source_doc_id: str
    dry_run: bool = True


class FixtureApplyRequest(BaseModel):
    file_name: str


class MismatchStatusRequest(BaseModel):
    status: str


class GuideAcceptRequest(BaseModel):
    source_doc_id: str


@router.get("/extract-fixtures")
def get_extract_fixtures() -> dict[str, Any]:
    rows = list_extract_fixtures()
    return {"fixtures": rows, "fixture_count": len(rows)}


@router.get("/review/{source_doc_id}")
def get_review(source_doc_id: str, extraction_run_id: str | None = None) -> dict[str, Any]:
    try:
        run = load_promote_run(source_doc_id, extraction_run_id)
    except FileNotFoundError:
        for row in list_extract_fixtures():
            if row["source_doc_id"] == source_doc_id:
                run = load_extract_fixture(row["file_name"])
                break
        else:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"no extract run for {source_doc_id}",
            ) from None
    return {
        "source_doc_id": run.source_doc_id,
        "tier": run.tier,
        "terminus": run.terminus,
        "extraction_run_id": run.extraction_run_id,
        "promote_allowed": run.tier == "act",
        "entities": run.entities,
        "entity_count": len(run.entities),
    }


@router.post("/extract")
def post_extract(body: ExtractRequest) -> dict[str, Any]:
    if not body.dry_run:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Live extract is Phase 6. Use dry_run=true ($0) or wait for seed.",
        )
    return {
        "source_doc_id": body.source_doc_id,
        "dry_run": True,
        "usd_this_run": 0.0,
        "detail": "Dry-run acknowledged. Full-document live extract is Phase 6.",
    }


@router.post("/fixtures/apply")
def post_fixture_apply(body: FixtureApplyRequest) -> dict[str, Any]:
    session = get_session()
    try:
        run = load_extract_fixture(body.file_name)
        if run.tier == "act":
            seed_act_document(session, source_doc_id=run.source_doc_id, title=run.source_doc_id)
        result = apply_extract_terminus(session, run)
        session.commit()
        return {
            "source_doc_id": run.source_doc_id,
            "tier": run.tier,
            "terminus": run.terminus,
            "promote_allowed": False,
            "result": result,
        }
    except FileNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    finally:
        session.close()


@router.get("/mismatches")
def get_mismatches() -> dict[str, Any]:
    session = get_session()
    try:
        flags = list_flags(session)
        return {"flags": flags, "flag_count": len(flags)}
    finally:
        session.close()


@router.patch("/mismatches/{flag_id}")
def patch_mismatch(flag_id: int, body: MismatchStatusRequest) -> dict[str, Any]:
    session = get_session()
    try:
        flag: OeEngineMismatchFlag = set_flag_status(session, flag_id, body.status)
        session.commit()
        return {
            "id": flag.id,
            "status": flag.status,
            "compare_group_id": flag.compare_group_id,
            "year": flag.year,
        }
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except KeyError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="flag not found") from None
    finally:
        session.close()


@router.get("/guide-display")
def get_guide_display_index() -> dict[str, Any]:
    rows = list_guide_displays()
    return {"displays": rows, "display_count": len(rows)}


@router.get("/guide-display/{source_doc_id}")
def get_one_guide_display(source_doc_id: str) -> dict[str, Any]:
    try:
        payload = load_guide_display(source_doc_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return payload


@router.post("/guide-display/update")
def post_guide_update(body: GuideAcceptRequest) -> dict[str, Any]:
    try:
        return accept_guide_display(body.source_doc_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.get("/guide-notes")
def get_guide_notes(compare_group_id: str | None = None) -> dict[str, Any]:
    notes = guide_notes_for(compare_group_id)
    return {"notes": notes, "note_count": len(notes), "source_label": "Guide"}


@router.post("/ingest/{source_doc_id}")
def post_ingest_existing(source_doc_id: str) -> dict[str, Any]:
    """Re-ingest a manifest PDF. Hash match is $0; new bytes need embeddings."""
    from oe_engine_app.services.ingest import ingest_manifest

    session = get_session()
    try:
        class _SkipEmbedder:
            model = "none"

            def embed_batch(self, texts: list[str]) -> list[list[float]]:
                raise RuntimeError("new PDF ingest needs OPENAI_API_KEY (not Phase 5)")

        results = ingest_manifest(session, embedder=_SkipEmbedder(), source_doc_id=source_doc_id)
        if not results:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"unknown source_doc_id {source_doc_id}",
            )
        row = results[0]
        return {
            "source_doc_id": row.source_doc_id,
            "status": row.status,
            "chunk_count": row.chunk_count,
            "embedding_usd": row.embedding_usd,
            "detail": row.detail,
        }
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    finally:
        session.close()
