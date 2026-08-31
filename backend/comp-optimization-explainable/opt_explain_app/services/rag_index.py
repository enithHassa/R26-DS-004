"""Seed and load year-indexed rule/rate docs from approved catalogs.

Years come from files on disk. There is no SUPPORTED_YAS enum.
"""

from __future__ import annotations

import json
import logging
import threading
from pathlib import Path
from typing import Any

from opt_explain_app.config import OptimizationExplainableSettings, get_oe_settings

logger = logging.getLogger(__name__)

_LOCK = threading.Lock()
_RULES_BY_YEAR: dict[str, list[dict[str, Any]]] = {}
_RATES_BY_YEAR: dict[str, list[dict[str, Any]]] = {}


def _read_json(path: Path) -> dict[str, Any] | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning("Skipping unreadable catalog %s: %s", path.name, exc)
        return None
    return data if isinstance(data, dict) else None


def _year_from_path(path: Path, payload: dict[str, Any]) -> str:
    slug = path.stem.strip()
    inner = str(payload.get("assessment_year") or "").strip()
    return slug or inner


_CATALOG_ADMIN_SOURCES = frozenset({"catalog_admin_update", "catalog_admin_new_year"})
_WATCHER_DEMO_MARKERS = ("watcher-demo", "watcher_demo", "ird-amend-watcher-demo")


def _blob_is_synthetic_demo(payload: dict[str, Any]) -> bool:
    notes = str(payload.get("notes") or "")
    promotion_source = str(payload.get("promotion_source") or "")
    watcher = str(payload.get("watcher_source_doc_id") or "")
    blob = f"{notes} {promotion_source} {watcher}".upper()
    if "SYNTHETIC" in blob:
        return True
    if "WATCHER-DEMO" in blob or "WATCHER_DEMO" in blob:
        return True
    watcher_l = watcher.lower()
    return any(marker in watcher_l for marker in _WATCHER_DEMO_MARKERS)


def _catalog_has_indexable_content(payload: dict[str, Any]) -> bool:
    if payload.get("phase1_empty_skeleton"):
        return False
    entries = payload.get("entries")
    if isinstance(entries, list) and entries:
        return True
    bands = payload.get("bands")
    return isinstance(bands, list) and bool(bands)


def _is_synthetic_demo_year(ya: str, payload: dict[str, Any]) -> bool:
    """Skip watcher/demo fixtures. Catalog-admin promoted years are indexed."""
    return not _should_index_year(ya, payload)


def _should_index_year(ya: str, payload: dict[str, Any]) -> bool:
    """True when this year file should appear in the OE RAG index."""
    if not ya:
        return False
    promotion_source = str(payload.get("promotion_source") or "").strip()
    if promotion_source in _CATALOG_ADMIN_SOURCES:
        return True
    if _blob_is_synthetic_demo(payload):
        return False
    # Catalog-admin NEW_YEAR uses Phase 6 cmd_promote, which stamps phase6_watcher.
    if promotion_source == "phase6_watcher":
        return _catalog_has_indexable_content(payload)
    return True


def _newest_mtime(directory: Path) -> float | None:
    if not directory.is_dir():
        return None
    paths = list(directory.glob("*.json"))
    if not paths:
        return None
    return max(path.stat().st_mtime for path in paths)


def _catalog_newer_than_index(cfg: OptimizationExplainableSettings) -> bool:
    """True when live approved/rates changed after the last RAG index write."""
    catalog_times = [
        t
        for t in (_newest_mtime(cfg.approved_dir), _newest_mtime(cfg.rates_dir))
        if t is not None
    ]
    index_times = [
        t
        for t in (_newest_mtime(cfg.rule_docs_dir), _newest_mtime(cfg.rate_docs_dir))
        if t is not None
    ]
    if not catalog_times:
        return False
    if not index_times:
        return True
    return max(catalog_times) > max(index_times)


