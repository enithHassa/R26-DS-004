"""Year catalog from compiled oe_engine_year_* views."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Query

from oe_engine_app.deps import get_session
from oe_engine_app.services import year_store

router = APIRouter(tags=["catalog"])


@router.get("/years")
def get_years() -> dict[str, Any]:
    session = get_session()
    try:
        years = year_store.list_years(session)
        slugs = [row["assessment_year"] for row in years]
        return {
            "assessment_years": slugs,
            "years": years,
            "year_count": len(slugs),
        }
    finally:
        session.close()


@router.get("/acts/{assessment_year}")
def get_acts(assessment_year: str) -> dict[str, Any]:
    session = get_session()
    try:
        acts = year_store.acts_for_year(session, assessment_year)
        return {
            "assessment_year": assessment_year,
            "acts": acts,
            "act_count": len(acts),
        }
    finally:
        session.close()


@router.get("/reliefs/{assessment_year}")
def get_reliefs(
    assessment_year: str,
    exclude_source_doc_id: str | None = Query(default=None),
) -> dict[str, Any]:
    session = get_session()
    try:
        entries = year_store.reliefs_for_year(
            session, assessment_year, exclude_source_doc_id
        ) or []
        return {
            "assessment_year": assessment_year,
            "exclude_source_doc_id": (exclude_source_doc_id or "").strip() or None,
            "entries": entries,
            "entry_count": len(entries),
        }
    finally:
        session.close()


@router.get("/rates/{assessment_year}")
def get_rates(
    assessment_year: str,
    exclude_source_doc_id: str | None = Query(default=None),
) -> dict[str, Any]:
    session = get_session()
    try:
        bands = year_store.rates_for_year(
            session, assessment_year, exclude_source_doc_id
        ) or []
        return {
            "assessment_year": assessment_year,
            "exclude_source_doc_id": (exclude_source_doc_id or "").strip() or None,
            "bands": bands,
            "band_count": len(bands),
        }
    finally:
        session.close()


@router.get("/compare")
def get_compare(
    exclude_source_doc_id: str | None = Query(default=None),
    compare_group_id: str | None = Query(default=None),
) -> dict[str, Any]:
    session = get_session()
    try:
        years = [row["assessment_year"] for row in year_store.list_years(session)]
        skip = (exclude_source_doc_id or "").strip() or None
        group_filter = (compare_group_id or "").strip() or None
        buckets: list[dict[str, Any]] = []
        labels: dict[str, str] = {}
        for ya in years:
            entries = year_store.reliefs_for_year(session, ya, skip) or []
            for entry in entries:
                gid = str(entry.get("compare_group_id") or "")
                if gid and gid not in labels:
                    labels[gid] = str(entry.get("display_name") or gid)
            if group_filter:
                entries = [
                    e for e in entries if str(e.get("compare_group_id") or "") == group_filter
                ]
            buckets.append(
                {"assessment_year": ya, "entries": entries, "entry_count": len(entries)}
            )
        groups = [
            {"compare_group_id": gid, "display_name": name}
            for gid, name in sorted(labels.items(), key=lambda item: item[1].lower())
        ]
        series = None
        if group_filter:
            series = [
                {
                    "assessment_year": bucket["assessment_year"],
                    "entry": (bucket["entries"][0] if bucket["entries"] else None),
                    "cap_amount": (
                        bucket["entries"][0].get("cap_amount") if bucket["entries"] else None
                    ),
                }
                for bucket in buckets
            ]
        return {
            "assessment_years": years,
            "exclude_source_doc_id": skip,
            "compare_group_id": group_filter,
            "years": buckets,
            "groups": groups,
            "group_count": len(groups),
            "series": series,
        }
    finally:
        session.close()


@router.post("/index/refresh")
def post_index_refresh() -> dict[str, Any]:
    session = get_session()
    try:
        from oe_engine_app.services.compiler import recompile_year_views

        recompile_year_views(session, persist=True)
        session.commit()
        years = year_store.list_years(session)
        return {
            "status": "ok",
            "years": [row["assessment_year"] for row in years],
            "year_count": len(years),
            "detail": "Recompiled year views from promoted Act entities.",
        }
    finally:
        session.close()
