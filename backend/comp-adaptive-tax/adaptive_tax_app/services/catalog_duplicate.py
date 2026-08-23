"""Hash-first duplicate detection for catalog-admin Add New Act (before Pass 1).

Cheap PDF parse only: Phase 4 ``read_act_text`` + ``normalize_for_match``.
Path authority is ``confirm_pdf_paths`` / ``manifest_index``. This module never
rewrites ``corpus_manifest.json``.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import re
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from adaptive_tax_app.services.catalog_admin_store import (
    IN_FLIGHT_STATUSES,
    CatalogAdminPaths,
    catalog_admin_paths,
    list_jobs,
    new_job_id,
    now_iso,
    save_job,
)
from adaptive_tax_app.services.storage import sanitize_filename, sha256_hex, validate_pdf_bytes
from backend.shared.config.settings import PROJECT_ROOT

PHASE4_SCRIPT = PROJECT_ROOT / "scripts" / "relief_interview_phase4_extract.py"
PHASE4_ACCURACY_SCRIPT = PROJECT_ROOT / "scripts" / "relief_interview_phase4_accuracy.py"
PHASE5_SCRIPT = PROJECT_ROOT / "scripts" / "relief_interview_phase5_review.py"
PHASE6_SCRIPT = PROJECT_ROOT / "scripts" / "relief_interview_phase6_watcher.py"

DuplicateCase = Literal["a", "b", "b2", "d", "none", "prior_failed"]
MatchKind = Literal["text_hash", "filename", "pdf_sha256", ""]

# Running-header / short-title identity (same Act, No. X of YYYY shape as Phase 4).
_ACT_IDENTITY_RE = re.compile(
    r"(?ix)"
    r"Inland\s+Revenue(?:\s*\(Amendment\))?\s+"
    r"Act,?\s*No\.?\s*(\d+)\s+of\s+(\d{4})"
)
_CITED_AS_RE = re.compile(
    r"(?ix)"
    r"(?:may\s+be\s+cited\s+as|This\s+Act\s+may\s+be\s+cited\s+as)"
    r".{0,200}?"
    r"Act,?\s*No\.?\s*(\d+)\s+of\s+(\d{4})"
)
_FILENAME_IDENTITY_RE = re.compile(
    r"(?ix)(?:Act[_\s.]*No\.?[_\s.]*)(\d+)[-_ ]+(\d{4})"
)
_TITLE_NO_YEAR_RE = re.compile(
    r"(?ix)Act\s+No\.?\s*0*(\d+)\s+of\s+(\d{4})"
)

INDEX_SPEC = "1.0.0"
IDENTITY_PAGES = 8


class CatalogDuplicateError(ValueError):
    """Upload cannot be identity-checked (empty, not a PDF, unreadable)."""


class CatalogConflictError(CatalogDuplicateError):
    """Stale preview_fingerprint or concurrent catalog edit (HTTP 409)."""


def _load_module(path: Path, name: str) -> Any:
    cached = sys.modules.get(name)
    if cached is not None and getattr(cached, "__file__", None) == str(path):
        return cached
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def p4() -> Any:
    return _load_module(PHASE4_SCRIPT, "relief_interview_phase4_extract")


def p4_accuracy() -> Any:
    return _load_module(PHASE4_ACCURACY_SCRIPT, "relief_interview_phase4_accuracy")


def p5() -> Any:
    return _load_module(PHASE5_SCRIPT, "relief_interview_phase5_review")


def p6() -> Any:
    return _load_module(PHASE6_SCRIPT, "relief_interview_phase6_watcher")


@dataclass(frozen=True)
class ActIdentity:
    act_no: str
    act_year: str
    label: str
    source: str
    parsed_from: str = ""
    quote: str = ""

    def as_dict(self) -> dict[str, str]:
        payload = asdict(self)
        if not payload.get("parsed_from"):
            payload["parsed_from"] = payload.get("source") or ""
        return payload


@dataclass
class DuplicateDecision:
    case: DuplicateCase
    message: str
    match_kind: MatchKind = ""
    text_sha256: str = ""
    tables_sha256: str = ""
    pdf_sha256: str = ""
    filename: str = ""
    act_identity: ActIdentity | None = None
    matched_source_doc_id: str | None = None
    suggested_source_doc_id: str | None = None
    extracted_on: str | None = None
    uploaded_on: str | None = None
    review_path: str | None = None
    job_id: str | None = None
    job_path: str | None = None
    warnings: list[str] = field(default_factory=list)
    index_stale: bool = False
    actions: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        if self.act_identity is not None:
            payload["act_identity"] = self.act_identity.as_dict()
        return payload


def normalize_act_no(raw: str) -> str:
    digits = re.sub(r"\D", "", raw or "")
    if not digits:
        return ""
    return f"{int(digits):02d}"


def format_act_label(act_no: str, act_year: str) -> str:
    if not act_no or not act_year:
        return ""
    return f"Act No. {normalize_act_no(act_no)} of {act_year}"


def parse_act_identity(text: str, *, filename: str = "") -> ActIdentity | None:
    """Parse Act No/year from PDF title/header/short-title, then filename."""
    blob = text or ""
    for pattern, source in ((_CITED_AS_RE, "short_title"), (_ACT_IDENTITY_RE, "running_header")):
        match = pattern.search(blob)
        if match:
            act_no = normalize_act_no(match.group(1))
            act_year = match.group(2)
            return ActIdentity(
                act_no=act_no,
                act_year=act_year,
                label=format_act_label(act_no, act_year),
                source=source,
                parsed_from=source,
                quote=match.group(0)[:240],
            )
    file_match = _FILENAME_IDENTITY_RE.search(filename or "")
    if file_match:
        act_no = normalize_act_no(file_match.group(1))
        act_year = file_match.group(2)
        return ActIdentity(
            act_no=act_no,
            act_year=act_year,
            label=format_act_label(act_no, act_year),
            source="filename",
            parsed_from="filename",
            quote=file_match.group(0)[:240],
        )
    return None


def map_identity_to_source_doc_ids(
    identity: ActIdentity | None,
    documents: list[dict[str, Any]],
) -> list[str]:
    """Map Act No/year to known ids via manifest title regex (not LLM)."""
    if identity is None or not identity.act_no or not identity.act_year:
        return []
    want_no = int(identity.act_no)
    want_year = identity.act_year
    hits: list[str] = []
    for doc in documents:
        sid = str(doc.get("source_doc_id") or "")
        title = str(doc.get("title") or "")
        title_match = _TITLE_NO_YEAR_RE.search(title)
        if title_match and int(title_match.group(1)) == want_no and title_match.group(2) == want_year:
            if sid and sid not in hits:
                hits.append(sid)
            continue
        amend_id = f"ird-amend-{want_year}-{want_no:02d}"
        if sid == amend_id and sid not in hits:
            hits.append(sid)
        if want_no == 24 and want_year == "2017" and sid == "ird-ira-2017-base" and sid not in hits:
            hits.append(sid)
    return hits


def mint_source_doc_id(
    identity: ActIdentity | None,
    taken: set[str],
    *,
    text_sha256: str = "",
    avoid: str | None = None,
) -> str:
    taken_all = set(taken)
    if avoid:
        taken_all.add(avoid)
    if identity and identity.act_year and identity.act_no:
        canonical = f"ird-amend-{identity.act_year}-{normalize_act_no(identity.act_no)}"
        if canonical not in taken_all:
            return canonical
        suffix = (text_sha256 or "rescanned")[:8]
        candidate = f"{canonical}-{suffix}"
        n = 2
        while candidate in taken_all:
            candidate = f"{canonical}-{suffix}-{n}"
            n += 1
        return candidate
    suffix = (text_sha256 or "new")[:8]
    candidate = f"ird-amend-unknown-{suffix}"
    n = 2
    while candidate in taken_all:
        candidate = f"ird-amend-unknown-{suffix}-{n}"
        n += 1
    return candidate


def sha256_normalized(value: str, normalize) -> str:
    return hashlib.sha256(normalize(value or "").encode("utf-8")).hexdigest()


def fingerprints_from_path(pdf_path: Path) -> tuple[str, str]:
    """Primary = SHA-256 of normalized linear stream; secondary = tables_blob."""
    phase4 = p4()
    act = phase4.read_act_text(pdf_path)
    text_sha = sha256_normalized(act.stream, phase4.normalize_for_match)
    tables_sha = sha256_normalized(act.tables_blob, phase4.normalize_for_match)
    return text_sha, tables_sha


def read_identity_text(pdf_path: Path, *, max_pages: int = IDENTITY_PAGES) -> str:
    """Unstripped early-page text so running headers (stripped in read_act_text) remain."""
    import fitz

    doc = fitz.open(str(pdf_path))
    try:
        parts: list[str] = []
        for idx, page in enumerate(doc):
            if idx >= max_pages:
                break
            parts.append(page.get_text("text") or "")
        return "\n".join(parts)
    finally:
        doc.close()


def _extracted_on_for(source_doc_id: str, paths: CatalogAdminPaths) -> str | None:
    if not paths.extracted_dir.is_dir():
        return None
    dates: list[str] = []
    for path in paths.extracted_dir.glob(f"{source_doc_id}__*.json"):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        stamp = data.get("extracted_at")
        if isinstance(stamp, str) and stamp:
            dates.append(stamp)
    if dates:
        return min(dates)
    return None


def load_manifest_documents(paths: CatalogAdminPaths) -> list[dict[str, Any]]:
    if not paths.manifest_path.is_file():
        return []
    data = json.loads(paths.manifest_path.read_text(encoding="utf-8"))
    return list(data.get("documents") or [])


def load_hash_index(paths: CatalogAdminPaths) -> dict[str, Any] | None:
    if not paths.hash_index.is_file():
        return None
    try:
        return json.loads(paths.hash_index.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def index_staleness(
    index: dict[str, Any] | None,
    paths: CatalogAdminPaths,
) -> tuple[bool, list[str]]:
    warnings: list[str] = []
    if index is None:
        return True, [
            "corpus_text_hashes.json is missing — text-hash matching against the "
            "extract corpus is skipped until you refresh the index. Filename and "
            "Act No/year still apply."
        ]
    phase4 = p4()
    resolved, _rows, errors = phase4.confirm_pdf_paths()
    for err in errors:
        warnings.append(f"path check: {err}")
    by_id = {d.get("source_doc_id"): d for d in index.get("documents") or [] if d.get("source_doc_id")}
    missing = [sid for sid in resolved if sid not in by_id]
    if missing:
        warnings.append(
            "Hash index is missing extract-corpus ids: " + ", ".join(missing) + ". Refresh the index."
        )
    stale = bool(missing) or bool(errors)
    for sid, pdf_path in resolved.items():
        row = by_id.get(sid) or {}
        indexed_at = row.get("indexed_at") or index.get("indexed_at") or ""
        try:
            mtime = datetime.fromtimestamp(pdf_path.stat().st_mtime, tz=timezone.utc)
        except OSError:
            continue
        if not indexed_at:
            stale = True
            continue
        try:
            indexed_dt = datetime.fromisoformat(indexed_at.replace("Z", "+00:00"))
        except ValueError:
            stale = True
            continue
        if mtime > indexed_dt:
            stale = True
            warnings.append(
                f"Hash index may be stale for {sid} (PDF newer than indexed_at). Refresh the index."
            )
    if stale and not any("stale" in w.lower() or "missing" in w.lower() for w in warnings):
        warnings.append("Hash index may be stale. Refresh the index.")
    return stale, warnings


def build_corpus_hash_index(paths: CatalogAdminPaths | None = None) -> dict[str, Any]:
    """confirm_pdf_paths → read_act_text → write corpus_text_hashes.json. Never the manifest."""
    root = paths or catalog_admin_paths()
    if root.hash_index.resolve() == root.manifest_path.resolve():
        raise CatalogDuplicateError("Refusing to write the hash index over corpus_manifest.json.")
    phase4 = p4()
    resolved, rows, errors = phase4.confirm_pdf_paths()
    documents: list[dict[str, Any]] = []
    indexed_at = now_iso()
    for sid, pdf_path in resolved.items():
        text_sha, tables_sha = fingerprints_from_path(pdf_path)
        identity = parse_act_identity(read_identity_text(pdf_path), filename=pdf_path.name)
        row_meta = next((r for r in rows if r.get("source_doc_id") == sid), {})
        documents.append(
            {
                "source_doc_id": sid,
                "file_name": pdf_path.name,
                "text_sha256": text_sha,
                "tables_sha256": tables_sha,
                "act_no": identity.act_no if identity else "",
                "act_year": identity.act_year if identity else "",
                "indexed_at": indexed_at,
                "act_title": row_meta.get("act_title", ""),
            }
        )
    payload = {
        "spec_version": INDEX_SPEC,
        "phase": "catalog-admin-step2",
        "indexed_at": indexed_at,
        "note": (
            "SHA-256 of Phase 4 normalize_for_match(linear stream). "
            "Never rewrite corpus_manifest.json."
        ),
        "path_errors": errors,
        "documents": documents,
    }
    root.hash_index.parent.mkdir(parents=True, exist_ok=True)
    root.hash_index.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return payload


def _proposal_fingerprints(data: dict[str, Any], paths: CatalogAdminPaths) -> tuple[str, str, str]:
    text_sha = str(data.get("text_sha256") or "")
    tables_sha = str(data.get("tables_sha256") or "")
    pdf_sha = str(data.get("pdf_sha256") or "")
    if text_sha:
        return text_sha, tables_sha, pdf_sha
    rel = data.get("pdf_path") or ""
    if not rel:
        return text_sha, tables_sha, pdf_sha
    pdf_path = Path(rel)
    if not pdf_path.is_absolute():
        pdf_path = PROJECT_ROOT / pdf_path
    if not pdf_path.is_file():
        alt = paths.proposed_dir.parent / Path(rel).name
        if alt.is_file():
            pdf_path = alt
    if pdf_path.is_file():
        try:
            text_sha, tables_sha = fingerprints_from_path(pdf_path)
        except Exception:  # noqa: BLE001 — proposal PDF may be a missing fixture
            pass
        if not pdf_sha:
            pdf_sha = p6().file_sha256(pdf_path)
    return text_sha, tables_sha, pdf_sha


def load_complete_proposals(paths: CatalogAdminPaths) -> list[dict[str, Any]]:
    """Complete proposed/*.json only. Failed jobs are not proposals."""
    if not paths.proposed_dir.is_dir():
        return []
    out: list[dict[str, Any]] = []
    for path in sorted(paths.proposed_dir.glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        sid = str(data.get("source_doc_id") or path.stem)
        text_sha, tables_sha, pdf_sha = _proposal_fingerprints(data, paths)
        out.append(
            {
                "source_doc_id": sid,
                "extracted_at": data.get("extracted_at"),
                "uploaded_on": data.get("extracted_at"),
                "text_sha256": text_sha,
                "tables_sha256": tables_sha,
                "pdf_sha256": pdf_sha,
                "pdf_file_name": data.get("pdf_file_name") or path.name,
                "act_title": data.get("act_title") or "",
                "included_count": data.get("included_count"),
                "row_count": data.get("row_count"),
                "promotion_status": data.get("promotion_status"),
                "status": "extracted",
            }
        )
    return out


def taken_source_doc_ids(
    paths: CatalogAdminPaths,
    *,
    documents: list[dict[str, Any]],
    proposals: list[dict[str, Any]],
    jobs: list[dict[str, Any]],
) -> set[str]:
    taken = {str(d.get("source_doc_id")) for d in documents if d.get("source_doc_id")}
    taken.update(p4().EXTRACT_SOURCE_DOC_IDS)
    taken.update(sid for sid in (p.get("source_doc_id") for p in proposals) if sid)
    for job in jobs:
        if job.get("status") == "discarded":
            continue
        sid = job.get("source_doc_id")
        if sid:
            taken.add(str(sid))
    return taken


def classify_duplicate(
    *,
    text_sha256: str,
    tables_sha256: str,
    pdf_sha256: str,
    filename: str,
    identity: ActIdentity | None,
    corpus_rows: list[dict[str, Any]],
    proposals: list[dict[str, Any]],
    jobs: list[dict[str, Any]],
    documents: list[dict[str, Any]],
    taken: set[str],
    warnings: list[str],
    index_stale: bool,
) -> DuplicateDecision:
    """Hash first, filename fallback for corpus only, then Act No/year pause."""
    label = identity.label if identity else "this Act"
    name_l = (filename or "").lower()

    def _corpus_msg(sid: str, extracted_on: str | None, kind: MatchKind) -> DuplicateDecision:
        date_bit = extracted_on or "an unknown date"
        suggested = mint_source_doc_id(
            identity, taken, text_sha256=text_sha256, avoid=sid
        )
        return DuplicateDecision(
            case="a",
            match_kind=kind,
            message=(
                f"This Act ({label}) is already in the system as {sid}, "
                f"extracted on {date_bit}. No action taken. To continue to extract "
                f"without replacing {sid}, treat this file as a new source."
            ),
            text_sha256=text_sha256,
            tables_sha256=tables_sha256,
            pdf_sha256=pdf_sha256,
            filename=filename,
            act_identity=identity,
            matched_source_doc_id=sid,
            suggested_source_doc_id=suggested,
            extracted_on=extracted_on,
            warnings=list(warnings),
            index_stale=index_stale,
            actions=["cancel", "treat_as_new_source"],
        )

    for row in corpus_rows:
        if text_sha256 and row.get("text_sha256") == text_sha256:
            sid = str(row["source_doc_id"])
            return _corpus_msg(sid, row.get("extracted_on") or row.get("indexed_at"), "text_hash")

    for proposal in proposals:
        if text_sha256 and proposal.get("text_sha256") == text_sha256:
            sid = str(proposal["source_doc_id"])
            uploaded = proposal.get("extracted_at") or proposal.get("uploaded_on")
            return DuplicateDecision(
                case="b",
                match_kind="text_hash",
                message=(
                    f"This Act was already uploaded on {uploaded or 'an unknown date'} "
                    "and is awaiting review — go to the review queue instead."
                ),
                text_sha256=text_sha256,
                tables_sha256=tables_sha256,
                pdf_sha256=pdf_sha256,
                filename=filename,
                act_identity=identity,
                matched_source_doc_id=sid,
                uploaded_on=uploaded,
                extracted_on=uploaded,
                review_path=f"/adaptive-tax/catalog-admin/review/{sid}",
                warnings=list(warnings),
                index_stale=index_stale,
                actions=["open_review"],
            )

    for job in jobs:
        status = str(job.get("status") or "")
        hash_hit = bool(text_sha256) and job.get("text_sha256") == text_sha256
        pdf_hit = bool(pdf_sha256) and job.get("pdf_sha256") == pdf_sha256
        if not (hash_hit or pdf_hit):
            continue
        job_id = str(job.get("id") or "")
        kind: MatchKind = "text_hash" if hash_hit else "pdf_sha256"
        if status in IN_FLIGHT_STATUSES:
            return DuplicateDecision(
                case="b2",
                match_kind=kind,
                message=(
                    "Extraction already queued for this Act — open that job. "
                    "A second extract was not started."
                ),
                text_sha256=text_sha256,
                tables_sha256=tables_sha256,
                pdf_sha256=pdf_sha256,
                filename=filename,
                act_identity=identity,
                matched_source_doc_id=job.get("source_doc_id"),
                job_id=job_id,
                job_path=f"/adaptive-tax/catalog-admin/jobs/{job_id}",
                uploaded_on=job.get("created_at"),
                warnings=list(warnings),
                index_stale=index_stale,
                actions=["open_job"],
            )
        if status == "failed":
            return DuplicateDecision(
                case="prior_failed",
                match_kind=kind,
                message=(
                    f"A previous extract of this PDF failed"
                    f"{(' on ' + job['created_at']) if job.get('created_at') else ''}. "
                    "Retry that job instead of uploading again. Failed jobs are not "
                    "treated as pending review."
                ),
                text_sha256=text_sha256,
                tables_sha256=tables_sha256,
                pdf_sha256=pdf_sha256,
                filename=filename,
                act_identity=identity,
                matched_source_doc_id=job.get("source_doc_id"),
                job_id=job_id,
                job_path=f"/adaptive-tax/catalog-admin/jobs/{job_id}",
                uploaded_on=job.get("created_at"),
                warnings=list(warnings),
                index_stale=index_stale,
                actions=["open_failed_job"],
            )

    for row in corpus_rows:
        row_name = str(row.get("file_name") or "").lower()
        if name_l and row_name and name_l == row_name:
            sid = str(row["source_doc_id"])
            return _corpus_msg(sid, row.get("extracted_on") or row.get("indexed_at"), "filename")

    identity_hits = map_identity_to_source_doc_ids(identity, documents)
    if not identity_hits and identity:
        for row in corpus_rows:
            if (
                row.get("act_no") == identity.act_no
                and row.get("act_year") == identity.act_year
                and row.get("source_doc_id")
            ):
                identity_hits.append(str(row["source_doc_id"]))
    if identity_hits:
        sid = identity_hits[0]
        suggested = mint_source_doc_id(identity, taken, text_sha256=text_sha256, avoid=sid)
        return DuplicateDecision(
            case="d",
            match_kind="",
            message=(
                f"This appears to be a different file for an Act already in the "
                f"system ({sid}) — possible re-scan or updated copy."
            ),
            text_sha256=text_sha256,
            tables_sha256=tables_sha256,
            pdf_sha256=pdf_sha256,
            filename=filename,
            act_identity=identity,
            matched_source_doc_id=sid,
            suggested_source_doc_id=suggested,
            warnings=list(warnings),
            index_stale=index_stale,
            actions=["cancel", "treat_as_new_source"],
        )

    suggested = mint_source_doc_id(identity, taken, text_sha256=text_sha256)
    return DuplicateDecision(
        case="none",
        match_kind="",
        message=(
            f"No corpus or pending-review match. Suggested source_doc_id is "
            f"{suggested}. You can edit it before extract (next step)."
        ),
        text_sha256=text_sha256,
        tables_sha256=tables_sha256,
        pdf_sha256=pdf_sha256,
        filename=filename,
        act_identity=identity,
        suggested_source_doc_id=suggested,
        warnings=list(warnings),
        index_stale=index_stale,
        actions=["edit_source_doc_id"],
    )


def _corpus_rows_for_check(
    index: dict[str, Any] | None,
    documents: list[dict[str, Any]],
    paths: CatalogAdminPaths,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if index:
        for doc in index.get("documents") or []:
            sid = str(doc.get("source_doc_id") or "")
            if not sid:
                continue
            item = dict(doc)
            item["extracted_on"] = _extracted_on_for(sid, paths) or doc.get("indexed_at")
            rows.append(item)
    seen_names = {str(r.get("file_name") or "").lower() for r in rows if r.get("file_name")}
    # Filename fallback uses live manifest names even when the hash index is missing.
    for doc in documents:
        sid = str(doc.get("source_doc_id") or "")
        name = str(doc.get("file_name") or "")
        if not sid:
            continue
        if name.lower() in seen_names:
            continue
        rows.append(
            {
                "source_doc_id": sid,
                "file_name": name,
                "text_sha256": "",
                "tables_sha256": "",
                "act_no": "",
                "act_year": "",
                "extracted_on": _extracted_on_for(sid, paths),
            }
        )
        if name:
            seen_names.add(name.lower())
    return rows


def check_pdf(
    pdf_path: Path,
    *,
    original_filename: str,
    paths: CatalogAdminPaths | None = None,
) -> DuplicateDecision:
    root = paths or catalog_admin_paths()
    text_sha, tables_sha = fingerprints_from_path(pdf_path)
    pdf_sha = sha256_hex(pdf_path.read_bytes())
    identity = parse_act_identity(
        read_identity_text(pdf_path),
        filename=original_filename,
    )
    documents = load_manifest_documents(root)
    index = load_hash_index(root)
    stale, warnings = index_staleness(index, root)
    corpus_rows = _corpus_rows_for_check(index, documents, root)
    proposals = load_complete_proposals(root)
    jobs = list_jobs(root)
    taken = taken_source_doc_ids(root, documents=documents, proposals=proposals, jobs=jobs)
    return classify_duplicate(
        text_sha256=text_sha,
        tables_sha256=tables_sha,
        pdf_sha256=pdf_sha,
        filename=original_filename,
        identity=identity,
        corpus_rows=corpus_rows,
        proposals=proposals,
        jobs=jobs,
        documents=documents,
        taken=taken,
        warnings=warnings,
        index_stale=stale,
    )


def ingest_upload(
    *,
    content: bytes,
    filename: str,
    reviewer: str,
    paths: CatalogAdminPaths | None = None,
) -> tuple[DuplicateDecision, dict[str, Any] | None]:
    """Cheap-read + classify. Persists a job only when a later step still needs the PDF."""
    try:
        validate_pdf_bytes(content, filename=filename)
    except ValueError as exc:
        raise CatalogDuplicateError(str(exc)) from exc
    root = paths or catalog_admin_paths()
    root.uploads_dir.mkdir(parents=True, exist_ok=True)
    safe = sanitize_filename(filename)
    tmp_id = new_job_id()
    tmp_path = root.uploads_dir / f"{tmp_id}_{safe}"
    tmp_path.write_bytes(content)
    try:
        decision = check_pdf(tmp_path, original_filename=filename, paths=root)
    except Exception as exc:
        tmp_path.unlink(missing_ok=True)
        raise CatalogDuplicateError(f"Could not read PDF text: {exc}") from exc

    persist = decision.case in {"a", "d", "none"}
    if not persist:
        tmp_path.unlink(missing_ok=True)
        return decision, None

    paused = decision.case in {"a", "d"}
    job = {
        "id": tmp_id,
        "status": "paused_rescan" if paused else "uploaded",
        "original_filename": filename,
        "storage_path": tmp_path.as_posix(),
        "text_sha256": decision.text_sha256,
        "tables_sha256": decision.tables_sha256,
        "pdf_sha256": decision.pdf_sha256,
        "act_identity": decision.act_identity.as_dict() if decision.act_identity else None,
        "matched_source_doc_id": decision.matched_source_doc_id,
        "source_doc_id": None if paused else decision.suggested_source_doc_id,
        "suggested_source_doc_id": decision.suggested_source_doc_id,
        "duplicate_case": decision.case,
        "uploaded_by": reviewer,
        "created_at": now_iso(),
        "error": None,
    }
    save_job(job, root)
    decision.job_id = tmp_id
    decision.job_path = f"/adaptive-tax/catalog-admin/jobs/{tmp_id}"
    return decision, job


def treat_as_new_source(
    job_id: str,
    *,
    reviewer: str,
    paths: CatalogAdminPaths | None = None,
) -> tuple[DuplicateDecision, dict[str, Any]]:
    """Case (d) only: mint a new id. Never replace the matched source_doc_id."""
    from adaptive_tax_app.services.catalog_admin_store import load_job

    root = paths or catalog_admin_paths()
    job = load_job(job_id, root)
    if job is None:
        raise CatalogDuplicateError(f"Job {job_id} not found.")
    if job.get("status") != "paused_rescan":
        raise CatalogDuplicateError("Only a paused re-scan can be treated as a new source.")
    avoid = str(job.get("matched_source_doc_id") or "")
    documents = load_manifest_documents(root)
    proposals = load_complete_proposals(root)
    jobs = list_jobs(root)
    taken = taken_source_doc_ids(root, documents=documents, proposals=proposals, jobs=jobs)
    identity_raw = job.get("act_identity") or {}
    identity = (
        ActIdentity(
            act_no=str(identity_raw.get("act_no") or ""),
            act_year=str(identity_raw.get("act_year") or ""),
            label=str(identity_raw.get("label") or ""),
            source=str(identity_raw.get("source") or identity_raw.get("parsed_from") or ""),
            parsed_from=str(identity_raw.get("parsed_from") or identity_raw.get("source") or ""),
            quote=str(identity_raw.get("quote") or ""),
        )
        if identity_raw
        else None
    )
    new_id = mint_source_doc_id(
        identity,
        taken,
        text_sha256=str(job.get("text_sha256") or ""),
        avoid=avoid or None,
    )
    if new_id == avoid:
        raise CatalogDuplicateError(f"Refusing to replace {avoid}.")
    job["status"] = "uploaded"
    job["source_doc_id"] = new_id
    job["suggested_source_doc_id"] = new_id
    job["duplicate_case"] = "none"
    job["treated_as_new_source_by"] = reviewer
    job["treated_as_new_source_at"] = now_iso()
    save_job(job, root)
    decision = DuplicateDecision(
        case="none",
        message=(
            f"Recorded as a new source {new_id} — did not replace {avoid}. "
            "Extract (Pass 1) is the next step."
        ),
        text_sha256=str(job.get("text_sha256") or ""),
        tables_sha256=str(job.get("tables_sha256") or ""),
        pdf_sha256=str(job.get("pdf_sha256") or ""),
        filename=str(job.get("original_filename") or ""),
        act_identity=identity,
        matched_source_doc_id=avoid or None,
        suggested_source_doc_id=new_id,
        job_id=job_id,
        job_path=f"/adaptive-tax/catalog-admin/jobs/{job_id}",
        actions=["edit_source_doc_id"],
    )
    return decision, job


def discard_job(job_id: str, *, reviewer: str, paths: CatalogAdminPaths | None = None) -> dict[str, Any]:
    from adaptive_tax_app.services.catalog_admin_store import load_job

    root = paths or catalog_admin_paths()
    job = load_job(job_id, root)
    if job is None:
        raise CatalogDuplicateError(f"Job {job_id} not found.")
    if job.get("status") in {"extracted", "extracting"}:
        raise CatalogDuplicateError("Cannot discard an in-flight or completed extract.")
    storage = job.get("storage_path")
    if storage:
        Path(storage).unlink(missing_ok=True)
    job["status"] = "discarded"
    job["discarded_by"] = reviewer
    job["discarded_at"] = now_iso()
    save_job(job, root)
    return job


def set_source_doc_id(
    job_id: str,
    source_doc_id: str,
    *,
    paths: CatalogAdminPaths | None = None,
) -> dict[str, Any]:
    from adaptive_tax_app.services.catalog_admin_store import load_job

    root = paths or catalog_admin_paths()
    job = load_job(job_id, root)
    if job is None:
        raise CatalogDuplicateError(f"Job {job_id} not found.")
    if job.get("status") != "uploaded":
        raise CatalogDuplicateError("source_doc_id can only be edited before extract.")
    sid = (source_doc_id or "").strip()
    if not re.fullmatch(r"ird-[a-z0-9-]+", sid):
        raise CatalogDuplicateError(
            "source_doc_id must match ird-amend-{year}-{nn} (lowercase letters, digits, hyphens)."
        )
    documents = load_manifest_documents(root)
    proposals = load_complete_proposals(root)
    jobs = list_jobs(root)
    taken = taken_source_doc_ids(root, documents=documents, proposals=proposals, jobs=jobs)
    taken.discard(str(job.get("source_doc_id") or ""))
    avoid = str(job.get("matched_source_doc_id") or "")
    if sid == avoid:
        raise CatalogDuplicateError(
            f"Cannot use {sid} — that is the existing Act. Treat as a new source uses a different id."
        )
    if sid in taken:
        raise CatalogDuplicateError(f"{sid} is already used. Pick a different source_doc_id.")
    job["source_doc_id"] = sid
    job["suggested_source_doc_id"] = sid
    save_job(job, root)
    return job


def queue_payload(paths: CatalogAdminPaths | None = None) -> dict[str, Any]:
    root = paths or catalog_admin_paths()
    proposals = load_complete_proposals(root)
    jobs = list_jobs(root)
    in_flight = [j for j in jobs if j.get("status") in IN_FLIGHT_STATUSES]
    failed = [j for j in jobs if j.get("status") == "failed"]
    return {
        "proposals": [
            {
                "source_doc_id": p["source_doc_id"],
                "extracted_at": p.get("extracted_at"),
                "text_sha256": p.get("text_sha256"),
                "act_title": p.get("act_title") or "",
                "pdf_file_name": p.get("pdf_file_name"),
                "included_count": p.get("included_count"),
                "promotion_status": p.get("promotion_status"),
                "review_path": f"/adaptive-tax/catalog-admin/review/{p['source_doc_id']}",
            }
            for p in proposals
        ],
        "in_flight_jobs": [
            {
                "id": j.get("id"),
                "status": j.get("status"),
                "source_doc_id": j.get("source_doc_id"),
                "original_filename": j.get("original_filename"),
                "act_label": ((j.get("act_identity") or {}) or {}).get("label"),
                "created_at": j.get("created_at"),
                "job_path": f"/adaptive-tax/catalog-admin/jobs/{j.get('id')}",
            }
            for j in in_flight
        ],
        "failed_jobs": [
            {
                "id": j.get("id"),
                "status": "failed",
                "error": j.get("error"),
                "created_at": j.get("created_at"),
                "original_filename": j.get("original_filename"),
                "act_label": ((j.get("act_identity") or {}) or {}).get("label"),
                "job_path": f"/adaptive-tax/catalog-admin/jobs/{j.get('id')}",
            }
            for j in failed
        ],
        "note": (
            "Complete proposed/ items are pending review. In-flight jobs are not. "
            "Failed jobs are excluded from pending-review duplicates — retry that job."
        ),
    }