def _rule_doc(ya: str, entry: dict[str, Any]) -> dict[str, Any] | None:
    entry_id = str(entry.get("entry_id") or "").strip()
    if not entry_id:
        return None
    cap = entry.get("cap_amount")
    if cap is not None:
        cap = str(cap).replace(",", "").strip()
    binding = entry.get("engine_binding")
    if not isinstance(binding, dict):
        binding = {"kind": "none"}
    return {
        "doc_id": f"{ya}:{entry_id}",
        "assessment_year": ya,
        "entry_id": entry_id,
        "compare_group_id": str(entry.get("compare_group_id") or ""),
        "display_name": str(entry.get("display_name") or ""),
        "question_prompt": str(entry.get("question_prompt") or ""),
        "input_kind": str(entry.get("input_kind") or "notice"),
        "help": str(entry.get("help") or ""),
        "auto_applied": bool(entry.get("auto_applied")),
        "cap_amount": cap,
        "unit": str(entry.get("unit") or "lkr"),
        "engine_binding": binding,
        "act_name": str(entry.get("act_name") or ""),
        "section_ref": str(entry.get("section_ref") or ""),
        "quote": str(entry.get("quote") or ""),
        "source_doc_id": str(entry.get("source_doc_id") or ""),
        "needs_manual_verification": bool(entry.get("needs_manual_verification")),
        "sort_order": int(entry.get("sort_order") or 0),
    }


def _rate_doc(ya: str, band: dict[str, Any]) -> dict[str, Any] | None:
    try:
        band_index = int(band.get("band_index"))
    except (TypeError, ValueError):
        return None
    return {
        "doc_id": f"{ya}:band:{band_index}",
        "assessment_year": ya,
        "band_index": band_index,
        "lower": band.get("lower"),
        "upper": band.get("upper"),
        "rate_percent": band.get("rate_percent"),
        "band_label": str(band.get("band_label") or ""),
        "act_name": str(band.get("act_name") or ""),
        "section_ref": str(band.get("section_ref") or ""),
        "quote": str(band.get("quote") or ""),
        "source_doc_id": str(band.get("source_doc_id") or ""),
        "currency": "LKR",
    }


