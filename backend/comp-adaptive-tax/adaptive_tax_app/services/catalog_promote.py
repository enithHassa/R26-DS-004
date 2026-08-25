"""Catalog-admin promote: UPDATE (7a) and NEW YEAR (7b), with Step 8 immutability.

Every year-file write goes through Phase 5 _write_year_file with a matching
content_sha256. Promotes start and end with Phase 6 snapshot_year_hashes /
assert_past_years_unchanged (skipped only when live seals already drift).
cmd_verify is the post-hoc check on the write set. Untouched years are not
opened for write. Phase 6 cmd_promote is used only for NEW YEAR (it still
write_text's the new YA; catalog-admin immediately reseals through
_write_year_file). UPDATE never calls Phase 5/6 cmd_promote.
"""

from __future__ import annotations

import hashlib
import io
import json
import logging
import threading
from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from types import SimpleNamespace

from adaptive_tax_app.services.catalog_admin_store import CatalogAdminPaths, catalog_admin_paths, now_iso
from adaptive_tax_app.services.catalog_classify import load_proposed, p1, save_proposed
from adaptive_tax_app.services.catalog_duplicate import (
    CatalogConflictError,
    CatalogDuplicateError,
    p5,
    p6,
)
from adaptive_tax_app.services.catalog_review import (
    ENGINE_YAS,
    _commencements,
    _is_approved_update,
    _is_rate,
    _provisions_by_id,
    _with_ledger,
    enrich_review,
    engine_year_message,
    live_assessment_years,
    promote_preview,
    proposal_rows,
    union_relief_candidates,
)

_PROMOTE_LOCK = threading.Lock()
logger = logging.getLogger(__name__)


def notify_oe_index_refresh() -> dict[str, Any]:
    """HTTP POST the Optimization and Explainable index. Never import adaptive_tax_app there."""
    import httpx

    from backend.shared.config.settings import settings

    base = (settings.COMP_OPTIMIZATION_EXPLAINABLE_URL or "").rstrip("/")
    if not base:
        return {"ok": False, "error": "COMP_OPTIMIZATION_EXPLAINABLE_URL is empty"}
    url = f"{base}/api/v1/index/refresh"
    try:
        with httpx.Client(timeout=30.0) as client:
            response = client.post(url)
        body: Any
        try:
            body = response.json()
        except ValueError:
            body = {"text": response.text[:500]}
        if response.is_success:
            logger.info(
                "OE index refresh ok (years=%s)",
                (body.get("years") if isinstance(body, dict) else None),
            )
            return {"ok": True, "url": url, "status_code": response.status_code, "body": body}
        logger.warning(
            "OE index refresh HTTP %s from %s: %s",
            response.status_code,
            url,
            body,
        )
        return {
            "ok": False,
            "url": url,
            "status_code": response.status_code,
            "error": str(body),
        }
    except httpx.HTTPError as exc:
        logger.warning(
            "OE index refresh failed (%s): is Optimization and Explainable running on :8008?",
            exc,
        )
        return {"ok": False, "url": url, "error": str(exc)}


def _with_year_dirs(paths: CatalogAdminPaths):
    phase1 = p1()
    phase5 = p5()
    watcher = p6()

    class _Ctx:
        def __enter__(self) -> tuple[Any, Any, Any]:
            self._p1_approved = phase1.APPROVED_DIR
            self._p1_rates = phase1.RATES_DIR
            self._p1_out = phase1.OUT_ROOT
            self._p5_approved = phase5.APPROVED_DIR
            self._p5_rates = phase5.RATES_DIR
            self._p6_approved = watcher.APPROVED_DIR
            self._p6_rates = watcher.RATES_DIR
            self._p6_proposed = watcher.PROPOSED_DIR
            self._p6_baseline = watcher.HASH_BASELINE_PATH
            self._p6_snap = watcher.snapshot_year_hashes
            phase1.APPROVED_DIR = paths.approved_dir
            phase1.RATES_DIR = paths.rates_dir
            phase1.OUT_ROOT = paths.approved_dir.parent
            phase5.APPROVED_DIR = paths.approved_dir
            phase5.RATES_DIR = paths.rates_dir
            watcher.APPROVED_DIR = paths.approved_dir
            watcher.RATES_DIR = paths.rates_dir
            watcher.PROPOSED_DIR = paths.proposed_dir
            watcher.HASH_BASELINE_PATH = paths.ledger_path.parent / "catalog_admin_hash_baseline.json"
            watcher._catalog_admin_real_snapshot = self._p6_snap
            watcher.snapshot_year_hashes = lambda: _snapshot_year_files(paths)
            return phase1, phase5, watcher

        def __exit__(self, *_exc: object) -> None:
            phase1.APPROVED_DIR = self._p1_approved
            phase1.RATES_DIR = self._p1_rates
            phase1.OUT_ROOT = self._p1_out
            phase5.APPROVED_DIR = self._p5_approved
            phase5.RATES_DIR = self._p5_rates
            watcher.APPROVED_DIR = self._p6_approved
            watcher.RATES_DIR = self._p6_rates
            watcher.PROPOSED_DIR = self._p6_proposed
            watcher.HASH_BASELINE_PATH = self._p6_baseline
            watcher.snapshot_year_hashes = self._p6_snap

    return _Ctx()


