"""Catalog-admin Step 5: stage proposed/{id}.json only, via Phase 6 save_proposed.

Never writes approved/, rates/, or corpus_manifest.json. Attribution fields are
independent: a later action must not overwrite an earlier trail.
"""

from __future__ import annotations

import re
import threading
from pathlib import Path
from typing import Any

from adaptive_tax_app.services.catalog_admin_store import (
    CatalogAdminPaths,
    catalog_admin_paths,
    now_iso,
)
from adaptive_tax_app.services.catalog_duplicate import CatalogDuplicateError, p6

_SAVE_LOCK = threading.Lock()

ENGINE_BINDING_KINDS = frozenset(
    {
        "none",
        "solar_panel_relief",
        "rent_relief",
        "senior_citizen_interest_relief",
        "qualifying_payments",
        "donations",
        "filing_line",
    }
)

EMPTY_PROVENANCE = {"reviewed_by": None, "reviewed_at": None}

QUESTION_INPUT_KINDS = frozenset({"notice", "yes_no_amount", "amount", "boolean"})
_COMPARE_GROUP_RE = re.compile(r"^[a-z][a-z0-9_]{1,80}$")


def normalize_act_identity(raw: Any) -> dict[str, str] | None:
    if not isinstance(raw, dict) or not raw:
        return None
    source = str(raw.get("parsed_from") or raw.get("source") or "")
    return {
        "act_no": str(raw.get("act_no") or ""),
        "act_year": str(raw.get("act_year") or ""),
        "label": str(raw.get("label") or ""),
        "source": str(raw.get("source") or source),
        "parsed_from": source,
        "quote": str(raw.get("quote") or ""),
    }


def ensure_provision_attribution(provision: dict[str, Any]) -> dict[str, Any]:
    """Additive defaults. Never clobber names already written."""
    provision.setdefault("kind_human", None)
    provision.setdefault("kind_set_by", None)
    provision.setdefault("kind_set_at", None)
    provision.setdefault("engine_binding", None)
    provision.setdefault("engine_binding_set_by", None)
    provision.setdefault("engine_binding_set_at", None)
    provision.setdefault("compare_group_human", None)
    provision.setdefault("question_fields", None)
    provision.setdefault("question_fields_set_by", None)
    provision.setdefault("question_fields_set_at", None)
    provenance = provision.get("provenance")
    if not isinstance(provenance, dict):
        provision["provenance"] = dict(EMPTY_PROVENANCE)
    else:
        provenance.setdefault("reviewed_by", None)
        provenance.setdefault("reviewed_at", None)
    return provision


