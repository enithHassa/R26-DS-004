"""Hash-first duplicate detection for act-admin uploads (before LLM extract)."""

from __future__ import annotations

import hashlib
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Literal

from sqlalchemy.orm import Session

from db.models import OeEngineDocument
from oe_engine_app.services.act_admin_store import (
    IN_FLIGHT_STATUSES,
    PENDING_REVIEW_STATUSES,
    ActAdminPaths,
    act_admin_paths,
    list_jobs,
    new_job_id,
    now_iso,
    save_job,
)
from oe_engine_app.services.pdf_extract import extract_pdf_pages

DuplicateCase = Literal["clear", "corpus_match", "pending_review", "in_flight", "prior_failed"]

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


class ActAdminUploadError(ValueError):
    """Upload cannot be processed."""


@dataclass(frozen=True)
class ActIdentity:
    act_no: str
    act_year: str
    label: str
    source: str
    quote: str = ""

    def as_dict(self) -> dict[str, str]:
        return asdict(self)


@dataclass
class DuplicateDecision:
    case: DuplicateCase
    message: str
    pdf_sha256: str = ""
    filename: str = ""
    act_identity: ActIdentity | None = None
    matched_source_doc_id: str | None = None
    suggested_source_doc_id: str | None = None
    job_id: str | None = None
    warnings: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "case": self.case,
            "message": self.message,
            "pdf_sha256": self.pdf_sha256,
            "filename": self.filename,
            "matched_source_doc_id": self.matched_source_doc_id,
            "suggested_source_doc_id": self.suggested_source_doc_id,
            "job_id": self.job_id,
            "warnings": self.warnings,
        }
        if self.act_identity is not None:
            payload["act_identity"] = self.act_identity.as_dict()
        return payload


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def validate_pdf_bytes(raw: bytes) -> None:
    if not raw:
        raise ActAdminUploadError("Empty upload.")
    if not raw.startswith(b"%PDF"):
        raise ActAdminUploadError("Not a PDF file.")


def normalize_act_no(raw: str) -> str:
    digits = re.sub(r"\D", "", raw or "")
    if not digits:
        return ""
    return str(int(digits))


def format_act_label(act_no: str, act_year: str) -> str:
    if not act_no or not act_year:
        return ""
    return f"Act No. {normalize_act_no(act_no)} of {act_year}"


def parse_act_identity(text: str, *, filename: str = "") -> ActIdentity | None:
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
            quote=file_match.group(0)[:240],
        )
    return None


def mint_source_doc_id(identity: ActIdentity | None, *, job_id: str) -> str:
    if identity and identity.act_no and identity.act_year:
        return f"oee-act-{identity.act_no}-{identity.act_year}"
    return f"oee-act-upload-{job_id[:8]}"


def _cheap_text_sample(raw: bytes, *, filename: str) -> tuple[str, list[str]]:
    import tempfile

    warnings: list[str] = []
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as handle:
        handle.write(raw)
        temp_path = Path(handle.name)
    try:
        pages = extract_pdf_pages(temp_path)
        text = "\n".join(text for _, text in pages[:8])
        if not text.strip():
            warnings.append("Could not read PDF text from first pages.")
        return text, warnings
    except Exception as exc:  # noqa: BLE001
        warnings.append(f"PDF read failed: {exc}")
        return "", warnings
    finally:
        temp_path.unlink(missing_ok=True)


def _job_for_hash(pdf_sha256: str, paths: ActAdminPaths) -> dict[str, Any] | None:
    for job in list_jobs(paths):
        if str(job.get("pdf_sha256") or "") == pdf_sha256:
            return job
    return None