def _snapshot_year_files(paths: CatalogAdminPaths) -> dict[str, str]:
    """Whole-file hashes. Pre-existing content_sha256 drift must not block UPDATE."""
    out: dict[str, str] = {}
    for label, directory in (("approved", paths.approved_dir), ("rates", paths.rates_dir)):
        if not directory.is_dir():
            continue
        for path in sorted(directory.glob("*.json")):
            out[f"{label}/{path.name}"] = hashlib.sha256(path.read_bytes()).hexdigest()
    return out


def _assert_frozen_unchanged(baseline: dict[str, str], paths: CatalogAdminPaths) -> list[str]:
    current = _snapshot_year_files(paths)
    problems: list[str] = []
    for key, expected in baseline.items():
        actual = current.get(key)
        if actual is None:
            problems.append(f"{key} missing after promote")
        elif actual != expected:
            problems.append(f"{key} hash changed ({expected[:12]}... -> {actual[:12]}...)")
    return problems


def _backup_paths(paths: list[Path]) -> dict[Path, bytes | None]:
    return {path: (path.read_bytes() if path.is_file() else None) for path in paths}


def _restore_backups(backups: dict[Path, bytes | None]) -> None:
    for path, data in backups.items():
        if data is None:
            path.unlink(missing_ok=True)
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)