def apply_staging_schema(
    proposal: dict[str, Any],
    *,
    job: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Additive Phase 6 proposal fields. Does not write approved/ or rates/."""
    job = job or {}
    if proposal.get("text_sha256") in (None, ""):
        proposal["text_sha256"] = job.get("text_sha256")
    if proposal.get("tables_sha256") in (None, ""):
        proposal["tables_sha256"] = job.get("tables_sha256")
    if not proposal.get("job_id"):
        proposal["job_id"] = job.get("id")
    identity = normalize_act_identity(proposal.get("act_identity") or job.get("act_identity"))
    if identity is not None:
        proposal["act_identity"] = identity
    proposal.setdefault(
        "duplicate_check",
        {
            "outcome": "clear",
            "corpus_hit": job.get("matched_source_doc_id"),
            "proposed_hit": None,
        },
    )
    proposal.setdefault("proposed_for_assessment_year", None)
    proposal.setdefault("proposed_year_set_by", None)
    proposal.setdefault("proposed_year_set_at", None)
    block = proposal.get("classification")
    if isinstance(block, dict):
        for provision in block.get("provisions") or []:
            if isinstance(provision, dict):
                ensure_provision_attribution(provision)
    return proposal


def copy_human_attribution(prior: dict[str, Any], provision: dict[str, Any]) -> None:
    """Keep independent trails across harvest refresh. Copy only fields that were set."""
    if prior.get("kind_human") not in (None, ""):
        provision["kind_human"] = prior.get("kind_human")
        provision["kind_set_by"] = prior.get("kind_set_by")
        provision["kind_set_at"] = prior.get("kind_set_at")
    if prior.get("engine_binding_set_by"):
        provision["engine_binding"] = prior.get("engine_binding")
        provision["engine_binding_set_by"] = prior.get("engine_binding_set_by")
        provision["engine_binding_set_at"] = prior.get("engine_binding_set_at")
    if prior.get("question_fields_set_by"):
        provision["question_fields"] = prior.get("question_fields")
        provision["question_fields_set_by"] = prior.get("question_fields_set_by")
        provision["question_fields_set_at"] = prior.get("question_fields_set_at")
        if isinstance(prior.get("question_fields"), dict):
            group = str(prior["question_fields"].get("compare_group_id") or "").strip()
            if group:
                provision["compare_group_human"] = group
    old_prov = prior.get("provenance") or {}
    if isinstance(old_prov, dict) and old_prov.get("reviewed_by"):
        provision["provenance"] = {
            "reviewed_by": old_prov.get("reviewed_by"),
            "reviewed_at": old_prov.get("reviewed_at"),
        }


def save_staged_proposal(
    proposal: dict[str, Any],
    paths: CatalogAdminPaths | None = None,
) -> Path:
    """Write only proposed/{id}.json by calling Phase 6 save_proposed."""
    root = paths or catalog_admin_paths()
    apply_staging_schema(proposal)
    watcher = p6()
    with _SAVE_LOCK:
        previous = watcher.PROPOSED_DIR
        try:
            watcher.PROPOSED_DIR = root.proposed_dir
            return watcher.save_proposed(proposal)
        finally:
            watcher.PROPOSED_DIR = previous


def set_engine_binding(
    provision: dict[str, Any],
    *,
    kind: str,
    reviewer: str,
    component_id: str | None = None,
) -> dict[str, Any]:
    """Write engine_binding_* only. Does not touch kind_set_* or provenance."""
    binding_kind = (kind or "").strip()
    if binding_kind not in ENGINE_BINDING_KINDS:
        raise CatalogDuplicateError(
            "engine_binding.kind must be one of: " + ", ".join(sorted(ENGINE_BINDING_KINDS))
        )
    if binding_kind == "filing_line" and not (component_id or "").strip():
        raise CatalogDuplicateError("filing_line requires component_id.")
    binding: dict[str, Any] = {"kind": binding_kind}
    if binding_kind == "filing_line":
        binding["component_id"] = (component_id or "").strip()
    provision["engine_binding"] = binding
    provision["engine_binding_set_by"] = reviewer
    provision["engine_binding_set_at"] = now_iso()
    return provision


def set_question_fields(
    provision: dict[str, Any],
    *,
    display_name: str,
    question_prompt: str,
    input_kind: str,
    help_text: str,
    compare_group_id: str,
    reviewer: str,
) -> dict[str, Any]:
    """Auditor-edited taxpayer UX. Never writes cap_amount or quote."""
    name = (display_name or "").strip()
    prompt = (question_prompt or "").strip()
    kind = (input_kind or "").strip()
    group = (compare_group_id or "").strip()
    help_value = (help_text or "").strip()
    if not name:
        raise CatalogDuplicateError("display_name is required.")
    if not prompt:
        raise CatalogDuplicateError("question_prompt is required.")
    if kind not in QUESTION_INPUT_KINDS:
        raise CatalogDuplicateError(
            "input_kind must be one of: " + ", ".join(sorted(QUESTION_INPUT_KINDS))
        )
    if not group or _COMPARE_GROUP_RE.match(group) is None:
        raise CatalogDuplicateError(
            "compare_group_id must be snake_case (e.g. personal_relief)."
        )
    provision["question_fields"] = {
        "display_name": name,
        "question_prompt": prompt,
        "input_kind": kind,
        "help": help_value,
        "compare_group_id": group,
    }
    provision["question_fields_set_by"] = reviewer
    provision["question_fields_set_at"] = now_iso()
    provision["compare_group_human"] = group
    return provision


def set_proposed_year(
    proposal: dict[str, Any],
    *,
    assessment_year: str,
    reviewer: str,
) -> dict[str, Any]:
    """Write proposed_year_set_* only. Does not touch classification or engine binding."""
    ya = (assessment_year or "").strip()
    if not ya:
        raise CatalogDuplicateError("assessment_year is required.")
    proposal["proposed_for_assessment_year"] = ya
    proposal["proposed_year_set_by"] = reviewer
    proposal["proposed_year_set_at"] = now_iso()
    return proposal
