"""Catalog-admin Step 6: Phase 5 review wrapper (not a second ledger)."""

from __future__ import annotations

import argparse
import hashlib
import json
import threading
from pathlib import Path
from typing import Any

from adaptive_tax_app.services.catalog_admin_store import (
    APPROVED_DIR,
    CatalogAdminPaths,
    catalog_admin_paths,
    load_job,
    now_iso,
)
from adaptive_tax_app.services.catalog_classify import (
    KIND_HUMAN_VALUES,
    classification_complete,
    load_proposed,
    save_proposed,
    unset_row_ids,
)
from adaptive_tax_app.services.catalog_duplicate import CatalogDuplicateError, p4, p4_accuracy, p5
from adaptive_tax_app.services.catalog_stage import (
    ENGINE_BINDING_KINDS,
    QUESTION_INPUT_KINDS,
    ensure_provision_attribution,
    set_engine_binding as stage_set_engine_binding,
    set_question_fields as stage_set_question_fields,
)
from backend.shared.config.settings import PROJECT_ROOT

_LEDGER_LOCK = threading.Lock()

ENGINE_YAS = frozenset({"2024_25", "2025_26"})
ENGINE_YEAR_NOTE = (
    "This will change the interview catalog estimate for YA {ya}. "
    "The verified calculation (official engine) is unchanged."
)
TAX_REDUCING_KINDS = frozenset(
    {
        "solar_panel_relief",
        "rent_relief",
        "senior_citizen_interest_relief",
        "qualifying_payments",
        "donations",
        "filing_line",
    }
)
RATE_KINDS = frozenset({"rate_band", "surcharge", "special_formula", "rule"})
SOLE_CHECK_LABEL = (
    "I have read the Act text and accept this rate without an independent check"
)
SOLE_CHECK_BANNER = (
    "No independent verification source exists for this year ΓÇö approval relies "
    "entirely on manual reading of the Act text."
)
# Phase 7 viva series ΓÇö the only known-table that can block promote this pass.
PERSONAL_RELIEF_KNOWN_CAPS: dict[str, int] = {
    "2018_19": 500_000,
    "2019_20": 500_000,
    "2020_21": 3_000_000,
    "2021_22": 3_000_000,
    "2022_23": 2_250_000,
    "2023_24": 1_200_000,
    "2024_25": 1_200_000,
    "2025_26": 1_800_000,
}

# Extractor paragraph slugs for Fifth Schedule 2(a). Live catalog key is personal_relief.
EXTRACT_PERSONAL_RELIEF_ALIASES = frozenset(
    {
        "fifth_schedule_paragraph_2_a",
        "fifth_schedule_2_a",
        "fifth_schedule_2a",
        "fifth_schedule_paragraph_2a",
    }
)


def tax_effect_copy(kind: str | None, *, component_id: str | None = None) -> str:
    if not kind:
        return "Calculator rule not chosen ΓÇö pick Step 1 before you can approve this row."
    if kind == "none":
        return (
            "Standard calculator rule saved. Tax uses the cap and the taxpayer's "
            "answers from Step 2 (personal relief, claim amounts, auto-applied caps)."
        )
    engines: list[str] = []
    if kind in TAX_REDUCING_KINDS:
        engines.append("official calculate() on 2024/25ΓÇô2025/26")
        engines.append("catalog estimate")
    extra = ""
    if kind == "filing_line":
        extra = f" component_id={component_id}" if component_id else " (component_id required)"
    joined = "; ".join(engines) if engines else "catalog estimate"
    return f"This relief WILL reduce calculated tax ({joined}).{extra}"


def _provisions_by_id(proposal: dict[str, Any]) -> dict[str, dict[str, Any]]:
    block = proposal.get("classification") or {}
    out: dict[str, dict[str, Any]] = {}
    for provision in block.get("provisions") or []:
        rid = str(provision.get("row_id") or "")
        if rid:
            out[rid] = ensure_provision_attribution(provision)
    return out


def _entry_id(row: dict[str, Any]) -> str:
    return str(row.get("entry_id") or row.get("row_id") or "")


def proposal_rows(proposal: dict[str, Any]) -> list[dict[str, Any]]:
    by_entry: dict[str, dict[str, Any]] = {}
    for section in proposal.get("sections") or []:
        section_key = str(section.get("section_key") or "")
        for row in section.get("rows") or []:
            merged = {**row, "section_key": row.get("section_key") or section_key}
            rid = _entry_id(merged)
            if rid:
                by_entry[rid] = merged
    rows = list(proposal.get("rows") or [])
    if not rows:
        return list(by_entry.values())
    out: list[dict[str, Any]] = []
    for row in rows:
        rid = _entry_id(row)
        extra = by_entry.get(rid) or {}
        out.append({**row, "section_key": row.get("section_key") or extra.get("section_key") or ""})
    return out


def ledger_row_id(row: dict[str, Any], source_doc_id: str) -> str:
    section_key = str(row.get("section_key") or "")
    payload = dict(row)
    payload.setdefault("row_kind", "relief")
    return p5().row_id_for(payload, source_doc_id, section_key)


def _with_ledger(paths: CatalogAdminPaths):
    mod = p5()

    class _Ctx:
        def __enter__(self) -> Any:
            _LEDGER_LOCK.acquire()
            self._ledger = mod.LEDGER_PATH
            self._extracted = mod.EXTRACTED_DIR
            self._review = mod.REVIEW_DIR
            mod.LEDGER_PATH = paths.ledger_path
            mod.EXTRACTED_DIR = paths.extracted_dir
            mod.REVIEW_DIR = paths.ledger_path.parent
            return mod

        def __exit__(self, *_exc: object) -> None:
            mod.LEDGER_PATH = self._ledger
            mod.EXTRACTED_DIR = self._extracted
            mod.REVIEW_DIR = self._review
            _LEDGER_LOCK.release()

    return _Ctx()


def _decision_for(mod: Any, hashed_id: str) -> dict[str, Any] | None:
    ledger = mod.load_ledger()
    raw = (ledger.get("decisions") or {}).get(hashed_id)
    return dict(raw) if isinstance(raw, dict) else None


def _is_relief(row: dict[str, Any]) -> bool:
    kind = str(row.get("row_kind") or "")
    return kind == "relief" or kind.startswith("qp_")