def check_duplicate(
    session: Session,
    *,
    raw: bytes,
    filename: str,
    paths: ActAdminPaths | None = None,
) -> DuplicateDecision:
    root = paths or act_admin_paths()
    validate_pdf_bytes(raw)
    digest = sha256_bytes(raw)
    text, warnings = _cheap_text_sample(raw, filename=filename)
    identity = parse_act_identity(text, filename=filename)
    suggested = mint_source_doc_id(identity, job_id=new_job_id())

    doc = session.query(OeEngineDocument).filter(OeEngineDocument.sha256 == digest).one_or_none()
    if doc is not None:
        return DuplicateDecision(
            case="corpus_match",
            message=f"PDF hash already ingested as {doc.source_doc_id}.",
            pdf_sha256=digest,
            filename=filename,
            act_identity=identity,
            matched_source_doc_id=doc.source_doc_id,
            suggested_source_doc_id=suggested,
            warnings=warnings,
        )

    existing_job = _job_for_hash(digest, root)
    if existing_job is not None:
        status = str(existing_job.get("status") or "")
        job_id = str(existing_job.get("id") or "")
        if status in IN_FLIGHT_STATUSES:
            return DuplicateDecision(
                case="in_flight",
                message="Extraction is already running for this PDF.",
                pdf_sha256=digest,
                filename=filename,
                act_identity=identity,
                matched_source_doc_id=str(existing_job.get("source_doc_id") or "") or None,
                suggested_source_doc_id=suggested,
                job_id=job_id,
                warnings=warnings,
            )
        if status in PENDING_REVIEW_STATUSES:
            return DuplicateDecision(
                case="pending_review",
                message="This PDF is already waiting in review.",
                pdf_sha256=digest,
                filename=filename,
                act_identity=identity,
                matched_source_doc_id=str(existing_job.get("source_doc_id") or "") or None,
                suggested_source_doc_id=suggested,
                job_id=job_id,
                warnings=warnings,
            )
        if status == "failed":
            return DuplicateDecision(
                case="prior_failed",
                message="A previous extract failed for this PDF — retry that job.",
                pdf_sha256=digest,
                filename=filename,
                act_identity=identity,
                matched_source_doc_id=str(existing_job.get("source_doc_id") or "") or None,
                suggested_source_doc_id=suggested,
                job_id=job_id,
                warnings=warnings,
            )

    return DuplicateDecision(
        case="clear",
        message="No duplicate found.",
        pdf_sha256=digest,
        filename=filename,
        act_identity=identity,
        suggested_source_doc_id=suggested,
        warnings=warnings,
    )


def ingest_upload(
    session: Session,
    *,
    raw: bytes,
    filename: str,
    reviewer: str,
    paths: ActAdminPaths | None = None,
) -> tuple[DuplicateDecision, dict[str, Any]]:
    root = paths or act_admin_paths()
    decision = check_duplicate(session, raw=raw, filename=filename, paths=root)
    if decision.case in {"in_flight", "pending_review", "prior_failed"}:
        job = _job_for_hash(decision.pdf_sha256, root)
        if job is not None:
            decision.job_id = str(job.get("id") or "")
        return decision, job or {}

    job_id = new_job_id()
    source_doc_id = mint_source_doc_id(decision.act_identity, job_id=job_id)
    root.uploads_dir.mkdir(parents=True, exist_ok=True)
    safe_name = re.sub(r"[^\w.\-]+", "_", filename or "upload.pdf")
    storage_path = root.uploads_dir / f"{job_id}__{safe_name}"
    storage_path.write_bytes(raw)

    job = {
        "id": job_id,
        "status": "uploaded",
        "source_doc_id": source_doc_id,
        "original_filename": filename,
        "storage_path": storage_path.as_posix(),
        "pdf_sha256": decision.pdf_sha256,
        "act_identity": decision.act_identity.as_dict() if decision.act_identity else None,
        "reviewer": reviewer,
        "uploaded_at": now_iso(),
        "error": None,
    }
    save_job(job, root)
    decision.job_id = job_id
    decision.suggested_source_doc_id = source_doc_id
    if decision.case == "corpus_match":
        decision.message = (
            f"PDF matches ingested corpus ({decision.matched_source_doc_id}). "
            "Starting a new draft extract for review."
        )
    return decision, job
