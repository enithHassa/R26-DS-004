"""Smart extraction - ONLY relief-rich chunks (minimal API cost)."""
import sys
import json
import logging
from uuid import uuid4
from pathlib import Path

repo_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(repo_root))
sys.path.insert(0, str(repo_root / "backend" / "comp-rag-relief" / "app"))

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session
from backend.shared.config.settings import settings
from config import get_rag_relief_settings
from routers.extract_improved import improved_extract_relief

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

rag_settings = get_rag_relief_settings()
engine = create_engine(settings.database_url)


def get_relief_rich_chunks():
    """Get ONLY the 10 chunks known to contain reliefs."""
    relief_chunk_ids = [
        'd2b1ff17', '66d008d1', '89d47a93', '1c5c49c4', 'e50ce9f8',
        'a315c9fd', 'e57741cb', '80a06818', '1d400b02', '021b4494'
    ]

    with engine.connect() as conn:
        result = conn.execute(text("""
            SELECT chunk_id, text, page_number
            FROM rag_relief_chunks
            WHERE source_act ILIKE '%2017%'
            AND (
                LOWER(text) LIKE '%personal relief%'
                OR LOWER(text) LIKE '%employment%'
                OR LOWER(text) LIKE '%relief%amount%'
                OR LOWER(text) LIKE '%section 2%'
                OR LOWER(text) LIKE '%schedule%'
                OR LOWER(text) LIKE '%500000%'
                OR LOWER(text) LIKE '%700000%'
            )
            LIMIT 10
        """))
        return [{"chunk_id": str(row[0]), "text": row[1], "page": row[2]} for row in result]


def save_relief(session: Session, extracted: dict, source_act: str):
    """Save extracted relief to database."""
    try:
        if extracted.get("name") == "Unknown":
            return False

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
    """Extract from relief-rich chunks only."""
    print("\n" + "="*80)
    print("SMART EXTRACTION - RELIEF-RICH CHUNKS ONLY")
    print("="*80 + "\n")

    # Get chunks
    chunks = get_relief_rich_chunks()
    print(f"1️⃣  Loading relief-rich chunks...")
    print(f"   Found {len(chunks)} chunks with relief keywords\n")

    if not chunks:
        print("   ❌ NO RELIEF CHUNKS FOUND!")
        return

    # Extract
    print(f"2️⃣  EXTRACTING RELIEFS...")
    print(f"   (Estimated cost: $0.10-0.20)\n")

    extracted_count = 0
    with Session(engine) as session:
        for i, chunk in enumerate(chunks, 1):
            print(f"   [{i}/{len(chunks)}] {chunk['text'][:60]}...")

            extracted = improved_extract_relief(
                context=chunk["text"],
                query="Extract tax reliefs with amounts"
            )

            if extracted.get("name") and extracted.get("name") != "Unknown":
                print(f"      ✓ Found: {extracted.get('name')} ({extracted.get('cap_amount')} {extracted.get('currency')})")
                if save_relief(session, extracted, "Inland Revenue Act No. 24 of 2017"):
                    extracted_count += 1
            else:
                print(f"      - No relief found")

    # Results
    print("\n" + "="*80)
    print(f"3️⃣  EXTRACTION COMPLETE - {extracted_count} RELIEFS SAVED")
    print("="*80 + "\n")

    # Show what's in database
    with engine.connect() as conn:
        result = conn.execute(text("""
            SELECT relief_name, cap_amount, cap_currency, confidence_overall
            FROM rag_relief_variations
            WHERE status = 'pending'
            ORDER BY confidence_overall DESC
        """))

        reliefs = list(result)
        if reliefs:
            print("EXTRACTED RELIEFS IN DATABASE:\n")
            for relief_name, amount, currency, conf in reliefs:
                print(f"  ✓ {relief_name}")
                print(f"    Amount: {amount} {currency} | Confidence: {conf:.0%}\n")
        else:
            print("No reliefs in database yet")

    print("="*80 + "\n")


if __name__ == "__main__":
    main()
