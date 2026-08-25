"""Cross-year relief compare from the RAG index (not hardcoded group lists)."""

from __future__ import annotations

from typing import Any

from opt_explain_app.services import rag_index


def _group_label(entries: list[dict[str, Any]]) -> dict[str, str]:
    labels: dict[str, str] = {}
    for doc in entries:
        group = str(doc.get("compare_group_id") or "").strip()
        if not group or group in labels:
            continue
        labels[group] = str(doc.get("display_name") or group).strip() or group
    return labels


def compare_reliefs(
    exclude_source_doc_id: str | None = None,
    compare_group_id: str | None = None,
) -> dict[str, Any]:
    """Build a multi-year compare payload from indexed reliefs.

    Years come from approved catalog files on disk — new promotes add rows
    automatically after ``POST /index/refresh``.
    """
    skip = (exclude_source_doc_id or "").strip() or None
    group_filter = (compare_group_id or "").strip() or None

    year_rows = rag_index.list_years()
    assessment_years = [row["assessment_year"] for row in year_rows]

    buckets: list[dict[str, Any]] = []
    all_labels: dict[str, str] = {}

    for ya in assessment_years:
        docs = rag_index.reliefs_for_year(ya, skip) or []
        all_labels.update(_group_label(docs))

    for ya in assessment_years:
        docs = rag_index.reliefs_for_year(ya, skip) or []
        if group_filter:
            docs = [
                doc
                for doc in docs
                if str(doc.get("compare_group_id") or "") == group_filter
            ]
        buckets.append(
            {
                "assessment_year": ya,
                "entries": docs,
                "entry_count": len(docs),
            }
        )

    groups = [
        {"compare_group_id": gid, "display_name": name}
        for gid, name in sorted(all_labels.items(), key=lambda item: item[1].lower())
    ]

    series: list[dict[str, Any]] | None = None
    if group_filter:
        series = []
        for bucket in buckets:
            ya = bucket["assessment_year"]
            matches = [
                doc
                for doc in bucket["entries"]
                if str(doc.get("compare_group_id") or "") == group_filter
            ]
            entry = matches[0] if matches else None
            series.append(
                {
                    "assessment_year": ya,
                    "entry": entry,
                    "cap_amount": entry.get("cap_amount") if entry else None,
                    "source_doc_id": entry.get("source_doc_id") if entry else None,
                    "section_ref": entry.get("section_ref") if entry else None,
                    "needs_manual_verification": bool(
                        entry.get("needs_manual_verification") if entry else False
                    ),
                }
            )

    return {
        "assessment_years": assessment_years,
        "exclude_source_doc_id": skip,
        "compare_group_id": group_filter,
        "years": buckets,
        "groups": groups,
        "group_count": len(groups),
        "series": series,
    }
