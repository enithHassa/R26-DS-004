"""Load extracted relief rules from Filing Catalog into RAG system."""
import sys
import json
from pathlib import Path
from uuid import uuid4

repo_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(repo_root))

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session
from backend.shared.config.settings import settings

engine = create_engine(settings.database_url)


def load_filing_catalog():
    """Load relief rules from filing_component_catalog_v1.json."""
    print("\n" + "="*90)
    print("LOADING ALL EXTRACTED RELIEFS FROM FILING CATALOG")
    print("="*90 + "\n")

    catalog_file = repo_root / "models" / "adaptive-tax" / "fixtures" / "filing_component_catalog_v1.json"

    if not catalog_file.exists():
        print(f"❌ File not found: {catalog_file}")
        return

    print(f"1️⃣  Loading from: filing_component_catalog_v1.json")

    with open(catalog_file) as f:
        data = json.load(f)

    # Filter for relief-related components
    all_components = data.get("components", [])

    relief_keywords = {
        "relief", "donation", "solar", "rent", "senior", "personal",
        "charitable", "qp_approved", "fifth", "schedule", "expenditure"
    }

    relief_components = [
        c for c in all_components
        if any(kw in str(c).lower() for kw in relief_keywords)
    ]

    print(f"   Found {len(relief_components)} relief-related rules\n")

    loaded_count = 0
    with Session(engine) as session:
        for component in relief_components:
            try:
                # Build relief record from component
                comp_id = component.get("component_id", "")
                display_name = component.get("display_name", "")
                section = component.get("section", "")
                paragraph = component.get("paragraph")
                source_quote = component.get("source_quote", "")
                reason_short = component.get("reason_short", "")
                source_doc_id = component.get("source_doc_id", "IRD Act 2017")
                ya_effective = component.get("ya_effective", [])
                effective_from = component.get("effective_from")
                effective_to = component.get("effective_to")
                legal_confidence = component.get("legal_confidence", "pending")
                confidence_map = {"high": 0.9, "medium": 0.7, "low": 0.5, "pending": 0.3}
                conf_score = confidence_map.get(legal_confidence, 0.7)

                # Skip if no useful data
                if not display_name or not source_quote:
                    continue

                # Build section reference
                section_ref = section
                if paragraph:
                    section_ref = f"{section}({paragraph})"

                insert_query = text("""
                    INSERT INTO rag_relief_variations (
                        id, relief_name, assessment_year, source_act, section_ref,
                        law_quote, how_to_calculate,
                        confidence_amount, confidence_explanation,
                        confidence_overall, status, extracted_by,
                        effective_from, effective_to
                    ) VALUES (
                        :id, :name, :year, :act, :section,
                        :quote, :how_calc,
                        :conf_amount, :conf_explain,
                        :conf_overall, :status, :extracted_by,
                        :eff_from, :eff_to
                    )
                """)

                # Load one row per assessment year
                for year in ya_effective:
                    session.execute(
                        insert_query,
                        {
                            "id": str(uuid4()),
                            "name": display_name,
                            "year": year,
                            "act": source_doc_id,
                            "section": section_ref,
                            "quote": source_quote,
                            "how_calc": reason_short or display_name,
                            "conf_amount": conf_score,
                            "conf_explain": conf_score,
                            "conf_overall": conf_score,
                            "status": "approved",
                            "extracted_by": "filing-catalog-v1",
                            "eff_from": effective_from,
                            "eff_to": effective_to,
                        },
                    )
                    session.commit()
                    loaded_count += 1

                print(f"   ✓ {display_name}")

            except Exception as e:
                print(f"   ✗ Error: {str(e)[:100]}")
                session.rollback()

    # Show results
    print(f"\n" + "="*90)
    print(f"2️⃣  LOADED {loaded_count} RELIEF ENTRIES INTO RAG SYSTEM")
    print("="*90 + "\n")

    with engine.connect() as conn:
        result = conn.execute(text("""
            SELECT COUNT(DISTINCT relief_name) as relief_count,
                   COUNT(*) as total_entries
            FROM rag_relief_variations
            WHERE status = 'approved'
        """))
        row = result.fetchone()
        if row:
            relief_count, total_entries = row
            print(f"✅ Database now contains:")
            print(f"   • {relief_count} unique reliefs")
            print(f"   • {total_entries} total year-specific entries (with history)")
            print(f"   • All extracted from Acts 2017-2026")
            print(f"   • Ready for Relief Interview form")

    print("\n" + "="*90 + "\n")


if __name__ == "__main__":
    load_filing_catalog()