def _load_year(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _replace_group_entry(
    entries: list[dict[str, Any]],
    group: str,
    new_entry: dict[str, Any],
) -> list[dict[str, Any]]:
    out = [dict(e) for e in entries if str(e.get("compare_group_id") or "") != group]
    out.append(new_entry)
    out.sort(key=lambda e: (int(e.get("sort_order", 100)), str(e.get("compare_group_id") or "")))
    return out


def _build_entry(mod: Any, chosen: dict[str, Any], commencements: dict[str, str]) -> dict[str, Any]:
    catalog = chosen.get("_catalog_entry")
    if isinstance(catalog, dict) and catalog.get("compare_group_id"):
        return dict(catalog)
    return mod.build_approved_entry(chosen, commencements)


def _approved_update_rate_rows(
    proposal: dict[str, Any],
    *,
    paths: CatalogAdminPaths,
    mod: Any,
) -> list[dict[str, Any]]:
    from adaptive_tax_app.services.catalog_review import _candidate_from_proposal_row, _entry_id

    by_id = _provisions_by_id(proposal)
    sid = str(proposal.get("source_doc_id") or "")
    out: list[dict[str, Any]] = []
    for row in proposal_rows(proposal):
        if not _is_rate(row):
            continue
        provision = by_id.get(_entry_id(row))
        decision = _decision_for_row(mod, row, sid)
        if not _is_approved_update(row, provision=provision, decision=decision):
            continue
        out.append(
            _candidate_from_proposal_row(
                row,
                proposal=proposal,
                provision=provision,
                decision=decision,
                approved_dir=paths.approved_dir,
            )
        )
    return out


def _decision_for_row(mod: Any, row: dict[str, Any], source_doc_id: str) -> dict[str, Any] | None:
    from adaptive_tax_app.services.catalog_review import _decision_for, ledger_row_id

    return _decision_for(mod, ledger_row_id(row, source_doc_id))


def _band_signature(payload: dict[str, Any]) -> tuple[Any, ...]:
    return tuple(
        (
            band.get("lower"),
            band.get("upper"),
            band.get("rate_percent"),
            band.get("source_doc_id"),
        )
        for band in payload.get("bands") or []
    )


def _planned_rate_writes(
    phase5: Any,
    *,
    paths: CatalogAdminPaths,
    new_rows: list[dict[str, Any]],
    commencements: dict[str, str],
    run_id: str,
    source_doc_id: str,
    reviewer: str,
    only_years: set[str] | None = None,
) -> list[tuple[Path, dict[str, Any], str]]:
    if not paths.rates_dir.is_dir():
        return []
    existing_rows: list[dict[str, Any]] = []
    for path in sorted(paths.rates_dir.glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        prov = data.get("provenance") or {}
        effective = str(prov.get("ladder_effective_from") or "")
        for band in data.get("bands") or []:
            existing_rows.append(
                {
                    "row_kind": "rate_band",
                    "applies_to": "individual",
                    "lower": band.get("lower"),
                    "upper": band.get("upper"),
                    "rate_percent": band.get("rate_percent"),
                    "band_label": band.get("band_label"),
                    "source_doc_id": band.get("source_doc_id"),
                    "effective_from": effective or band.get("effective_from") or "",
                    "section_ref": band.get("section_ref"),
                    "quote": band.get("quote"),
                    "act_name": band.get("act_name"),
                    "act_title": band.get("act_name"),
                    "quote_source": band.get("quote_source"),
                }
            )
    live = existing_rows + new_rows
    ladders = phase5.build_ladders(live, commencements)
    planned: list[tuple[Path, dict[str, Any], str]] = []
    for path in sorted(paths.rates_dir.glob("*.json")):
        ya = path.stem
        if only_years is not None and ya not in only_years:
            continue
        existing = json.loads(path.read_text(encoding="utf-8"))
        start = phase5.ya_start(ya)
        ladder = None
        for candidate in sorted(ladders, key=lambda item: item["effective_from"] or ""):
            raw = candidate.get("effective_from") or ""
            if not raw:
                continue
            try:
                when = datetime.strptime(raw, "%Y-%m-%d").date()
            except ValueError:
                continue
            if when <= start:
                ladder = candidate
        if ladder is None:
            continue
        bands = [
            {
                "band_index": idx + 1,
                "lower": phase5._as_int(band["lower"]),
                "upper": phase5._as_int(band.get("upper")),
                "rate_percent": phase5._as_float(band["rate_percent"]),
                "band_label": band.get("band_label", ""),
                "act_name": phase5.display_act_name(band),
                "act_name_extracted": band.get("act_name", ""),
                "section_ref": band.get("section_ref", ""),
                "quote": band.get("quote", ""),
                "source_doc_id": band["source_doc_id"],
                "quote_source": band.get("quote_source", ""),
            }
            for idx, band in enumerate(ladder["bands"])
        ]
        payload = dict(existing)
        payload["bands"] = bands
        payload["needs_manual_verification"] = True
        payload["promoted_at"] = now_iso()
        payload["promotion_run"] = run_id
        payload["promotion_source"] = "catalog_admin_update"
        payload["watcher_source_doc_id"] = source_doc_id
        payload["provenance"] = {
            **(existing.get("provenance") or {}),
            "ladder_source_doc_id": ladder["source_doc_id"],
            "ladder_effective_from": ladder["effective_from"],
            "reviewed_by": reviewer,
        }
        payload["content_sha256"] = phase5.canonical_sha256(payload)
        if _band_signature(payload) == _band_signature(existing) and ya not in ENGINE_YAS:
            # Same slabs — skip unless we still need a source_doc_id swap on engine years
            if (existing.get("provenance") or {}).get("ladder_source_doc_id") == ladder[
                "source_doc_id"
            ]:
                continue
        if _band_signature(payload) == _band_signature(existing) and (
            existing.get("provenance") or {}
        ).get("ladder_source_doc_id") == ladder["source_doc_id"]:
            continue
        planned.append((path, payload, f"rates/{ya}.json"))
    return planned


def _formula_key(item: dict[str, Any]) -> tuple[str, str, str]:
    return (
        str(item.get("quote") or ""),
        str(item.get("value") or ""),
        str(item.get("description") or ""),
    )


def _planned_rule_writes(
    phase5: Any,
    *,
    paths: CatalogAdminPaths,
    new_rows: list[dict[str, Any]],
    run_id: str,
    source_doc_id: str,
    reviewer: str,
    only_years: set[str] | None = None,
) -> list[tuple[Path, dict[str, Any], str]]:
    planned: list[tuple[Path, dict[str, Any], str]] = []
    for row in new_rows:
        if str(row.get("row_kind") or "") == "rate_band":
            continue
        ya = str(row.get("derived_assessment_year") or "")
        if only_years is not None and ya not in only_years:
            continue
        path = paths.rates_dir / f"{ya}.json"
        if not ya or not path.is_file():
            continue
        existing = json.loads(path.read_text(encoding="utf-8"))
        payload_row = phase5._rule_payload({**row, "source_doc_id": source_doc_id})
        if not payload_row.get("rule_kind"):
            payload_row["rule_kind"] = (
                "surcharge" if row.get("row_kind") == "surcharge" else "rate_rule"
            )
        if not payload_row.get("description"):
            payload_row["description"] = str(row.get("display_name") or "")
        bucket = "surcharges" if payload_row.get("rule_kind") == "surcharge" else "special_formulas"
        current = list(existing.get(bucket) or [])
        key = _formula_key(payload_row)
        if any(_formula_key(item) == key and item.get("source_doc_id") == source_doc_id for item in current):
            continue
        replaced = False
        merged: list[dict[str, Any]] = []
        for item in current:
            if _formula_key(item) == key:
                merged.append(payload_row)
                replaced = True
            else:
                merged.append(item)
        if not replaced:
            merged.append(payload_row)
        payload = dict(existing)
        payload[bucket] = merged
        payload["needs_manual_verification"] = True
        payload["promoted_at"] = now_iso()
        payload["promotion_run"] = run_id
        payload["promotion_source"] = "catalog_admin_update"
        payload["watcher_source_doc_id"] = source_doc_id
        payload["provenance"] = {
            **(existing.get("provenance") or {}),
            "reviewed_by": reviewer,
        }
        payload["content_sha256"] = phase5.canonical_sha256(payload)
        planned.append((path, payload, f"rates/{ya}.json"))
    return planned


def _merge_planned(
    items: list[tuple[Path, dict[str, Any], str]],
    phase5: Any,
) -> list[tuple[Path, dict[str, Any], str]]:
    by_key: dict[str, tuple[Path, dict[str, Any], str]] = {}
    for path, payload, key in items:
        prior = by_key.get(key)
        if prior is None:
            by_key[key] = (path, payload, key)
            continue
        merged = dict(prior[1])
        for field in ("special_formulas", "surcharges", "bands", "provenance"):
            if field in payload:
                merged[field] = payload[field]
        merged["content_sha256"] = phase5.canonical_sha256(merged)
        by_key[key] = (path, merged, key)
    return list(by_key.values())


def _write_year_file(mod: Any, path: Path, payload: dict[str, Any]) -> None:
    """The only catalog-admin path that may write approved/ or rates/ year files."""
    sealed = dict(payload)
    sealed["content_sha256"] = mod.canonical_sha256(sealed)
    try:
        mod._write_year_file(path, sealed, False)
    except SystemExit as exc:
        raise CatalogDuplicateError(str(exc)) from exc


def _seal_existing_year_file(phase5: Any, path: Path) -> None:
    """Re-write an existing year file through Phase 5 _write_year_file (adds/checks seal)."""
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["content_sha256"] = phase5.canonical_sha256(payload)
    _write_year_file(phase5, path, payload)


def _stamp_new_year_promotion_source(
    phase5: Any,
    paths: CatalogAdminPaths,
    *,
    ya: str,
    source_doc_id: str,
) -> None:
    """Phase 6 cmd_promote stamps phase6_watcher; mark catalog-admin NEW_YEAR for OE indexing."""
    for directory in (paths.approved_dir, paths.rates_dir):
        path = directory / f"{ya}.json"
        if not path.is_file():
            continue
        payload = json.loads(path.read_text(encoding="utf-8"))
        payload["promotion_source"] = "catalog_admin_new_year"
        payload["watcher_source_doc_id"] = source_doc_id
        _write_year_file(phase5, path, payload)


def _phase6_snapshot(watcher: Any, _paths: CatalogAdminPaths) -> dict[str, str] | None:
    """Call Phase 6 snapshot_year_hashes. None means pre-existing seal drift."""
    real = getattr(watcher, "_catalog_admin_real_snapshot", None)
    if real is None:
        return None
    patched = watcher.snapshot_year_hashes
    watcher.snapshot_year_hashes = real
    try:
        return real()
    except SystemExit:
        return None
    finally:
        watcher.snapshot_year_hashes = patched


def _phase6_assert_frozen(
    watcher: Any,
    start_seals: dict[str, str] | None,
    write_set: set[str],
) -> list[str]:
    if start_seals is None:
        return []
    frozen = {k: v for k, v in start_seals.items() if k not in write_set}
    real = getattr(watcher, "_catalog_admin_real_snapshot", None)
    if real is None:
        return []
    patched = watcher.snapshot_year_hashes
    watcher.snapshot_year_hashes = real
    try:
        return watcher.assert_past_years_unchanged(frozen)
    except SystemExit as exc:
        return [str(exc)]
    finally:
        watcher.snapshot_year_hashes = patched


def _verify_written_seals(phase5: Any, paths: CatalogAdminPaths, written: list[str]) -> None:
    """Every catalog-admin write must carry a matching content_sha256. Then cmd_verify."""
    problems: list[str] = []
    for key in written:
        label, name = key.split("/", 1)
        directory = paths.approved_dir if label == "approved" else paths.rates_dir
        path = directory / name
        if not path.is_file():
            problems.append(f"{key} missing after promote")
            continue
        payload = json.loads(path.read_text(encoding="utf-8"))
        recorded = payload.get("content_sha256")
        if not recorded:
            problems.append(f"{key} missing content_sha256")
        elif recorded != phase5.canonical_sha256(payload):
            problems.append(f"{key} content_sha256 mismatch")
    buf = io.StringIO()
    try:
        with redirect_stdout(buf), redirect_stderr(buf):
            phase5.cmd_verify(SimpleNamespace())
    except ValueError as exc:
        # Work-dir extracts sit outside REPO_ROOT; Phase 5 load_staging_rows uses relative_to.
        # Written-file seals above remain the hard check.
        if "not in the subpath" not in str(exc).lower() and "relative_to" not in str(exc):
            raise
    else:
        for line in buf.getvalue().splitlines():
            if "edited after promotion" not in line.lower() and "hash mismatch" not in line.lower():
                continue
            if any(key in line for key in written):
                problems.append(line.strip())
    if problems:
        raise CatalogDuplicateError(
            "Immutability cmd_verify failed: " + "; ".join(problems)
        )


def promote_update(
    source_doc_id: str,
    *,
    reviewer: str,
    preview_fingerprint: str,
    acknowledged_group_ids: list[str] | None = None,
    paths: CatalogAdminPaths | None = None,
) -> dict[str, Any]:
    """Promote UPDATE rows into existing year files. Does not call cmd_promote."""
    root = paths or catalog_admin_paths()
    with _PROMOTE_LOCK:
        return _promote_update_locked(
            source_doc_id,
            reviewer=reviewer,
            preview_fingerprint=preview_fingerprint,
            acknowledged_group_ids=list(acknowledged_group_ids or []),
            paths=root,
        )


def _promote_update_locked(
    source_doc_id: str,
    *,
    reviewer: str,
    preview_fingerprint: str,
    acknowledged_group_ids: list[str],
    paths: CatalogAdminPaths,
) -> dict[str, Any]:
    proposal = load_proposed(source_doc_id, paths)
    review = enrich_review(proposal, paths)
    if review.get("promotion_status") in {"promoted", "partially_promoted"}:
        raise CatalogDuplicateError(review["promote_blocked_reason"])
    if not review["promote_enabled"]:
        raise CatalogDuplicateError(review["promote_blocked_reason"])

    preview = promote_preview(source_doc_id, paths)
    expected = str(preview.get("preview_fingerprint") or "")
    if not preview_fingerprint or preview_fingerprint != expected:
        raise CatalogConflictError(
            "preview_fingerprint is stale. Re-run impact preview and acknowledge again."
        )
    if preview.get("blocks_promote"):
        raise CatalogDuplicateError(
            "Promote is blocked: personal_relief known-table drift or engine-year "
            "rate ontology mismatch."
        )
    needed = set(preview.get("needs_gap_ack_group_ids") or [])
    acked = {str(g) for g in acknowledged_group_ids}
    missing = sorted(needed - acked)
    if missing:
        raise CatalogDuplicateError(
            "Acknowledge groups with no known-table (bound to this fingerprint): "
            + ", ".join(missing)
        )

    commencements = _commencements(paths, source_doc_id)
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    written: list[str] = []
    engine_notes: list[dict[str, str]] = []
    status = "promoted"

    with _with_ledger(paths) as mod, _with_year_dirs(paths) as (_phase1, phase5, watcher):
        yas = live_assessment_years(paths.approved_dir, list(mod.SUPPORTED_YAS))
        start_seals = _phase6_snapshot(watcher, paths)
        full_snapshot = _snapshot_year_files(paths)
        changed_by_ya: dict[str, list[str]] = {}
        for group_preview in preview["groups"]:
            group = str(group_preview["compare_group_id"])
            if group == "rate_rules":
                continue
            for ya, before, after in zip(
                yas, group_preview["before"], group_preview["after"], strict=True
            ):
                if before == after:
                    continue
                if not (paths.approved_dir / f"{ya}.json").is_file():
                    continue
                changed_by_ya.setdefault(ya, []).append(group)

        planned: list[tuple[Path, dict[str, Any], str]] = []
        for ya, groups_changed in changed_by_ya.items():
            approved_path = paths.approved_dir / f"{ya}.json"
            existing = _load_year(approved_path)
            entries = list(existing.get("entries") or [])
            for group in groups_changed:
                after_cands = union_relief_candidates(group, proposal, paths=paths, mod=mod)
                chosen = mod.select_for_year(after_cands, ya, commencements)
                if chosen is None:
                    continue
                entries = _replace_group_entry(
                    entries, group, _build_entry(mod, chosen, commencements)
                )
            payload = dict(existing)
            payload["entries"] = entries
            payload["entry_count"] = len(entries)
            payload["phase1_empty_skeleton"] = False
            payload["promoted_at"] = now_iso()
            payload["promotion_run"] = run_id
            payload["promotion_source"] = "catalog_admin_update"
            payload["watcher_source_doc_id"] = source_doc_id
            payload["notes"] = (
                "Catalog-admin UPDATE. select_for_year (Rule 1b → 1 → 2) for touched "
                "compare_groups only. Untouched groups copied; Phase 5 cmd_promote was "
                "not called. Official calculate() is unchanged."
            )
            payload["content_sha256"] = phase5.canonical_sha256(payload)
            planned.append((approved_path, payload, f"approved/{ya}.json"))

        rate_rows = _approved_update_rate_rows(proposal, paths=paths, mod=mod)
        if rate_rows:
            if (review.get("rate_panel") or {}).get("ontology_blocks"):
                raise CatalogDuplicateError(
                    "Engine-year rate ontology mismatch blocks UPDATE of "
                    "2024_25 / 2025_26 ladders."
                )
            planned.extend(
                _merge_planned(
                    list(
                        _planned_rate_writes(
                            phase5,
                            paths=paths,
                            new_rows=rate_rows,
                            commencements=commencements,
                            run_id=run_id,
                            source_doc_id=source_doc_id,
                            reviewer=reviewer,
                        )
                    )
                    + list(
                        _planned_rule_writes(
                            phase5,
                            paths=paths,
                            new_rows=rate_rows,
                            run_id=run_id,
                            source_doc_id=source_doc_id,
                            reviewer=reviewer,
                        )
                    ),
                    phase5,
                )
            )

        write_set = {key for _path, _payload, key in planned}
        frozen_baseline = {k: v for k, v in full_snapshot.items() if k not in write_set}
        pre_problems = _assert_frozen_unchanged(frozen_baseline, paths)
        if pre_problems:
            raise CatalogDuplicateError(
                "Immutability pre-check failed: " + "; ".join(pre_problems)
            )
        pre_seals = _phase6_assert_frozen(watcher, start_seals, write_set)
        if pre_seals:
            raise CatalogDuplicateError(
                "Phase 6 snapshot pre-check failed: " + "; ".join(pre_seals)
            )

        write_paths = [path for path, _payload, _key in planned]
        backups = _backup_paths(write_paths)
        try:
            for path, payload, key in planned:
                _write_year_file(phase5, path, payload)
                written.append(key)
                ya = path.stem
                if ya in ENGINE_YAS:
                    engine_notes.append(
                        {"assessment_year": ya, "message": engine_year_message(ya)}
                    )
            post_problems = _assert_frozen_unchanged(frozen_baseline, paths)
            if post_problems:
                raise CatalogDuplicateError(
                    "Immutability post-check failed; writes rolled back: "
                    + "; ".join(post_problems)
                )
            seal_problems = _phase6_assert_frozen(watcher, start_seals, write_set)
            if seal_problems:
                raise CatalogDuplicateError(
                    "Phase 6 assert_past_years_unchanged failed; writes rolled back: "
                    + "; ".join(seal_problems)
                )
            _verify_written_seals(phase5, paths, written)
            has_new_year = bool(review.get("has_new_year_rows"))
            status = "partially_promoted" if has_new_year else "promoted"
            proposal["promotion_status"] = status
            proposal["promoted_at"] = now_iso()
            proposal["promoted_by"] = reviewer
            proposal["promotion_run"] = run_id
            proposal["promoted_kind"] = "UPDATE"
            proposal["promoted_year_files"] = written
            proposal["corpus_manifest_updated"] = False
            save_proposed(proposal, paths)
            ledger = mod.load_ledger()
            ledger.setdefault("promotions", []).append(
                {
                    "run_id": run_id,
                    "at": now_iso(),
                    "by": reviewer,
                    "kind": "UPDATE",
                    "source_doc_id": source_doc_id,
                    "written": written,
                }
            )
            mod.save_ledger(ledger)
        except Exception:
            _restore_backups(backups)
            raise

    return {
        **enrich_review(load_proposed(source_doc_id, paths), paths),
        "promotion": {
            "status": status,
            "run_id": run_id,
            "written": written,
            "year_files_frozen": preview.get("year_files_frozen"),
            "engine_year_notes": engine_notes,
            "engine_year_note": " ".join(n["message"] for n in engine_notes) or None,
            "corpus_manifest_updated": False,
            "tax_inert_rows": preview.get("tax_inert_rows"),
            "index_refresh": notify_oe_index_refresh(),
        },
    }


NEW_YEAR_CONFIRM_COPY = (
    "This Act's commencement suggests YA {new_year} — confirm before creating a new year file."
)


def suggested_new_years(proposal: dict[str, Any]) -> list[str]:
    from adaptive_tax_app.services.catalog_review import _entry_id, _kind_human, _provisions_by_id

    by_id = _provisions_by_id(proposal)
    yas: set[str] = set()
    for row in proposal_rows(proposal):
        if not row.get("included"):
            continue
        provision = by_id.get(_entry_id(row))
        if _kind_human(provision) != "NEW_YEAR":
            continue
        ya = str((provision or {}).get("derived_assessment_year") or "")
        if ya:
            yas.add(ya)
    return sorted(yas)


def confirm_new_year(
    source_doc_id: str,
    *,
    reviewer: str,
    assessment_year: str,
    confirmed: bool,
    paths: CatalogAdminPaths | None = None,
) -> dict[str, Any]:
    """Hard-stop: write_empty_skeletons + Phase 6 set-year. Does not promote."""
    if not confirmed:
        raise CatalogDuplicateError("Confirm is required before creating a new year file.")
    ya = (assessment_year or "").strip()
    root = paths or catalog_admin_paths()
    proposal = load_proposed(source_doc_id, root)
    review = enrich_review(proposal, root)
    if not review.get("has_new_year_rows"):
        raise CatalogDuplicateError("Classify at least one included row as NEW_YEAR before confirm.")
    suggested = suggested_new_years(proposal)
    if not suggested:
        raise CatalogDuplicateError(
            "NEW_YEAR rows need a derived assessment year before confirm."
        )
    if len(suggested) > 1:
        raise CatalogDuplicateError(
            "NEW_YEAR rows disagree on YA (" + ", ".join(suggested) + ")."
        )
    if ya != suggested[0]:
        raise CatalogDuplicateError(
            NEW_YEAR_CONFIRM_COPY.format(new_year=suggested[0])
            + f" Confirm YA must be {suggested[0]}."
        )
    if proposal.get("new_year_confirmed") and proposal.get("proposed_for_assessment_year") == ya:
        return enrich_review(proposal, root)

    approved_path = root.approved_dir / f"{ya}.json"
    rates_path = root.rates_dir / f"{ya}.json"
    if approved_path.is_file():
        existing = json.loads(approved_path.read_text(encoding="utf-8"))
        if existing.get("entries"):
            raise CatalogDuplicateError(
                f"approved/{ya}.json already has live entries. "
                "The watcher may only create a NEW year file, never rewrite one. Use UPDATE."
            )

    with _with_year_dirs(root) as (phase1, phase5, watcher):
        if not approved_path.is_file() or not rates_path.is_file():
            try:
                phase1.write_empty_skeletons([ya], dry_run=False)
            except ValueError as exc:
                if not approved_path.is_file() or not rates_path.is_file():
                    raise CatalogDuplicateError(str(exc)) from exc
        if approved_path.is_file():
            existing = json.loads(approved_path.read_text(encoding="utf-8"))
            if existing.get("entries"):
                raise CatalogDuplicateError(
                    f"approved/{ya}.json already has live entries. Use UPDATE."
                )
        for path in (approved_path, rates_path):
            if path.is_file():
                _seal_existing_year_file(phase5, path)
        args = SimpleNamespace(source_doc_id=source_doc_id, ya=ya, reviewer=reviewer)
        err = io.StringIO()
        out = io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            try:
                rc = watcher.cmd_set_year(args)
            except ValueError as exc:
                # Work-dir paths are outside the repo; prints use relative_to(REPO_ROOT).
                if "relative_to" in str(exc) or "not in the subpath" in str(exc).lower():
                    rc = 0
                else:
                    raise
        if rc != 0:
            raise CatalogDuplicateError(
                (err.getvalue() or out.getvalue() or f"cmd_set_year failed ({rc})").strip()
            )

    proposal = load_proposed(source_doc_id, root)
    if proposal.get("proposed_for_assessment_year") != ya:
        # cmd_set_year print crashed after a failed save — apply the same fields here.
        proposal["proposed_for_assessment_year"] = ya
        proposal["proposed_year_set_at"] = now_iso()
        proposal["proposed_year_set_by"] = reviewer
    proposal["new_year_confirmed"] = True
    save_proposed(proposal, root)
    return enrich_review(load_proposed(source_doc_id, root), root)


def _quote_gated_new_year_relief(row: dict[str, Any], provision: dict[str, Any] | None) -> bool:
    from adaptive_tax_app.services.catalog_review import _is_relief, _kind_human

    if not row.get("included") or not _is_relief(row):
        return False
    if _kind_human(provision) != "NEW_YEAR":
        return False
    return bool(row.get("quote_ok_full_doc")) and bool(row.get("pass2_verbatim"))


def _approved_new_year_rate_rows(
    proposal: dict[str, Any],
    *,
    paths: CatalogAdminPaths,
    mod: Any,
) -> list[dict[str, Any]]:
    from adaptive_tax_app.services.catalog_review import (
        _candidate_from_proposal_row,
        _entry_id,
        _kind_human,
    )

    by_id = _provisions_by_id(proposal)
    sid = str(proposal.get("source_doc_id") or "")
    out: list[dict[str, Any]] = []
    for row in proposal_rows(proposal):
        if not _is_rate(row) or not row.get("included"):
            continue
        provision = by_id.get(_entry_id(row))
        decision = _decision_for_row(mod, row, sid)
        if _kind_human(provision) != "NEW_YEAR":
            continue
        if (decision or {}).get("status") != "approved":
            continue
        if not provision or not provision.get("sole_check_ack"):
            raise CatalogDuplicateError(
                "NEW_YEAR rate rows must be accepted via the sole-check control, "
                "not the routine relief approve."
            )
        out.append(
            _candidate_from_proposal_row(
                row,
                proposal=proposal,
                provision=provision,
                decision=decision,
                approved_dir=paths.approved_dir,
            )
        )
    return out


def promote_new_year(
    source_doc_id: str,
    *,
    reviewer: str,
    paths: CatalogAdminPaths | None = None,
) -> dict[str, Any]:
    """NEW_YEAR populate via Phase 6 cmd_promote. Does not extend taxpayer year lists."""
    root = paths or catalog_admin_paths()
    with _PROMOTE_LOCK:
        return _promote_new_year_locked(source_doc_id, reviewer=reviewer, paths=root)


def _promote_new_year_locked(
    source_doc_id: str,
    *,
    reviewer: str,
    paths: CatalogAdminPaths,
) -> dict[str, Any]:
    from adaptive_tax_app.services.catalog_review import (
        _entry_id,
        _kind_human,
        _provisions_by_id,
    )

    proposal = load_proposed(source_doc_id, paths)
    review = enrich_review(proposal, paths)
    ya = str(proposal.get("proposed_for_assessment_year") or "")
    if not proposal.get("new_year_confirmed") or not ya:
        raise CatalogDuplicateError(
            NEW_YEAR_CONFIRM_COPY.format(new_year=suggested_new_years(proposal)[0] if suggested_new_years(proposal) else "{new_year}")
        )
    if review.get("promotion_status") == "promoted":
        raise CatalogDuplicateError("Already promoted.")
    if not review.get("classification_complete") or not review.get("bindings_complete"):
        raise CatalogDuplicateError(review["promote_blocked_reason"])
    included = [
        r
        for r in (review.get("relief_rows") or []) + (review.get("rate_rows") or [])
        if r.get("included")
    ]
    pending = [r for r in included if r.get("decision_status") not in {"approved", "rejected"}]
    if pending:
        raise CatalogDuplicateError("Approve or reject every included row before promote.")

    write_set = {f"approved/{ya}.json", f"rates/{ya}.json"}
    frozen_before = _snapshot_year_files(paths)
    for key in write_set:
        frozen_before.pop(key, None)

    by_id = _provisions_by_id(proposal)
    included_flags: dict[str, bool] = {}
    for row in proposal_rows(proposal):
        eid = _entry_id(row)
        included_flags[eid] = bool(row.get("included"))
        provision = by_id.get(eid)
        row["included"] = _quote_gated_new_year_relief(row, provision)
    save_proposed(proposal, paths)

    written = [f"approved/{ya}.json", f"rates/{ya}.json"]
    try:
        with _with_year_dirs(paths) as (_phase1, phase5, watcher):
            start_seals = _phase6_snapshot(watcher, paths)
            pre_seals = _phase6_assert_frozen(watcher, start_seals, write_set)
            if pre_seals:
                raise CatalogDuplicateError(
                    "Phase 6 snapshot pre-check failed: " + "; ".join(pre_seals)
                )
            seed = {k: v for k, v in _snapshot_year_files(paths).items() if k not in written}
            watcher.write_immutable_baseline(seed, note=f"catalog-admin 7b before {ya}")
            args = SimpleNamespace(source_doc_id=source_doc_id, reviewer=reviewer, dry_run=False)
            err = io.StringIO()
            out = io.StringIO()
            with redirect_stdout(out), redirect_stderr(err):
                rc = watcher.cmd_promote(args)
            if rc != 0:
                raise CatalogDuplicateError(
                    (err.getvalue() or out.getvalue() or f"Phase 6 cmd_promote failed ({rc})").strip()
                )

            for path in (paths.approved_dir / f"{ya}.json", paths.rates_dir / f"{ya}.json"):
                if path.is_file():
                    _seal_existing_year_file(phase5, path)

            proposal = load_proposed(source_doc_id, paths)
            for row in proposal_rows(proposal):
                eid = _entry_id(row)
                if eid in included_flags:
                    row["included"] = included_flags[eid]
            with _with_ledger(paths) as mod:
                rate_rows = _approved_new_year_rate_rows(proposal, paths=paths, mod=mod)
                if rate_rows:
                    planned = _merge_planned(
                        list(
                            _planned_rate_writes(
                                phase5,
                                paths=paths,
                                new_rows=rate_rows,
                                commencements=_commencements(paths, source_doc_id),
                                run_id=str(proposal.get("promotion_run") or ""),
                                source_doc_id=source_doc_id,
                                reviewer=reviewer,
                                only_years={ya},
                            )
                        )
                        + list(
                            _planned_rule_writes(
                                phase5,
                                paths=paths,
                                new_rows=rate_rows,
                                run_id=str(proposal.get("promotion_run") or ""),
                                source_doc_id=source_doc_id,
                                reviewer=reviewer,
                                only_years={ya},
                            )
                        ),
                        phase5,
                    )
                    backups = _backup_paths([path for path, _payload, _key in planned])
                    try:
                        for path, payload, key in planned:
                            payload["needs_manual_verification"] = True
                            _write_year_file(phase5, path, payload)
                            if key not in written:
                                written.append(key)
                    except Exception:
                        _restore_backups(backups)
                        raise

            post = _assert_frozen_unchanged(frozen_before, paths)
            if post:
                raise CatalogDuplicateError(
                    "Immutability post-check failed: " + "; ".join(post)
                )
            seal_problems = _phase6_assert_frozen(watcher, start_seals, set(written))
            if seal_problems:
                raise CatalogDuplicateError(
                    "Phase 6 assert_past_years_unchanged failed: "
                    + "; ".join(seal_problems)
                )
            _verify_written_seals(phase5, paths, written)
            _stamp_new_year_promotion_source(
                phase5,
                paths,
                ya=ya,
                source_doc_id=source_doc_id,
            )

            proposal["promoted_kind"] = "NEW_YEAR"
            proposal["promoted_year_files"] = written
            proposal["corpus_manifest_updated"] = False
            has_update = bool(review.get("has_update_rows"))
            already_update = str(proposal.get("promotion_status") or "") in {
                "promoted",
                "partially_promoted",
            }
            if has_update and not already_update:
                proposal["promotion_status"] = "partially_promoted"
            else:
                proposal["promotion_status"] = "promoted"
            save_proposed(proposal, paths)
    except Exception:
        proposal = load_proposed(source_doc_id, paths)
        for row in proposal_rows(proposal):
            eid = _entry_id(row)
            if eid in included_flags:
                row["included"] = included_flags[eid]
        save_proposed(proposal, paths)
        raise

    rates_path = paths.rates_dir / f"{ya}.json"
    if rates_path.is_file():
        rates = json.loads(rates_path.read_text(encoding="utf-8"))
        if rates.get("needs_manual_verification") is not True:
            raise CatalogDuplicateError("NEW_YEAR rates must keep needs_manual_verification true.")

    return {
        **enrich_review(load_proposed(source_doc_id, paths), paths),
        "promotion": {
            "status": proposal.get("promotion_status"),
            "kind": "NEW_YEAR",
            "written": written,
            "assessment_year": ya,
            "corpus_manifest_updated": False,
            "index_refresh": notify_oe_index_refresh(),
        },
    }
