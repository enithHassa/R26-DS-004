"""Semantic chunking for tax act PDFs."""

import logging
import re
from typing import Any

logger = logging.getLogger(__name__)


class ReliefChunker:
    """
    Semantic chunker optimized for tax relief provisions.
    Splits by relief/section boundaries, not fixed token size.
    """

    # Patterns for tax act structure
    SCHEDULE_PATTERN = re.compile(
        r"(?:First|Fifth|Sixth|Seventh|Eighth|Ninth|Tenth|Eleventh|Twelfth)\s+Schedule",
        re.IGNORECASE,
    )
    PARAGRAPH_PATTERN = re.compile(r"^\s*paragraph\s+\d+", re.IGNORECASE | re.MULTILINE)
    SECTION_PATTERN = re.compile(r"^\s*(?:Section|Part|Chapter)\s+\d+", re.IGNORECASE | re.MULTILINE)
    RELIEF_PATTERN = re.compile(r"Rs\.\s*[\d,]+", re.IGNORECASE)

    @staticmethod
    def chunk_text(
        text: str,
        chunk_size: int = 800,
        overlap: int = 100,
        by_schedule: bool = True,
    ) -> list[dict[str, Any]]:
        """
        Chunk PDF text semantically for relief provisions.

        Args:
            text: Full extracted text from PDF
            chunk_size: Target tokens per chunk (approximate)
            overlap: Token overlap between chunks
            by_schedule: Try to preserve schedule boundaries

        Returns:
            [
                {
                    "chunk_id": "chunk_001",
                    "text": "Relief provision text...",
                    "start_char": 1000,
                    "end_char": 2000,
                    "has_relief": True,
                    "has_amount": True,
                    "relief_amounts": ["1200000", "1500000"],
                }
            ]
        """
        if not text or len(text.strip()) == 0:
            logger.warning("Empty text provided to chunker")
            return []

        logger.info(f"Chunking text ({len(text)} chars)")

        # Split by schedules first (if applicable)
        if by_schedule:
            sections = ReliefChunker._split_by_schedule(text)
        else:
            sections = [{"title": "Full Document", "content": text, "order": 1}]

        chunks = []
        chunk_id = 1

        for section in sections:
            # Further split section into smaller chunks with overlap
            section_chunks = ReliefChunker._chunk_section(
                section["content"],
                chunk_size=chunk_size,
                overlap=overlap,
                section_title=section["title"],
            )

            for chunk_text in section_chunks:
                chunk_data = {
                    "chunk_id": f"chunk_{chunk_id:03d}",
                    "text": chunk_text,
                    "has_relief": bool(re.search(r"relief|exemption|deduction", chunk_text, re.IGNORECASE)),
                    "has_amount": bool(ReliefChunker.RELIEF_PATTERN.search(chunk_text)),
                    "relief_amounts": ReliefChunker._extract_amounts(chunk_text),
                    "section": section["title"],
                }
                chunks.append(chunk_data)
                chunk_id += 1

        logger.info(f"Created {len(chunks)} chunks")
        return chunks

    @staticmethod
    def _split_by_schedule(text: str) -> list[dict[str, Any]]:
        """Split text by schedule headers."""
        schedules = []
        matches = list(ReliefChunker.SCHEDULE_PATTERN.finditer(text))

        if not matches:
            return [{"title": "Full Document", "content": text, "order": 1}]

        for i, match in enumerate(matches):
            start = match.start()
            end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
            schedule_title = match.group()
            schedules.append(
                {
                    "title": schedule_title,
                    "content": text[start:end],
                    "order": i,
                }
            )

        return schedules

    @staticmethod
    def _chunk_section(
        section_text: str,
        chunk_size: int = 800,
        overlap: int = 100,
        section_title: str = "",
    ) -> list[str]:
        """
        Chunk a section (schedule) into smaller chunks.
        Tries to break at logical boundaries (paragraphs, reliefs).
        """
        if len(section_text) < chunk_size:
            return [section_text]

        chunks = []
        words = section_text.split()

        if not words:
            return [section_text]

        # Estimate words per chunk (rough: 1 word ≈ 1.3 tokens)
        words_per_chunk = max(10, int(chunk_size / 1.3))
        overlap_words = max(5, int(overlap / 1.3))

        for i in range(0, len(words), words_per_chunk - overlap_words):
            chunk_words = words[i : i + words_per_chunk]
            chunk_text = " ".join(chunk_words)

            if chunk_text.strip():
                chunks.append(chunk_text)

        logger.debug(f"Split '{section_title}' into {len(chunks)} chunks")
        return chunks

    @staticmethod
    def _extract_amounts(text: str) -> list[str]:
        """Extract relief amounts (Rs. values) from chunk."""
        amounts = []
        for match in ReliefChunker.RELIEF_PATTERN.finditer(text):
            amount_text = match.group().replace("Rs.", "").strip()
            amounts.append(amount_text)
        return list(set(amounts))  # Deduplicate