def _is_rate(row: dict[str, Any]) -> bool:
    return str(row.get("row_kind") or "") in RATE_KINDS


def _binding_kind(provision: dict[str, Any] | None) -> str | None:
    if not provision:
        return None
    binding = provision.get("engine_binding")
    if not isinstance(binding, dict):
        return None
    kind = str(binding.get("kind") or "").strip()
    return kind or None


def bindings_complete(proposal: dict[str, Any]) -> bool:
    by_id = _provisions_by_id(proposal)
    for row in proposal_rows(proposal):
        if not row.get("included") or not _is_relief(row):
            continue
        provision = by_id.get(_entry_id(row))
        kind = _binding_kind(provision)
        if not kind:
            return False
        if kind == "filing_line" and not str(
            (provision or {}).get("engine_binding", {}).get("component_id") or ""
        ).strip():
            return False
    return True


def _gate_ok(row: dict[str, Any]) -> bool:
    return bool(row.get("included"))


def _has_ontology_pack(ya: str) -> bool:
    if not ya:
        return False
    return p4_accuracy().load_ontology_pack(ya) is not None


def _sole_check(provision: dict[str, Any] | None) -> bool:
    if not provision:
        return True
    if provision.get("kind_human") == "NEW_YEAR" or provision.get("kind_suggested") == "NEW_YEAR":
        return True
    ya = str(provision.get("derived_assessment_year") or "")
    return not _has_ontology_pack(ya)


def _cap_int(value: Any) -> int | None:
    text = str(value or "").replace(",", "").strip()
    if text.isdigit():
        return int(text)
    try:
        return int(float(text))
    except (TypeError, ValueError):
        return None


def live_catalog_groups() -> tuple[set[str], dict[str, str]]:
    """Live approved compare_group_id set and display_name ΓåÆ group."""
    ids: set[str] = set()
    by_name: dict[str, str] = {}
    if not APPROVED_DIR.is_dir():
        return ids, by_name
    for path in APPROVED_DIR.glob("*.json"):
        data = json.loads(path.read_text(encoding="utf-8"))
        for entry in data.get("entries") or []:
            gid = str(entry.get("compare_group_id") or "").strip()
            if gid:
                ids.add(gid)
            name = str(entry.get("display_name") or "").strip().lower()
            if name and gid:
                by_name.setdefault(name, gid)
    return ids, by_name


