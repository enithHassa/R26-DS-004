"""Dual-text PDF extract: page text_stream plus pdfplumber table_render."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from pypdf import PdfReader


@dataclass
class DualExtract:
    pages: list[tuple[int, str]]
    tables_by_page: dict[int, list[str]]
    page_count: int
    table_method: str | None = None
    warnings: list[str] = field(default_factory=list)


def extract_pdf_pages(path: Path) -> list[tuple[int, str]]:
    reader = PdfReader(str(path))
    pages: list[tuple[int, str]] = []
    for i, page in enumerate(reader.pages):
        try:
            text = page.extract_text() or ""
        except Exception as exc:  # noqa: BLE001
            text = f"<!-- extract error: {exc} -->"
        pages.append((i + 1, text))
    return pages


def extract_pdf_tables_by_page(path: Path) -> tuple[dict[int, list[str]], str | None, list[str]]:
    warnings: list[str] = []
    try:
        import pdfplumber  # type: ignore[import-untyped]
    except ImportError:
        return {}, None, ["pdfplumber not installed; table_render omitted"]

    out: dict[int, list[str]] = {}
    try:
        with pdfplumber.open(str(path)) as pdf:
            for i, page in enumerate(pdf.pages):
                page_num = i + 1
                tables = page.extract_tables() or []
                blobs: list[str] = []
                for table in tables:
                    if not table:
                        continue
                    lines: list[str] = []
                    for row in table:
                        cells = [
                            ""
                            if c is None
                            else str(c).strip().replace("\n", " ").replace("\t", " ")
                            for c in row
                        ]
                        lines.append("\t".join(cells))
                    blob = "\n".join(lines).strip()
                    if blob:
                        blobs.append(blob)
                if blobs:
                    out[page_num] = blobs
    except Exception as exc:  # noqa: BLE001
        warnings.append(f"table extract failed: {exc}")
        return {}, None, warnings
    return out, "pdfplumber", warnings


def extract_dual_text(path: Path) -> DualExtract:
    pages = extract_pdf_pages(path)
    tables, method, warnings = extract_pdf_tables_by_page(path)
    return DualExtract(
        pages=pages,
        tables_by_page=tables,
        page_count=len(pages),
        table_method=method,
        warnings=warnings,
    )
