#!/usr/bin/env python3
"""Phase 1b bootstrap for IRD corpus ingestion.

This script supports Day 1-3 of the roadmap:
- crawl/link inventory from IRD Income Tax hub
- identify downloadable source candidates
- optionally download sources and compute SHA256
- emit manifest-ready rows for governance tracking
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from collections import deque
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin, urlparse

import httpx

HUB_URL = "https://www.ird.gov.lk/en/type%20of%20taxes/sitepages/income%20tax.aspx?menuid=1201"
DEFAULT_OUT_DIR = Path("data/raw/ird/inventory")
DEFAULT_DOWNLOAD_DIR = Path("data/raw/ird/downloads")
DEFAULT_MANIFEST_OUT = Path("data/raw/ird/source_manifest_autofill.csv")
DEFAULT_TIMEOUT = 25.0
DOC_EXTENSIONS = (".pdf", ".doc", ".docx", ".xls", ".xlsx", ".csv")
TIER_A_HINTS = ("act", "inland revenue act", "amendment", "consolidated")
TIER_B_HINTS = ("guide", "e-services", "e services", "quick guide", "return")
TIER_C_HINTS = (
    "circular",
    "ruling",
    "publications",
    "apit",
    "paye",
    "schedule",
    "forms",
)


class LinkParser(HTMLParser):
    """Extract href links and page title from HTML."""

    def __init__(self) -> None:
        super().__init__()
        self.links: list[str] = []
        self._capture_title = False
        self._title_parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() == "a":
            href = dict(attrs).get("href")
            if href:
                self.links.append(href)
        elif tag.lower() == "title":
            self._capture_title = True

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() == "title":
            self._capture_title = False

    def handle_data(self, data: str) -> None:
        if self._capture_title:
            self._title_parts.append(data.strip())

    @property
    def title(self) -> str:
        return " ".join([p for p in self._title_parts if p]).strip()


@dataclass
class InventoryRecord:
    source_page: str
    target_url: str
    title: str
    link_text_guess: str
    file_ext: str
    doc_type: str
    tier: str
    instrument_type: str


def now_utc_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def normalize_url(url: str, base: str) -> str:
    joined = urljoin(base, url)
    parsed = urlparse(joined)
    return parsed._replace(fragment="").geturl()


def is_same_host(url: str, seed_host: str) -> bool:
    host = urlparse(url).netloc.lower()
    return host == seed_host.lower()


def classify_tier(text: str) -> str:
    lowered = text.lower()
    if any(h in lowered for h in TIER_A_HINTS):
        return "A"
    if any(h in lowered for h in TIER_B_HINTS):
        return "B"
    if any(h in lowered for h in TIER_C_HINTS):
        return "C"
    return "C"


def classify_instrument_type(text: str, ext: str) -> str:
    lowered = text.lower()
    if "consolidated" in lowered:
        return "consolidated"
    if "amendment" in lowered:
        return "amendment_act"
    if "act" in lowered:
        return "act"
    if "circular" in lowered:
        return "circular"
    if "ruling" in lowered:
        return "ruling"
    if "guide" in lowered:
        return "guide"
    if "table" in lowered or "apit" in lowered or "paye" in lowered:
        return "table"
    if ext in (".xls", ".xlsx", ".csv"):
        return "schedule"
    return "publication"


def classify_doc_type(ext: str) -> str:
    if ext == ".pdf":
        return "pdf"
    if ext in (".doc", ".docx"):
        return "doc"
    if ext in (".xls", ".xlsx", ".csv"):
        return "tabular"
    return "html"


def slugify(value: str) -> str:
    value = value.lower().strip()
    value = re.sub(r"[^a-z0-9]+", "-", value)
    return value.strip("-")[:80] or "source"


def compute_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        while True:
            chunk = f.read(65536)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def extract_links(page_html: str, page_url: str) -> tuple[str, list[str]]:
    parser = LinkParser()
    parser.feed(page_html)
    urls = [normalize_url(link, page_url) for link in parser.links]
    return parser.title, urls


def crawl_inventory(hub_url: str, max_pages: int, timeout: float) -> list[InventoryRecord]:
    seed_host = urlparse(hub_url).netloc
    queue: deque[str] = deque([hub_url])
    visited: set[str] = set()
    records: list[InventoryRecord] = []

    with httpx.Client(timeout=timeout, follow_redirects=True) as client:
        while queue and len(visited) < max_pages:
            page_url = queue.popleft()
            if page_url in visited:
                continue
            visited.add(page_url)

            try:
                resp = client.get(page_url)
                resp.raise_for_status()
            except Exception:
                continue

            content_type = resp.headers.get("content-type", "").lower()
            if "text/html" not in content_type and not page_url.lower().endswith(".aspx"):
                continue

            title, links = extract_links(resp.text, page_url)
            for link in links:
                if not is_same_host(link, seed_host):
                    continue

                lowered = link.lower()
                ext = Path(urlparse(link).path).suffix.lower()
                link_text = f"{title} {link}"

                if ext in DOC_EXTENSIONS:
                    tier = classify_tier(link_text)
                    records.append(
                        InventoryRecord(
                            source_page=page_url,
                            target_url=link,
                            title=title or "IRD source",
                            link_text_guess=link_text,
                            file_ext=ext,
                            doc_type=classify_doc_type(ext),
                            tier=tier,
                            instrument_type=classify_instrument_type(link_text, ext),
                        )
                    )
                    continue

                if "sitepages" in lowered or "publications" in lowered or "downloads" in lowered:
                    if link not in visited:
                        queue.append(link)

    # Remove duplicates by URL, preferring first-seen source page.
    dedup: dict[str, InventoryRecord] = {}
    for r in records:
        dedup.setdefault(r.target_url, r)
    return list(dedup.values())


def write_inventory(records: list[InventoryRecord], out_dir: Path) -> tuple[Path, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / "ird_link_inventory.json"
    csv_path = out_dir / "ird_link_inventory.csv"

    payload = {
        "generated_at_utc": now_utc_iso(),
        "record_count": len(records),
        "records": [asdict(r) for r in records],
    }
    json_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    with csv_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "source_page",
                "target_url",
                "title",
                "link_text_guess",
                "file_ext",
                "doc_type",
                "tier",
                "instrument_type",
            ],
        )
        writer.writeheader()
        for record in records:
            writer.writerow(asdict(record))

    return json_path, csv_path


def to_manifest_rows(
    downloaded_files: list[tuple[InventoryRecord, Path, str]],
) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for record, file_path, sha256 in downloaded_files:
        stem = Path(urlparse(record.target_url).path).stem or "source"
        source_doc_id = f"ird-{slugify(stem)}-{sha256[:8]}"
        rows.append(
            {
                "source_doc_id": source_doc_id,
                "title": record.title,
                "source_url": record.target_url,
                "doc_type": record.doc_type,
                "instrument_type": record.instrument_type,
                "tier": record.tier,
                "publication_date": "",
                "effective_start_date": "",
                "effective_end_date": "",
                "version_label": "tbd",
                "supersedes_source_doc_id": "",
                "is_draft": "false",
                "authority_weight": "1.00" if record.tier == "A" else "0.80" if record.tier == "B" else "0.60",
                "language": "en",
                "file_name": file_path.name,
                "sha256": sha256,
                "ingested_at_utc": now_utc_iso(),
                "ingested_by": "",
                "notes": f"auto-generated from {record.source_page}",
            }
        )
    return rows


def write_manifest(rows: list[dict[str, str]], out_file: Path) -> Path:
    out_file.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "source_doc_id",
        "title",
        "source_url",
        "doc_type",
        "instrument_type",
        "tier",
        "publication_date",
        "effective_start_date",
        "effective_end_date",
        "version_label",
        "supersedes_source_doc_id",
        "is_draft",
        "authority_weight",
        "language",
        "file_name",
        "sha256",
        "ingested_at_utc",
        "ingested_by",
        "notes",
    ]
    with out_file.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    return out_file


def download_candidates(
    records: list[InventoryRecord],
    download_dir: Path,
    timeout: float,
    tier_filter: set[str] | None,
) -> list[tuple[InventoryRecord, Path, str]]:
    download_dir.mkdir(parents=True, exist_ok=True)
    collected: list[tuple[InventoryRecord, Path, str]] = []

    with httpx.Client(timeout=timeout, follow_redirects=True) as client:
        for record in records:
            if tier_filter and record.tier not in tier_filter:
                continue
            file_name = Path(urlparse(record.target_url).path).name or "downloaded_source"
            safe_name = re.sub(r"[^A-Za-z0-9._-]+", "_", file_name)
            target = download_dir / safe_name
            try:
                resp = client.get(record.target_url)
                resp.raise_for_status()
            except Exception:
                continue
            target.write_bytes(resp.content)
            sha = compute_sha256(target)
            collected.append((record, target, sha))

    return collected


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Phase 1b IRD inventory + download bootstrap")
    parser.add_argument("--hub-url", default=HUB_URL, help="Seed IRD Income Tax hub URL")
    parser.add_argument("--max-pages", type=int, default=120, help="Maximum HTML pages to crawl")
    parser.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT, help="HTTP timeout in seconds")
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=DEFAULT_OUT_DIR,
        help="Directory for inventory JSON/CSV outputs",
    )
    parser.add_argument(
        "--download-dir",
        type=Path,
        default=DEFAULT_DOWNLOAD_DIR,
        help="Directory to save downloaded source files",
    )
    parser.add_argument(
        "--manifest-out",
        type=Path,
        default=DEFAULT_MANIFEST_OUT,
        help="Path to write manifest autofill CSV rows",
    )
    parser.add_argument(
        "--download",
        action="store_true",
        help="Download discovered source candidates and generate manifest autofill",
    )
    parser.add_argument(
        "--tiers",
        default="A,B,C",
        help="Comma-separated tier filter for downloads (e.g., A or A,B)",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    records = crawl_inventory(args.hub_url, args.max_pages, args.timeout)
    json_path, csv_path = write_inventory(records, args.out_dir)
    print(f"Inventory records: {len(records)}")
    print(f"Inventory JSON: {json_path}")
    print(f"Inventory CSV: {csv_path}")

    if not args.download:
        return

    tier_filter = {t.strip().upper() for t in args.tiers.split(",") if t.strip()}
    downloaded = download_candidates(records, args.download_dir, args.timeout, tier_filter)
    rows = to_manifest_rows(downloaded)
    manifest_path = write_manifest(rows, args.manifest_out)
    print(f"Downloaded files: {len(downloaded)}")
    print(f"Manifest autofill CSV: {manifest_path}")


if __name__ == "__main__":
    main()