def resolve_catalog_compare_group(
    row: dict[str, Any],
    provision: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Map extractor paragraph ids onto the live catalog group.

    Fifth Schedule 2(a) extracts as fifth_schedule_paragraph_2_a but the
    interview and approved year files key Personal Relief as personal_relief.
    """
    extract_id = str(row.get("compare_group_id") or "").strip()
    human = ""
    if provision:
        human = str(provision.get("compare_group_human") or "").strip()
    live_ids, by_name = live_catalog_groups()
    name = str(row.get("display_name") or "").strip().lower()
    baseline = str(row.get("baseline_compare_group_id") or "").strip()
    if human:
        chosen, reason = human, "reviewer"
    elif baseline and baseline in live_ids:
        chosen, reason = baseline, "baseline_compare_group_id"
    elif extract_id in live_ids:
        chosen, reason = extract_id, "extract_already_live"
    elif extract_id in EXTRACT_PERSONAL_RELIEF_ALIASES or name == "personal relief":
        chosen, reason = "personal_relief", "fifth_schedule_2_a_personal_relief"
    elif name and name in by_name:
        chosen, reason = by_name[name], "display_name"
    else:
        chosen, reason = extract_id, "extract"
    return {
        "extract_compare_group_id": extract_id,
        "catalog_compare_group_id": chosen,
        "compare_group_mapped": bool(extract_id and chosen and extract_id != chosen),
        "compare_group_map_reason": reason,
    }


def _section_extract_path(source_doc_id: str, section_key: str, root: CatalogAdminPaths) -> Path:
    safe_key = section_key.replace(" ", "_").lower()
    return root.extracted_dir / f"{source_doc_id}__{safe_key}.json"


def _resolve_proposal_pdf(proposal: dict[str, Any], root: CatalogAdminPaths) -> Path | None:
    job_id = str(proposal.get("job_id") or "")
    if job_id:
        try:
            job = load_job(job_id, root)
            storage = job.get("storage_path")
            if storage:
                path = Path(str(storage))
                if path.is_file():
                    return path
        except (OSError, ValueError, KeyError, json.JSONDecodeError):
            pass
    raw = proposal.get("pdf_path")
    if raw:
        path = Path(str(raw))
        if not path.is_absolute():
            path = PROJECT_ROOT / path
        if path.is_file():
            return path
    return None


def _cache_section_prose(path: Path, focus_prose: str) -> None:
    if not focus_prose or not path.is_file():
        return
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        prior = str(data.get("focus_prose") or "")
        if prior and len(prior) >= len(focus_prose):
            return
        data["focus_prose"] = focus_prose
        path.write_text(
            json.dumps(data, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
    except (OSError, json.JSONDecodeError, TypeError):
        return


def _section_act_prose(
    proposal: dict[str, Any],
    section_key: str,
    root: CatalogAdminPaths,
) -> str:
    sid = str(proposal.get("source_doc_id") or "")
    if not sid or not section_key:
        return ""

    for section in proposal.get("sections") or []:
        if str(section.get("section_key") or "") != section_key:
            continue
        prose = str(section.get("focus_prose") or "").strip()
        if prose:
            return prose

    path = _section_extract_path(sid, section_key, root)
    if path.is_file():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            prose = str(data.get("focus_prose") or "").strip()
            if prose and len(prose) >= 500:
                return prose
            focus_text = str(data.get("focus_text") or "")
            if focus_text:
                prose = p4().extract_section_prose(focus_text)
                if prose:
                    return prose
        except (OSError, json.JSONDecodeError):
            pass

    pdf_path = _resolve_proposal_pdf(proposal, root)
    if pdf_path is None:
        return ""
    try:
        extract = p4()
        act = extract.read_act_text(pdf_path)
        is_base = "amend" not in sid.lower()
        focus = extract.build_focus_window(act, section_key, is_base_act=is_base)
        if not focus:
            alt = section_key.replace(" ", "_").lower()
            focus = extract.build_focus_window(act, alt, is_base_act=is_base)
        prose = extract.extract_section_prose(focus)
        if prose:
            _cache_section_prose(path, prose)
        return prose
    except (OSError, ValueError, AttributeError):
        return ""


def _section_act_prose_cache(
    proposal: dict[str, Any],
    root: CatalogAdminPaths,
) -> dict[str, str]:
    keys: set[str] = set()
    for row in proposal_rows(proposal):
        if _is_rate(row):
            sk = str(row.get("section_key") or "")
            if sk:
                keys.add(sk)
    return {sk: _section_act_prose(proposal, sk, root) for sk in sorted(keys)}


def _is_table_quote_row(row: dict[str, Any]) -> bool:
    quote = str(row.get("quote") or "")
    return str(row.get("quote_source") or "") == "table_render" or "|" in quote


def build_review_row(
    row: dict[str, Any],
    *,
    proposal: dict[str, Any],
    provision: dict[str, Any] | None,
    decision: dict[str, Any] | None,
    section_prose_cache: dict[str, str] | None = None,
) -> dict[str, Any]:
    binding = (provision or {}).get("engine_binding") if provision else None
    kind = _binding_kind(provision)
    component_id = None
    if isinstance(binding, dict):
        component_id = binding.get("component_id")
    hashed = ledger_row_id(row, str(proposal.get("source_doc_id") or ""))
    reviewed_by = None
    if provision and isinstance(provision.get("provenance"), dict):
        reviewed_by = provision["provenance"].get("reviewed_by")
    if decision and not reviewed_by:
        reviewed_by = decision.get("reviewer")
    can_approve = _gate_ok(row)
    needs_binding = _is_relief(row) and bool(row.get("included"))
    if needs_binding and not kind:
        can_approve = False
    if row.get("included") and not (provision or {}).get("kind_human"):
        can_approve = False
    qf = (provision or {}).get("question_fields")
    display = (
        (qf.get("display_name") if isinstance(qf, dict) else None)
        or row.get("display_name")
        or row.get("band_label")
        or row.get("description")
        or row.get("rule_id")
        or (provision.get("display_name") if provision else None)
    )
    group = resolve_catalog_compare_group(row, provision)
    section_key = str(row.get("section_key") or "")
    section_act_prose = ""
    if str(row.get("row_kind") or "") == "rate_band":
        section_act_prose = (section_prose_cache or {}).get(section_key, "")
    return {
        "entry_id": _entry_id(row),
        "ledger_row_id": hashed,
        "row_kind": row.get("row_kind"),
        "display_name": display,
        "question_prompt": (qf.get("question_prompt") if isinstance(qf, dict) else None)
        or row.get("question_prompt")
        or "",
        "input_kind": (qf.get("input_kind") if isinstance(qf, dict) else None)
        or row.get("input_kind")
        or "notice",
        "help": (qf.get("help") if isinstance(qf, dict) else None) or row.get("help") or "",
        "question_fields": qf if isinstance(qf, dict) else None,
        "question_fields_set_by": (provision or {}).get("question_fields_set_by"),
        "question_fields_set_at": (provision or {}).get("question_fields_set_at"),
        "suggested_compare_group_id": group["extract_compare_group_id"],
        "description": row.get("description"),
        "value": row.get("value"),
        "cap_amount": row.get("cap_amount"),
        "rate_percent": row.get("rate_percent"),
        "lower": row.get("lower"),
        "upper": row.get("upper"),
        "effective_from": row.get("effective_from"),
        "section_ref": row.get("section_ref"),
        "compare_group_id": group["catalog_compare_group_id"] or row.get("compare_group_id"),
        "extract_compare_group_id": group["extract_compare_group_id"],
        "catalog_compare_group_id": group["catalog_compare_group_id"],
        "compare_group_mapped": group["compare_group_mapped"],
        "compare_group_map_reason": group["compare_group_map_reason"],
        "quote": row.get("quote"),
        "quote_source": row.get("quote_source"),
        "band_label": row.get("band_label"),
        "applies_to": row.get("applies_to"),
        "section_act_prose": section_act_prose or None,
        "quote_ok_full_doc": bool(row.get("quote_ok_full_doc")),
        "pass2_verbatim": bool(row.get("pass2_verbatim")),
        "included": bool(row.get("included")),
        "gate_ok": _gate_ok(row),
        "classification": provision,
        "engine_binding": binding,
        "engine_binding_set_by": (provision or {}).get("engine_binding_set_by"),
        "engine_binding_set_at": (provision or {}).get("engine_binding_set_at"),
        "tax_effect": (
            tax_effect_copy(kind, component_id=str(component_id) if component_id else None)
            if _is_relief(row)
            else None
        ),
        "decision_status": (decision or {}).get("status"),
        "reviewed_by": reviewed_by,
        "can_approve": can_approve,
        "approve_blocked_reason": (
            None
            if can_approve
            else (
                "Gate-fail rows cannot be approved ΓÇö request re-extract."
                if not _gate_ok(row)
                else "Set human classification first."
                if not (provision or {}).get("kind_human")
                else tax_effect_copy(None)
                if needs_binding and not kind
                else "Cannot approve."
            )
        ),
        "approve_label": SOLE_CHECK_LABEL if _is_rate(row) and _sole_check(provision) else "Approve row",
        "sole_check": _is_rate(row) and _sole_check(provision),
        "panel": "rate" if _is_rate(row) else "relief" if _is_relief(row) else "other",
    }


def _rate_ontology(proposal: dict[str, Any], rate_rows: list[dict[str, Any]]) -> dict[str, Any] | None:
    bands = [
        r
        for r in proposal_rows(proposal)
        if r.get("included") and str(r.get("row_kind") or "") == "rate_band"
    ]
    if not rate_rows and not bands:
        return None
    sole = any(r.get("sole_check") for r in rate_rows)
    yas = sorted(
        {
            str((r.get("classification") or {}).get("derived_assessment_year") or "")
            for r in rate_rows
            if (r.get("classification") or {}).get("derived_assessment_year")
        }
    )
    engine_update = [
        r
        for r in rate_rows
        if r.get("included")
        and not r.get("sole_check")
        and (r.get("classification") or {}).get("kind_human") == "UPDATE"
        and str((r.get("classification") or {}).get("derived_assessment_year") or "") in ENGINE_YAS
    ]
    diffs: list[dict[str, Any]] = []
    blocks = False
    if engine_update and bands:
        accuracy = p4_accuracy()
        for ya in sorted(
            {
                str((r.get("classification") or {}).get("derived_assessment_year") or "")
                for r in engine_update
            }
        ):
            pack = accuracy.load_ontology_pack(ya)
            ladder = {
                "bands": [
                    {
                        "lower": p5()._as_int(b.get("lower")),
                        "upper": p5()._as_int(b.get("upper")),
                        "rate": p5()._as_float(b.get("rate_percent")),
                    }
                    for b in sorted(bands, key=lambda item: p5()._as_int(item.get("lower")) or 0)
                    if p5()._as_int(b.get("lower")) is not None
                    and p5()._as_float(b.get("rate_percent")) is not None
                ]
            }
            if pack is None:
                sole = True
                continue
            result = accuracy.diff_against_ontology(ladder, pack)
            diffs.append({"assessment_year": ya, **result})
            if not result.get("match"):
                blocks = True
    return {
        "sole_check": sole,
        "banner": SOLE_CHECK_BANNER if sole else None,
        "derived_assessment_years": yas,
        "ontology_diffs": diffs,
        "ontology_blocks": blocks,
    }


def enrich_review(proposal: dict[str, Any], paths: CatalogAdminPaths) -> dict[str, Any]:
    sid = str(proposal.get("source_doc_id") or "")
    by_id = _provisions_by_id(proposal)
    section_prose_cache = _section_act_prose_cache(proposal, paths)
    with _with_ledger(paths) as mod:
        relief: list[dict[str, Any]] = []
        rates: list[dict[str, Any]] = []
        other: list[dict[str, Any]] = []
        for row in proposal_rows(proposal):
            hashed = ledger_row_id(row, sid)
            built = build_review_row(
                row,
                proposal=proposal,
                provision=by_id.get(_entry_id(row)),
                decision=_decision_for(mod, hashed),
                section_prose_cache=section_prose_cache,
            )
            if built["panel"] == "rate":
                rates.append(built)
            elif built["panel"] == "relief":
                relief.append(built)
            else:
                other.append(built)
    inert = [
        {
            "entry_id": r["entry_id"],
            "display_name": r.get("display_name"),
            "note": "interview-visible, tax-inert",
        }
        for r in relief
        if r.get("included") and _binding_kind(r.get("classification")) == "none"
    ]
    class_ok = classification_complete(proposal) and proposal.get("classification") is not None
    bind_ok = bindings_complete(proposal)
    included = [r for r in relief + rates if r.get("included")]
    decided_ok = (
        all(r.get("decision_status") in {"approved", "rejected"} for r in included)
        if included
        else True
    )
    rate_panel = _rate_ontology(proposal, rates)
    ontology_blocks = bool((rate_panel or {}).get("ontology_blocks"))
    status = str(proposal.get("promotion_status") or "")
    has_update = any(
        r.get("included") and (r.get("classification") or {}).get("kind_human") == "UPDATE"
        for r in relief + rates
    )
    has_new_year = any(
        r.get("included") and (r.get("classification") or {}).get("kind_human") == "NEW_YEAR"
        for r in relief + rates
    )
    from adaptive_tax_app.services.catalog_promote import NEW_YEAR_CONFIRM_COPY, suggested_new_years

    suggested = suggested_new_years(proposal)
    suggested_ya = suggested[0] if len(suggested) == 1 else None
    confirmed = bool(proposal.get("new_year_confirmed")) and str(
        proposal.get("proposed_for_assessment_year") or ""
    ) == (suggested_ya or "")
    new_year_promote_enabled = (
        class_ok
        and bind_ok
        and decided_ok
        and has_new_year
        and confirmed
        and not ontology_blocks
        and status != "promoted"
    )
    new_year_reasons: list[str] = []
    if has_new_year:
        if not suggested_ya:
            new_year_reasons.append(
                "NEW_YEAR rows need one derived assessment year before confirm."
                if not suggested
                else "NEW_YEAR rows disagree on YA (" + ", ".join(suggested) + ")."
            )
        elif not confirmed:
            new_year_reasons.append(NEW_YEAR_CONFIRM_COPY.format(new_year=suggested_ya))
        elif not decided_ok:
            new_year_reasons.append("Approve or reject every included row before promote.")
        elif status == "promoted":
            new_year_reasons.append("Already promoted.")
        else:
            new_year_reasons.append("Promote NEW YEAR via Phase 6 cmd_promote after confirm.")
    promote_enabled = (
        class_ok
        and bind_ok
        and decided_ok
        and has_update
        and not ontology_blocks
        and status not in {"promoted", "partially_promoted"}
    )
    reasons: list[str] = []
    if not class_ok:
        reasons.append("Every included row needs a human classification.")
    if not bind_ok:
        reasons.append("Every included relief needs an engine_binding (unset is not none).")
    if class_ok and bind_ok and not decided_ok:
        reasons.append("Approve or reject every included row before promote.")
    if not reasons:
        if status in {"promoted", "partially_promoted"}:
            reasons.append(
                "Already promoted."
                if status == "promoted"
                else "UPDATE already promoted ΓÇö remaining NEW_YEAR rows wait for Step 7b."
            )
        elif not has_update:
            reasons.append(
                "NEW_YEAR promote is Step 7b. This Step 7a path only promotes UPDATE rows."
            )
        elif ontology_blocks:
            reasons.append("Engine-year rate ontology mismatch blocks UPDATE.")
        else:
            reasons.append(
                "Run impact preview. Promote POST requires this fingerprint plus gap-acks."
            )
    return {
        "source_doc_id": sid,
        "proposal": proposal,
        "classification_complete": class_ok,
        "bindings_complete": bind_ok,
        "unset_row_ids": unset_row_ids(proposal),
        "tax_inert_rows": inert,
        "relief_rows": relief,
        "rate_rows": rates,
        "other_rows": other,
        "rate_panel": rate_panel,
        "engine_binding_kinds": sorted(ENGINE_BINDING_KINDS),
        "question_input_kinds": sorted(QUESTION_INPUT_KINDS),
        "promote_enabled": promote_enabled,
        "promote_blocked_reason": " ".join(reasons),
        "preview_ready": class_ok and bind_ok,
        "has_update_rows": has_update,
        "has_new_year_rows": has_new_year,
        "suggested_new_year": suggested_ya,
        "new_year_confirm_message": (
            NEW_YEAR_CONFIRM_COPY.format(new_year=suggested_ya) if suggested_ya else None
        ),
        "new_year_confirmed": confirmed,
        "new_year_promote_enabled": new_year_promote_enabled,
        "new_year_promote_blocked_reason": " ".join(new_year_reasons) if new_year_reasons else None,
        "promotion_status": status,
    }


def review_payload(source_doc_id: str, paths: CatalogAdminPaths | None = None) -> dict[str, Any]:
    root = paths or catalog_admin_paths()
    return enrich_review(load_proposed(source_doc_id, root), root)


def _find_row(proposal: dict[str, Any], row_id: str) -> dict[str, Any]:
    rid = (row_id or "").strip()
    for row in proposal_rows(proposal):
        if _entry_id(row) == rid:
            return row
    raise CatalogDuplicateError(f"Row {rid} is not on this proposal.")


def decide_row(
    source_doc_id: str,
    *,
    row_id: str,
    status: str,
    reviewer: str,
    reason: str | None = None,
    sole_check: bool = False,
    paths: CatalogAdminPaths | None = None,
) -> dict[str, Any]:
    """Approve / reject / flag via Phase 5 _record. Writes ledger reviewer only."""
    if status not in {"approved", "rejected", "needs_manual_verification"}:
        raise CatalogDuplicateError("status must be approved, rejected, or needs_manual_verification.")
    root = paths or catalog_admin_paths()
    proposal = load_proposed(source_doc_id, root)
    row = _find_row(proposal, row_id)
    if status == "approved" and not row.get("included"):
        raise CatalogDuplicateError(
            "Gate-fail rows cannot be approved. Request re-extract instead."
        )
    by_id = _provisions_by_id(proposal)
    provision = by_id.get(_entry_id(row))
    if status == "approved":
        if not provision or provision.get("kind_human") not in KIND_HUMAN_VALUES:
            raise CatalogDuplicateError("Set human classification before approve.")
        if _is_relief(row) and not _binding_kind(provision):
            raise CatalogDuplicateError(tax_effect_copy(None))
        if _binding_kind(provision) == "filing_line" and not str(
            (provision.get("engine_binding") or {}).get("component_id") or ""
        ).strip():
            raise CatalogDuplicateError("filing_line requires component_id.")
        if _is_rate(row) and _kind_human(provision) == "NEW_YEAR" and not sole_check:
            raise CatalogDuplicateError(
                "NEW_YEAR rate rows must be accepted via the sole-check control, "
                "not the routine relief approve."
            )
        if _is_rate(row) and _kind_human(provision) == "NEW_YEAR" and sole_check:
            provision["sole_check_ack"] = True
            provision["sole_check_ack_by"] = reviewer
            provision["sole_check_ack_at"] = now_iso()
    hashed = ledger_row_id(row, source_doc_id)
    staging = {
        **row,
        "row_id": hashed,
        "source_doc_id": source_doc_id,
        "section_key": row.get("section_key") or "",
        "entry_id": _entry_id(row),
    }
    args = argparse.Namespace(reviewer=reviewer, reason=reason, binding=None, component_id=None)
    resolved = resolve_catalog_compare_group(row, provision)
    overrides: dict[str, Any] | None = None
    catalog_group = str(resolved.get("catalog_compare_group_id") or "")
    if status == "approved" and catalog_group:
        # Phase 5 REVIEWER_SETTABLE: live catalog key, not the extractor paragraph slug.
        overrides = {"compare_group_id": catalog_group}
    root.ledger_path.parent.mkdir(parents=True, exist_ok=True)
    with _with_ledger(root) as mod:
        ledger = mod.load_ledger()
        mod._record(ledger, staging, status, args, overrides)
        mod.save_ledger(ledger)
    if provision is not None:
        provenance = provision.setdefault("provenance", {"reviewed_by": None, "reviewed_at": None})
        provenance["reviewed_by"] = reviewer
        provenance["reviewed_at"] = now_iso()
        save_proposed(proposal, root)
    return enrich_review(load_proposed(source_doc_id, root), root)


def set_row_engine_binding(
    source_doc_id: str,
    *,
    row_id: str,
    kind: str,
    reviewer: str,
    component_id: str | None = None,
    paths: CatalogAdminPaths | None = None,
) -> dict[str, Any]:
    root = paths or catalog_admin_paths()
    proposal = load_proposed(source_doc_id, root)
    by_id = _provisions_by_id(proposal)
    provision = by_id.get((row_id or "").strip())
    if provision is None:
        raise CatalogDuplicateError(f"Row {row_id} is not an included classified provision.")
    stage_set_engine_binding(
        provision, kind=kind, reviewer=reviewer, component_id=component_id
    )
    save_proposed(proposal, root)
    return enrich_review(proposal, root)


def set_row_question_fields(
    source_doc_id: str,
    *,
    row_id: str,
    display_name: str,
    question_prompt: str,
    input_kind: str,
    help_text: str,
    compare_group_id: str,
    reviewer: str,
    paths: CatalogAdminPaths | None = None,
) -> dict[str, Any]:
    """Auditor-edited taxpayer question. Caps and quotes stay on the extract row."""
    root = paths or catalog_admin_paths()
    proposal = load_proposed(source_doc_id, root)
    by_id = _provisions_by_id(proposal)
    provision = by_id.get((row_id or "").strip())
    if provision is None:
        raise CatalogDuplicateError(f"Row {row_id} is not an included classified provision.")
    stage_set_question_fields(
        provision,
        display_name=display_name,
        question_prompt=question_prompt,
        input_kind=input_kind,
        help_text=help_text,
        compare_group_id=compare_group_id,
        reviewer=reviewer,
    )
    save_proposed(proposal, root)
    return enrich_review(proposal, root)


def _commencements(paths: CatalogAdminPaths, source_doc_id: str) -> dict[str, str]:
    out = dict(p5().load_act_commencements())
    sidecar = paths.harvest_sidecar_dir / f"{source_doc_id}.json"
    if sidecar.is_file():
        data = json.loads(sidecar.read_text(encoding="utf-8"))
        for record in data.get("records") or []:
            sid = str(record.get("source_doc_id") or source_doc_id)
            iso = str(record.get("operation_date") or "")
            if sid and iso and (sid not in out or iso < out[sid]):
                out[sid] = iso
    return out


def engine_year_message(ya: str) -> str:
    return ENGINE_YEAR_NOTE.format(ya=ya)


def _kind_human(provision: dict[str, Any] | None) -> str | None:
    kind = str((provision or {}).get("kind_human") or "").strip()
    return kind if kind in KIND_HUMAN_VALUES else None


def _is_approved_update(
    row: dict[str, Any],
    *,
    provision: dict[str, Any] | None,
    decision: dict[str, Any] | None,
) -> bool:
    if not row.get("included"):
        return False
    if _kind_human(provision) != "UPDATE":
        return False
    return (decision or {}).get("status") == "approved"


def _candidate_from_catalog_entry(entry: dict[str, Any]) -> dict[str, Any]:
    prov = entry.get("provenance") or {}
    group = str(entry.get("compare_group_id") or "")
    return {
        "row_id": entry.get("entry_id"),
        "source_doc_id": entry.get("source_doc_id"),
        "compare_group_id": group,
        "cap_amount": entry.get("cap_amount"),
        "effective_from": prov.get("effective_from_stated") or prov.get("effective_from") or "",
        "effective_to": "",
        "row_kind": "relief",
        "display_name": entry.get("display_name"),
        "question_prompt": entry.get("question_prompt"),
        "sort_order": entry.get("sort_order", 100),
        "input_kind": entry.get("input_kind"),
        "help": entry.get("help") or "",
        "auto_applied": entry.get("auto_applied", False),
        "unit": entry.get("unit") or "lkr",
        "quote": entry.get("quote"),
        "section_ref": entry.get("section_ref"),
        "act_name": entry.get("act_name"),
        "act_title": entry.get("act_name"),
        "quote_ok_full_doc": prov.get("quote_ok_full_doc"),
        "pass2_verbatim": prov.get("pass2_verbatim"),
        "quote_source": prov.get("quote_source"),
        "extract_run_id": prov.get("extract_run_id"),
        "staging_path": prov.get("staging_path"),
        "_catalog_entry": entry,
        "_decision": {
            "status": "approved",
            "compare_group_id": group,
            "display_name": entry.get("display_name"),
            "question_prompt": entry.get("question_prompt"),
            "sort_order": entry.get("sort_order", 100),
            "input_kind": entry.get("input_kind"),
            "help": entry.get("help") or "",
            "auto_applied": entry.get("auto_applied", False),
            "engine_binding": entry.get("engine_binding") or {"kind": "none"},
            "reviewer": prov.get("reviewed_by") or "",
            "decided_at": prov.get("reviewed_at") or "",
        },
    }


def _approved_group_candidates(compare_group_id: str, approved_dir: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    if not approved_dir.is_dir():
        return rows
    for path in sorted(approved_dir.glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        for entry in data.get("entries") or []:
            if str(entry.get("compare_group_id") or "") != compare_group_id:
                continue
            key = (str(entry.get("source_doc_id") or ""), str(entry.get("entry_id") or ""))
            if key in seen:
                continue
            seen.add(key)
            rows.append(_candidate_from_catalog_entry(entry))
    return rows


def _prior_catalog_entry(compare_group_id: str, approved_dir: Path) -> dict[str, Any] | None:
    cands = _approved_group_candidates(compare_group_id, approved_dir)
    if not cands:
        return None
    return cands[0].get("_catalog_entry")


def _candidate_from_proposal_row(
    row: dict[str, Any],
    *,
    proposal: dict[str, Any],
    provision: dict[str, Any] | None,
    decision: dict[str, Any] | None,
    approved_dir: Path,
) -> dict[str, Any]:
    sid = str(proposal.get("source_doc_id") or "")
    resolved = resolve_catalog_compare_group(row, provision)
    group = str(resolved.get("catalog_compare_group_id") or "")
    hashed = ledger_row_id(row, sid)
    prior = _prior_catalog_entry(group, approved_dir) or {}
    binding = (provision or {}).get("engine_binding") if provision else None
    decided = dict(decision or {})
    decided["compare_group_id"] = group
    qf = (provision or {}).get("question_fields") if provision else None
    if not isinstance(qf, dict):
        qf = {}
    decided["display_name"] = (
        qf.get("display_name") or row.get("display_name") or prior.get("display_name") or ""
    )
    decided["question_prompt"] = (
        qf.get("question_prompt")
        or row.get("question_prompt")
        or prior.get("question_prompt")
        or ""
    )
    decided["sort_order"] = int(prior.get("sort_order", 100))
    decided["input_kind"] = (
        qf.get("input_kind") or row.get("input_kind") or prior.get("input_kind") or "notice"
    )
    decided["help"] = qf.get("help") or row.get("help") or prior.get("help") or ""
    decided["auto_applied"] = bool(prior.get("auto_applied", row.get("auto_applied", False)))
    decided["engine_binding"] = binding or {"kind": "none"}
    return {
        "row_id": hashed,
        "entry_id": _entry_id(row),
        "source_doc_id": sid,
        "compare_group_id": group,
        "cap_amount": row.get("cap_amount"),
        "effective_from": row.get("effective_from") or "",
        "effective_to": row.get("effective_to") or "",
        "row_kind": row.get("row_kind") or "relief",
        "display_name": decided["display_name"],
        "question_prompt": decided["question_prompt"],
        "sort_order": decided["sort_order"],
        "input_kind": decided["input_kind"],
        "help": decided["help"],
        "auto_applied": decided["auto_applied"],
        "unit": row.get("unit") or "lkr",
        "quote": row.get("quote"),
        "section_ref": row.get("section_ref"),
        "act_name": row.get("act_name"),
        "act_title": proposal.get("act_title") or row.get("act_name") or "",
        "quote_ok_full_doc": row.get("quote_ok_full_doc"),
        "pass2_verbatim": row.get("pass2_verbatim"),
        "quote_source": row.get("quote_source"),
        "extract_run_id": proposal.get("run_id") or row.get("extract_run_id"),
        "staging_path": row.get("staging_path") or "",
        "lower": row.get("lower"),
        "upper": row.get("upper"),
        "rate_percent": row.get("rate_percent"),
        "applies_to": row.get("applies_to") or "individual",
        "band_label": row.get("band_label"),
        "rule_kind": row.get("rule_kind"),
        "rule_id": row.get("rule_id"),
        "description": row.get("description"),
        "value": row.get("value"),
        "derived_assessment_year": (provision or {}).get("derived_assessment_year"),
        "_decision": decided,
    }


def union_relief_candidates(
    group: str,
    proposal: dict[str, Any],
    *,
    paths: CatalogAdminPaths,
    mod: Any,
) -> list[dict[str, Any]]:
    """Existing approved/extracted candidates + newly approved UPDATE rows."""
    seen: set[tuple[str, str]] = set()
    out: list[dict[str, Any]] = []

    def _add(cand: dict[str, Any]) -> None:
        key = (str(cand.get("source_doc_id") or ""), str(cand.get("row_id") or ""))
        if not key[0] and not key[1]:
            return
        if key in seen:
            return
        seen.add(key)
        out.append(cand)

    for cand in _approved_group_candidates(group, paths.approved_dir):
        _add(cand)
    try:
        staging = mod.load_staging_rows()
        ledger = mod.load_ledger()
        for row in mod.approved_rows(staging, ledger):
            decided = row.get("_decision") or {}
            gid = str(decided.get("compare_group_id") or row.get("compare_group_id") or "")
            if gid != group:
                continue
            _add(row)
    except (OSError, ValueError):
        pass
    by_id = _provisions_by_id(proposal)
    sid = str(proposal.get("source_doc_id") or "")
    for row in proposal_rows(proposal):
        if not _is_relief(row):
            continue
        provision = by_id.get(_entry_id(row))
        hashed = ledger_row_id(row, sid)
        decision = _decision_for(mod, hashed)
        if not _is_approved_update(row, provision=provision, decision=decision):
            continue
        resolved = resolve_catalog_compare_group(row, provision)
        if str(resolved.get("catalog_compare_group_id") or "") != group:
            continue
        _add(
            _candidate_from_proposal_row(
                row,
                proposal=proposal,
                provision=provision,
                decision=decision,
                approved_dir=paths.approved_dir,
            )
        )
    return out


def touched_update_groups(
    proposal: dict[str, Any],
    *,
    paths: CatalogAdminPaths,
    mod: Any,
) -> dict[str, set[str]]:
    """catalog compare_group_id ΓåÆ extractor ids, for approved UPDATE reliefs only."""
    by_id = _provisions_by_id(proposal)
    sid = str(proposal.get("source_doc_id") or "")
    extract_for_group: dict[str, set[str]] = {}
    for row in proposal_rows(proposal):
        if not _is_relief(row):
            continue
        provision = by_id.get(_entry_id(row))
        hashed = ledger_row_id(row, sid)
        decision = _decision_for(mod, hashed)
        if not _is_approved_update(row, provision=provision, decision=decision):
            continue
        resolved = resolve_catalog_compare_group(row, provision)
        group = str(resolved.get("catalog_compare_group_id") or "").strip()
        if not group:
            continue
        extract_id = str(resolved.get("extract_compare_group_id") or "")
        extract_for_group.setdefault(group, set())
        if extract_id:
            extract_for_group[group].add(extract_id)
    return extract_for_group


def live_assessment_years(approved_dir: Path, fallback: list[str]) -> list[str]:
    if not approved_dir.is_dir():
        return list(fallback)
    found = sorted(
        p.stem
        for p in approved_dir.glob("*.json")
        if p.stem[0:4].isdigit()
        and json.loads(p.read_text(encoding="utf-8")).get("entries") is not None
    )
    return found or list(fallback)


def _selection_key(item: dict[str, Any] | None) -> tuple[str, str, str]:
    if not item:
        return ("", "", "")
    return (
        str(item.get("source_doc_id") or ""),
        str(item.get("cap_amount") or ""),
        str(item.get("row_id") or item.get("entry_id") or ""),
    )


def _selection_summary(chosen: dict[str, Any] | None) -> dict[str, Any]:
    if not chosen:
        return {"source_doc_id": None, "cap_amount": None, "row_id": None}
    return {
        "source_doc_id": chosen.get("source_doc_id"),
        "cap_amount": chosen.get("cap_amount"),
        "row_id": chosen.get("row_id"),
    }


def preview_fingerprint(payload: dict[str, Any]) -> str:
    blob = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def _existing_year_stems(directory: Path) -> set[str]:
    if not directory.is_dir():
        return set()
    return {p.stem for p in directory.glob("*.json")}


def rule_update_target_years(
    proposal: dict[str, Any],
    *,
    paths: CatalogAdminPaths,
    mod: Any,
) -> list[str]:
    """Existing rates/{ya}.json that an approved UPDATE rule/surcharge would overlay.

    Uses the reviewer's derived_assessment_year (UPDATE of 2022_23 writes that
    file, not a new YA). Ladder rate_band rows are handled separately.
    """
    by_id = _provisions_by_id(proposal)
    sid = str(proposal.get("source_doc_id") or "")
    stems = _existing_year_stems(paths.rates_dir)
    out: set[str] = set()
    for row in proposal_rows(proposal):
        if not _is_rate(row) or str(row.get("row_kind") or "") == "rate_band":
            continue
        provision = by_id.get(_entry_id(row))
        decision = _decision_for(mod, ledger_row_id(row, sid))
        if not _is_approved_update(row, provision=provision, decision=decision):
            continue
        ya = str((provision or {}).get("derived_assessment_year") or "")
        if ya in stems:
            out.add(ya)
    return sorted(out)


def promote_preview(
    source_doc_id: str,
    paths: CatalogAdminPaths | None = None,
) -> dict[str, Any]:
    """Before/after select_for_year. Does not write approved/ or rates/."""
    root = paths or catalog_admin_paths()
    proposal = load_proposed(source_doc_id, root)
    review = enrich_review(proposal, root)
    if not review["preview_ready"]:
        raise CatalogDuplicateError(review["promote_blocked_reason"])
    commencements = _commencements(root, source_doc_id)
    with _with_ledger(root) as mod:
        yas = live_assessment_years(root.approved_dir, list(mod.SUPPORTED_YAS))
        extract_for_group = touched_update_groups(proposal, paths=root, mod=mod)
        groups: list[dict[str, Any]] = []
        for group in sorted(extract_for_group):
            before_cands = _approved_group_candidates(group, root.approved_dir)
            after_cands = union_relief_candidates(group, proposal, paths=root, mod=mod)
            before_sel = [
                {
                    "assessment_year": ya,
                    **_selection_summary(mod.select_for_year(before_cands, ya, commencements)),
                }
                for ya in yas
            ]
            after_sel = [
                {
                    "assessment_year": ya,
                    **_selection_summary(mod.select_for_year(after_cands, ya, commencements)),
                }
                for ya in yas
            ]
            known_ok = True
            known_note = None
            known_table = None
            if group == "personal_relief":
                known_table = mod.dry_run_personal_relief_table(after_cands, commencements)
                drift: list[str] = []
                for item in after_sel:
                    ya = str(item.get("assessment_year") or "")
                    expected = PERSONAL_RELIEF_KNOWN_CAPS.get(ya)
                    got = _cap_int(item.get("cap_amount"))
                    if expected is not None and got is not None and got != expected:
                        drift.append(f"{ya} expected {expected} got {got}")
                if drift:
                    known_ok = False
                    known_note = (
                        "personal_relief known-table drift ΓÇö "
                        + "; ".join(drift)
                        + " ΓÇö promote is blocked."
                    )
            else:
                known_note = "No known-table verification exists for this group."
            groups.append(
                {
                    "compare_group_id": group,
                    "extract_compare_group_ids": sorted(extract_for_group.get(group) or []),
                    "compare_group_mapped": any(
                        eid != group for eid in (extract_for_group.get(group) or set())
                    ),
                    "before": before_sel,
                    "after": after_sel,
                    "known_table": group == "personal_relief",
                    "known_table_ok": known_ok,
                    "known_table_detail": known_table,
                    "gap_banner": known_note if group != "personal_relief" or not known_ok else None,
                    "needs_gap_ack": group != "personal_relief",
                }
            )
    inert = [
        {
            "entry_id": r["entry_id"],
            "display_name": r.get("display_name"),
            "note": "interview-visible, tax-inert",
        }
        for r in review["relief_rows"]
        if r.get("included") and _binding_kind(r.get("classification")) == "none"
    ]
    rule_yas: list[str] = []
    with _with_ledger(root) as mod:
        rule_yas = rule_update_target_years(proposal, paths=root, mod=mod)
    if rule_yas:
        groups.append(
            {
                "compare_group_id": "rate_rules",
                "extract_compare_group_ids": [],
                "compare_group_mapped": False,
                "before": [
                    {
                        "assessment_year": ya,
                        "source_doc_id": None,
                        "cap_amount": None,
                        "row_id": "special_formulas",
                    }
                    for ya in rule_yas
                ],
                "after": [
                    {
                        "assessment_year": ya,
                        "source_doc_id": source_doc_id,
                        "cap_amount": None,
                        "row_id": "special_formulas",
                    }
                    for ya in rule_yas
                ],
                "known_table": False,
                "known_table_ok": True,
                "known_table_detail": None,
                "gap_banner": "No known-table verification exists for this group.",
                "needs_gap_ack": True,
            }
        )
    existing_approved = _existing_year_stems(root.approved_dir)
    write_approved = {
        ya
        for group in groups
        if group["compare_group_id"] != "rate_rules"
        for ya, before, after in zip(yas, group["before"], group["after"], strict=True)
        if before != after and ya in existing_approved
    }
    write_rates = set(rule_yas)
    write_keys = sorted(
        [f"approved/{ya}.json" for ya in sorted(write_approved)]
        + [f"rates/{ya}.json" for ya in sorted(write_rates)]
    )
    would_write = write_keys
    engine_notes = [
        {"assessment_year": ya, "message": engine_year_message(ya)}
        for ya in sorted(write_approved | write_rates)
        if ya in ENGINE_YAS
    ]
    frozen = sorted(
        f"{label}/{p.name}"
        for label, directory in (("approved", root.approved_dir), ("rates", root.rates_dir))
        for p in (list(directory.glob("*.json")) if directory.is_dir() else [])
        if f"{label}/{p.name}" not in set(write_keys)
    )
    fingerprint_input = {
        "source_doc_id": source_doc_id,
        "groups": [
            {
                "compare_group_id": g["compare_group_id"],
                "before": g["before"],
                "after": g["after"],
                "known_table_ok": g["known_table_ok"],
            }
            for g in groups
        ],
        "tax_inert_rows": inert,
        "classifications": [
            {
                "entry_id": r["entry_id"],
                "cap_amount": r.get("cap_amount"),
                "kind_human": (r.get("classification") or {}).get("kind_human"),
                "engine_binding": _binding_kind(r.get("classification")),
            }
            for r in review["relief_rows"] + review["rate_rows"]
            if r.get("included")
        ],
        "year_files_that_would_be_written": would_write,
    }
    return {
        "source_doc_id": source_doc_id,
        "groups": groups,
        "tax_inert_rows": inert,
        "year_files_that_would_be_written": would_write,
        "year_files_frozen": frozen,
        "engine_year_notes": engine_notes,
        "engine_year_note": " ".join(n["message"] for n in engine_notes) or None,
        "blocks_promote": any(g["known_table"] and not g["known_table_ok"] for g in groups)
        or bool((review.get("rate_panel") or {}).get("ontology_blocks")),
        "preview_fingerprint": preview_fingerprint(fingerprint_input),
        "rate_panel": review.get("rate_panel"),
        "needs_gap_ack_group_ids": [
            g["compare_group_id"] for g in groups if g.get("needs_gap_ack")
        ],
    }