def _write_year_file(directory: Path, ya: str, docs: list[dict[str, Any]]) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{ya}.json"
    path.write_text(json.dumps(docs, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _clear_dir(directory: Path) -> None:
    if not directory.is_dir():
        return
    for leftover in directory.glob("*.json"):
        leftover.unlink(missing_ok=True)


def refresh_index(
    settings: OptimizationExplainableSettings | None = None,
) -> dict[str, Any]:
    """Re-read approved catalogs and rewrite the year-indexed RAG store."""
    cfg = settings or get_oe_settings()
    rules: dict[str, list[dict[str, Any]]] = {}
    rates: dict[str, list[dict[str, Any]]] = {}

    if cfg.approved_dir.is_dir():
        for path in sorted(cfg.approved_dir.glob("*.json")):
            payload = _read_json(path)
            if payload is None:
                continue
            ya = _year_from_path(path, payload)
            if not ya or not _should_index_year(ya, payload):
                continue
            entries = payload.get("entries")
            docs: list[dict[str, Any]] = []
            if isinstance(entries, list):
                for raw in entries:
                    if not isinstance(raw, dict):
                        continue
                    doc = _rule_doc(ya, raw)
                    if doc:
                        docs.append(doc)
            docs.sort(key=lambda d: (d.get("sort_order", 0), d.get("entry_id", "")))
            rules[ya] = docs

    if cfg.rates_dir.is_dir():
        for path in sorted(cfg.rates_dir.glob("*.json")):
            payload = _read_json(path)
            if payload is None:
                continue
            ya = _year_from_path(path, payload)
            if not ya or not _should_index_year(ya, payload):
                continue
            bands = payload.get("bands")
            docs = []
            if isinstance(bands, list):
                for raw in bands:
                    if not isinstance(raw, dict):
                        continue
                    doc = _rate_doc(ya, raw)
                    if doc:
                        docs.append(doc)
            docs.sort(key=lambda d: int(d.get("band_index") or 0))
            rates[ya] = docs

    _clear_dir(cfg.rule_docs_dir)
    _clear_dir(cfg.rate_docs_dir)
    for ya, docs in rules.items():
        _write_year_file(cfg.rule_docs_dir, ya, docs)
    for ya, docs in rates.items():
        _write_year_file(cfg.rate_docs_dir, ya, docs)

    with _LOCK:
        _RULES_BY_YEAR.clear()
        _RULES_BY_YEAR.update(rules)
        _RATES_BY_YEAR.clear()
        _RATES_BY_YEAR.update(rates)

    years = sorted(set(rules) | set(rates))
    logger.info(
        "OE RAG index refreshed (years=%s, rules=%s, rates=%s)",
        len(years),
        sum(len(v) for v in rules.values()),
        sum(len(v) for v in rates.values()),
    )
    return {
        "years": years,
        "rule_count": sum(len(v) for v in rules.values()),
        "rate_count": sum(len(v) for v in rates.values()),
        "index_dir": str(cfg.index_dir),
    }


def load_index_from_disk(settings: OptimizationExplainableSettings | None = None) -> None:
    cfg = settings or get_oe_settings()
    rules: dict[str, list[dict[str, Any]]] = {}
    rates: dict[str, list[dict[str, Any]]] = {}
    if cfg.rule_docs_dir.is_dir():
        for path in cfg.rule_docs_dir.glob("*.json"):
            raw = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(raw, list):
                rules[path.stem] = [d for d in raw if isinstance(d, dict)]
    if cfg.rate_docs_dir.is_dir():
        for path in cfg.rate_docs_dir.glob("*.json"):
            raw = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(raw, list):
                rates[path.stem] = [d for d in raw if isinstance(d, dict)]
    with _LOCK:
        _RULES_BY_YEAR.clear()
        _RULES_BY_YEAR.update(rules)
        _RATES_BY_YEAR.clear()
        _RATES_BY_YEAR.update(rates)


def _ya_key(ya: str) -> tuple[int, int]:
    parts = str(ya).split("_")
    try:
        return (int(parts[0]), int(parts[1]) if len(parts) > 1 else 0)
    except (TypeError, ValueError):
        return (0, 0)


def _year_known(ya: str) -> bool:
    return ya in _RULES_BY_YEAR or ya in _RATES_BY_YEAR


def _earlier_years(ya: str, pool: dict[str, list[dict[str, Any]]]) -> list[str]:
    target = _ya_key(ya)
    return sorted(
        (other for other in pool if _ya_key(other) < target),
        key=_ya_key,
        reverse=True,
    )


def _select_reliefs(ya: str, exclude_source_doc_id: str | None) -> list[dict[str, Any]]:
    """Keep this year's rows, then fill missing compare_group_id from earlier years.

    Same idea as Adaptive Tax ``select_for_year``: dropping one act does not
    delete PDFs; remaining candidates for the group still apply.
    """
    current = list(_RULES_BY_YEAR.get(ya, []))
    skip = (exclude_source_doc_id or "").strip()
    if not skip:
        return current

    kept = [doc for doc in current if str(doc.get("source_doc_id") or "") != skip]
    kept_groups = {str(doc.get("compare_group_id") or "") for doc in kept}
    missing: set[str] = set()
    for doc in current:
        group = str(doc.get("compare_group_id") or "")
        if group and group not in kept_groups:
            missing.add(group)
    if not missing:
        return kept

    for group in sorted(missing):
        for earlier in _earlier_years(ya, _RULES_BY_YEAR):
            candidates = [
                doc
                for doc in _RULES_BY_YEAR.get(earlier, [])
                if str(doc.get("compare_group_id") or "") == group
                and str(doc.get("source_doc_id") or "") != skip
            ]
            if not candidates:
                continue
            candidates.sort(
                key=lambda doc: (int(doc.get("sort_order") or 0), str(doc.get("entry_id") or ""))
            )
            kept.append(candidates[0])
            break
    return kept


def _select_rates(ya: str, exclude_source_doc_id: str | None) -> list[dict[str, Any]]:
    current = list(_RATES_BY_YEAR.get(ya, []))
    skip = (exclude_source_doc_id or "").strip()
    if not skip:
        return current
    kept = [doc for doc in current if str(doc.get("source_doc_id") or "") != skip]
    if kept:
        return kept
    for earlier in _earlier_years(ya, _RATES_BY_YEAR):
        candidates = [
            doc
            for doc in _RATES_BY_YEAR.get(earlier, [])
            if str(doc.get("source_doc_id") or "") != skip
        ]
        if candidates:
            return candidates
    return []


def list_years() -> list[dict[str, Any]]:
    with _LOCK:
        years = sorted(set(_RULES_BY_YEAR) | set(_RATES_BY_YEAR), key=_ya_key)
        return [
            {
                "assessment_year": ya,
                "rule_count": len(_RULES_BY_YEAR.get(ya, [])),
                "rate_count": len(_RATES_BY_YEAR.get(ya, [])),
            }
            for ya in years
        ]


def acts_for_year(ya: str) -> list[dict[str, Any]] | None:
    with _LOCK:
        if not _year_known(ya):
            return None
        by_id: dict[str, dict[str, Any]] = {}
        for doc in _RULES_BY_YEAR.get(ya, []):
            source = str(doc.get("source_doc_id") or "").strip()
            if not source:
                continue
            rec = by_id.setdefault(
                source,
                {
                    "source_doc_id": source,
                    "title": str(doc.get("act_name") or source),
                    "relief_count": 0,
                    "rate_band_count": 0,
                },
            )
            rec["relief_count"] = int(rec["relief_count"]) + 1
            title = str(doc.get("act_name") or "").strip()
            if title:
                rec["title"] = title
        for doc in _RATES_BY_YEAR.get(ya, []):
            source = str(doc.get("source_doc_id") or "").strip()
            if not source:
                continue
            rec = by_id.setdefault(
                source,
                {
                    "source_doc_id": source,
                    "title": str(doc.get("act_name") or source),
                    "relief_count": 0,
                    "rate_band_count": 0,
                },
            )
            rec["rate_band_count"] = int(rec["rate_band_count"]) + 1
            if not rec.get("title") or rec["title"] == source:
                title = str(doc.get("act_name") or "").strip()
                if title:
                    rec["title"] = title
        return sorted(by_id.values(), key=lambda row: str(row.get("source_doc_id") or ""))


def reliefs_for_year(
    ya: str,
    exclude_source_doc_id: str | None = None,
) -> list[dict[str, Any]] | None:
    with _LOCK:
        if not _year_known(ya):
            return None
        return _select_reliefs(ya, exclude_source_doc_id)


def rates_for_year(
    ya: str,
    exclude_source_doc_id: str | None = None,
) -> list[dict[str, Any]] | None:
    with _LOCK:
        if not _year_known(ya):
            return None
        return _select_rates(ya, exclude_source_doc_id)


def ensure_index() -> dict[str, Any]:
    """Load existing index, refresh when empty or when catalogs changed on disk."""
    cfg = get_oe_settings()
    load_index_from_disk()
    with _LOCK:
        empty = not _RULES_BY_YEAR and not _RATES_BY_YEAR
    stale = _catalog_newer_than_index(cfg)
    if empty or stale:
        if stale and not empty:
            logger.info("OE catalog newer than RAG index — refreshing from approved/rates")
        return refresh_index(cfg)
    years = list_years()
    return {
        "years": [row["assessment_year"] for row in years],
        "rule_count": sum(row["rule_count"] for row in years),
        "rate_count": sum(row["rate_count"] for row in years),
        "loaded_from_disk": True,
    }
