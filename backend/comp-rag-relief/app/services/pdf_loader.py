"""PDF loading and text extraction service."""

import logging
from pathlib import Path
from typing import Any

import pdfplumber

logger = logging.getLogger(__name__)


class PDFLoader:
    """Load and extract text from PDF files."""

    @staticmethod
    def load_pdf(pdf_path: Path | str) -> dict[str, Any]:
        """
        Load single PDF and extract full text.

        Args:
            pdf_path: Path to PDF file

        Returns:
            {
                "filename": "act_name.pdf",
                "pages": 50,
                "text": "Full extracted text...",
                "text_by_page": ["Page 1 text", "Page 2 text", ...],
                "metadata": {...}
            }
        """
        pdf_path = Path(pdf_path)

        if not pdf_path.exists():
            raise FileNotFoundError(f"PDF not found: {pdf_path}")

        if pdf_path.suffix.lower() != ".pdf":
            raise ValueError(f"Not a PDF file: {pdf_path}")

        logger.info(f"Loading PDF: {pdf_path.name}")

        full_text = ""
        text_by_page = []
        page_count = 0

        try:
            with pdfplumber.open(pdf_path) as pdf:
                page_count = len(pdf.pages)

                for page_num, page in enumerate(pdf.pages, start=1):
                    try:
                        page_text = page.extract_text() or ""
                        text_by_page.append(page_text)
                        full_text += f"\n\n--- Page {page_num} ---\n{page_text}"
                    except Exception as e:
                        logger.warning(f"Failed to extract page {page_num}: {e}")
                        text_by_page.append("")

                # Extract metadata
                metadata = pdf.metadata or {}

        except Exception as e:
            logger.error(f"Failed to load PDF {pdf_path.name}: {e}")
            raise RuntimeError(f"PDF extraction failed: {e}") from e

        logger.info(f"Extracted {page_count} pages from {pdf_path.name}")

        return {
            "filename": pdf_path.name,
            "filepath": str(pdf_path),
            "pages": page_count,
            "text": full_text.strip(),
            "text_by_page": text_by_page,
            "metadata": metadata,
            "success": True,
        }

    @staticmethod
    def load_pdf_batch(pdf_dir: Path | str) -> dict[str, Any]:
        """
        Load all PDFs from a directory.

        Args:
            pdf_dir: Directory containing PDF files

        Returns:
            {
                "total_files": 9,
                "loaded": [{"filename": "act1.pdf", "pages": 50, ...}, ...],
                "failed": [{"filename": "act2.pdf", "error": "..."}, ...],
            }
        """
        pdf_dir = Path(pdf_dir)

        if not pdf_dir.exists():
            raise FileNotFoundError(f"Directory not found: {pdf_dir}")

        logger.info(f"Loading all PDFs from {pdf_dir}")

        loaded = []
        failed = []

        for pdf_file in sorted(pdf_dir.glob("*.pdf")):
            try:
                result = PDFLoader.load_pdf(pdf_file)
                loaded.append(result)
                logger.info(f"✓ Loaded {pdf_file.name}")
            except Exception as e:
                logger.error(f"✗ Failed {pdf_file.name}: {e}")
                failed.append({"filename": pdf_file.name, "error": str(e)})

        logger.info(f"Batch load complete: {len(loaded)} loaded, {len(failed)} failed")

        return {
            "total_files": len(loaded) + len(failed),
            "loaded_count": len(loaded),
            "failed_count": len(failed),
            "loaded": loaded,
            "failed": failed,
        }
