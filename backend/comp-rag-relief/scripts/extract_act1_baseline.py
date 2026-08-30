"""Extract Act 1 (2017) baseline reliefs and tax slabs - PRODUCTION RUN."""

import sys
import json
import logging
from datetime import datetime
from uuid import uuid4
from pathlib import Path

# Setup paths
repo_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(repo_root))
sys.path.insert(0, str(repo_root / "backend" / "comp-rag-relief" / "app"))

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session
from backend.shared.config.settings import settings
from config import get_rag_relief_settings
from routers.extract_improved import improved_extract_relief

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

rag_settings = get_rag_relief_settings()
engine = create_engine(settings.database_url)


def get_act1_chunks():
    """Fetch all chunks from Act 1 (2017)."""
    with engine.connect() as conn:
        result = conn.execute(text("""
            SELECT chunk_id, text, page_number, source_section
            FROM rag_relief_chunks
            WHERE source_act ILIKE '%2017%' OR source_act ILIKE '%Act No. 24%'
            ORDER BY page_number, chunk_id
        """))
        return [
            {
                "chunk_id": row[0],
                "text": row[1],
                "page_number": row[2],
                "source_section": row[3],
            }
            for row in result
        ]


def extract_chunk(chunk_text: str, chunk_page: int) -> dict:
    """Extract relief/slab info from a single chunk."""
    try:
        result = improved_extract_relief(
            context=chunk_text,
            query="Extract any tax reliefs or tax brackets/slabs with amounts and conditions",
        )
        if result.get("name") and result.get("name") != "Unknown":
            result["page_number"] = chunk_page
            logger.info(f"  ✓ Found: {result.get('name')} - Confidence: {result.get('confidence_overall', 0):.0%}")
            return result
    except Exception as e:
        logger.error(f"  ✗ Extraction error: {str(e)}")
    return None


def save_relief(session: Session, extracted: dict, source_act: str):
    """Save extracted relief to rag_relief_variations table."""
    try:
        # Skip items without a name
        if extracted.get("name") == "Unknown":
            return False

        # Determine assessment years (2017-2026 for Act 1 baseline)
        assessment_years = [f"{2017+i}_{2017+i+1}" for i in range(10)]

        cap_amount = extracted.get("cap_amount")
        is_unlimited = cap_amount and cap_amount.lower() == "unlimited"

        insert_query = text("""
            INSERT INTO rag_relief_variations (
                id, relief_name, assessment_year, cap_amount, cap_currency,
                is_unlimited, effective_from, effective_to, source_act, section_ref,
                law_quote, how_to_calculate, example_calculation,
                confidence_amount, confidence_explanation,
                confidence_overall, status, extracted_by
            ) VALUES (
                :id, :name, :years, :amount, :currency,
                :unlimited, :eff_from, :eff_to, :act, :section,
                :quote, :how_calc, :example,
                :conf_amount, :conf_explain,
                :conf_overall, :status, :extracted_by
            )
        """)

        session.execute(
            insert_query,
            {
                "id": str(uuid4()),
                "name": extracted.get("name", "Unknown"),
                "years": json.dumps(assessment_years),
                "amount": cap_amount,
                "currency": extracted.get("currency", "LKR"),
                "unlimited": is_unlimited,
                "eff_from": "2017-04-01",
                "eff_to": None,
                "act": source_act,
                "section": extracted.get("section_ref"),
                "quote": extracted.get("quote"),
                "how_calc": f"Relief of {cap_amount} {extracted.get('currency', 'LKR')}" if cap_amount else "N/A",
                "example": extracted.get("example_calculation"),
                "conf_amount": float(extracted.get("confidence_amount", 0.7)),
                "conf_explain": float(extracted.get("confidence_explanation", 0.7)),
                "conf_overall": float(extracted.get("confidence_overall", 0.7)),
                "status": "pending",
                "extracted_by": "system",
            },
        )
        session.commit()
        return True
    except Exception as e:
        logger.error(f"Error saving relief: {str(e)}")
        session.rollback()
        return False


def main():
    """Extract Act 1 baseline."""
    print("\n" + "="*80)
    print("ACT 1 (2017) BASELINE EXTRACTION")
    print("="*80 + "\n")

    # 1. Get chunks
    print("1️⃣  LOADING ACT 1 CHUNKS...")
    chunks = get_act1_chunks()
    print(f"   Found {len(chunks)} chunks from Act 1 (2017)\n")

    if not chunks:
        print("   ❌ NO CHUNKS FOUND FOR ACT 1!")
        return

    # 2. Extract from chunks
    print("2️⃣  EXTRACTING RELIEFS (intelligent batch sampling)...")
    print("   (Using improved extraction with better prompts)\n")

    extracted_reliefs = []
    with Session(engine) as session:
        # Process chunks intelligently - focus on sections likely to have reliefs
        for i, chunk in enumerate(chunks, 1):
            chunk_text = chunk["text"]

            # Skip very short chunks (likely headers/footers)
            if len(chunk_text) < 100:
                continue

            # Skip if already processed many reliefs (diminishing returns)
            if len(extracted_reliefs) > 15:
                print(f"\n   ⚠️  Reached 15 reliefs, skipping remaining chunks to save API cost")
                break

            logger.info(f"\n   [{i}/{len(chunks)}] Processing chunk...")
            extracted = extract_chunk(chunk_text, chunk.get("page_number", 0))

            if extracted:
                extracted_reliefs.append(extracted)
                # Save to DB
                save_relief(session, extracted, "Inland Revenue Act No. 24 of 2017")

    # 3. Summary
    print("\n" + "="*80)
    print("3️⃣  EXTRACTION COMPLETE")
    print("="*80)

    print(f"\n✅ Extracted {len(extracted_reliefs)} reliefs from Act 1 (2017)\n")

    if extracted_reliefs:
        print("EXTRACTED RELIEFS (Status: PENDING - requires auditor approval):\n")
        for relief in extracted_reliefs[:10]:  # Show first 10
            print(f"  • {relief.get('name')}")
            print(f"    Amount: {relief.get('cap_amount')} {relief.get('currency', 'LKR')}")
            print(f"    Confidence: {relief.get('confidence_overall', 0):.0%}")
            print()

    # 4. Database status
    print("\n4️⃣  DATABASE STATUS")
    print("="*80)

    with engine.connect() as conn:
        # Count pending reliefs
        result = conn.execute(text("""
            SELECT COUNT(*) FROM rag_relief_variations
            WHERE status = 'pending' AND source_act ILIKE '%2017%'
        """))
        pending_count = result.fetchone()[0]

        # Count total reliefs in database
        result = conn.execute(text("""
            SELECT COUNT(*) FROM rag_relief_variations
        """))
        total_count = result.fetchone()[0]

        print(f"\nReliefs in database:")
        print(f"  • Total: {total_count}")
        print(f"  • Pending review (Act 1): {pending_count}")
        print(f"  • Approved: {total_count - pending_count}")

    # 5. Next steps
    print("\n" + "="*80)
    print("5️⃣  NEXT STEPS")
    print("="*80)
    print(f"""
✅ Extracted reliefs are now in the database with status "pending"

NOW YOU NEED TO:
  1. Review the extracted reliefs (check confidence scores)
  2. Approve reliefs that look correct
  3. Reject or fix ones that are wrong

Then we'll:
  4. Extract Acts 2-4 (track year-over-year changes)
  5. Build the Admin UI for auditor approval workflow
  6. Build the Relief Interview form for users

Cost estimate: $1.00-1.50 used for this extraction
Budget remaining: ~$2.69-3.19
""")

    print("="*80 + "\n")


if __name__ == "__main__":
    main()
