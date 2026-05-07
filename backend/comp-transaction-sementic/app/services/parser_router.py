"""Select downstream parser id from bank detection + file format (Phase 2)."""

from __future__ import annotations

from pathlib import Path

from .bank_detection import BankDetectionResult


def resolve_file_format(filename: str, content_type: str | None) -> str:
    ext = Path(filename).suffix.lower().lstrip(".")
    if ext in {"pdf", "csv", "xlsx", "xls", "txt", "jpg", "jpeg", "png"}:
        if ext == "xls":
            return "xlsx"
        return ext
    if not content_type:
        return "unknown"
    ct = content_type.lower()
    if "pdf" in ct:
        return "pdf"
    if "csv" in ct:
        return "csv"
    if "spreadsheet" in ct or "excel" in ct:
        return "xlsx"
    if "text/plain" in ct:
        return "txt"
    if "jpeg" in ct or "jpg" in ct:
        return "jpeg"
    if "png" in ct:
        return "png"
    return "unknown"


def select_parser(
    *,
    detection: BankDetectionResult,
    file_format: str,
) -> tuple[str, dict]:
    """Return (selected_parser_id, router_notes).

    These ids are consumed by Phase 3 extractors; Phase 2 only records the choice.
    """
    notes: dict[str, object] = {
        "router_reason": None,
    }

    if file_format in {"jpg", "jpeg", "png"}:
        if detection.bank_code == "NTB":
            notes["router_reason"] = "raster_ntb"
            return "ntb_pdf_v1", notes
        if detection.bank_code == "SAMPATH":
            notes["router_reason"] = "raster_sampath"
            return "sampath_pdf_v1", notes
        if detection.confidence >= 0.35 and detection.bank_code:
            notes["router_reason"] = "raster_bank_template"
            return f"{detection.bank_code.lower()}_pdf_v1", notes
        notes["router_reason"] = "raster_generic"
        return "generic_pdf_v1", notes

    if file_format == "csv":
        notes["router_reason"] = "tabular_csv"
        return "generic_csv_v1", notes

    if file_format == "xlsx":
        notes["router_reason"] = "tabular_xlsx"
        return "generic_xlsx_v1", notes

    if file_format == "txt":
        notes["router_reason"] = "freeform_text"
        return "generic_txt_v1", notes

    if file_format == "pdf":
        if detection.bank_code == "NTB":
            notes["router_reason"] = "bank_template_ntb"
            return "ntb_pdf_v1", notes
        if detection.bank_code == "SAMPATH":
            notes["router_reason"] = "bank_template_sampath"
            return "sampath_pdf_v1", notes
        if detection.confidence >= 0.35 and detection.bank_code:
            notes["router_reason"] = "bank_template_generic_bank"
            return f"{detection.bank_code.lower()}_pdf_v1", notes
        notes["router_reason"] = "generic_pdf_fallback"
        return "generic_pdf_v1", notes

    notes["router_reason"] = "unknown_format"
    return "generic_unknown_v1", notes
