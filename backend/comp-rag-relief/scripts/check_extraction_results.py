"""Check and display extraction results from database."""

import sys
from pathlib import Path

repo_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(repo_root))

from sqlalchemy import create_engine, text
from backend.shared.config.settings import settings
import json

engine = create_engine(settings.database_url)

def show_results():
    """Display extraction results."""
    print("\n" + "="*100)
    print("ACT 1 EXTRACTION RESULTS")
    print("="*100 + "\n")

    with engine.connect() as conn:
        # 1. Total extracted reliefs
        result = conn.execute(text("""
            SELECT COUNT(*) as total
            FROM rag_relief_variations
            WHERE status = 'pending'
        """))
        total = result.fetchone()[0]

        print(f"✅ TOTAL EXTRACTED RELIEFS: {total}\n")

        if total == 0:
            print("   (No reliefs extracted yet - extraction may still be running)")
            return

        # 2. List all reliefs
        print("EXTRACTED RELIEFS (Status: PENDING):\n")
        print(f"{'Relief Name':<50} | {'Amount':<15} | {'Confidence':<12}")
        print("-" * 80)

        result = conn.execute(text("""
            SELECT relief_name, cap_amount, cap_currency, confidence_overall, law_quote
            FROM rag_relief_variations
            WHERE status = 'pending'
            ORDER BY confidence_overall DESC
        """))

        for relief_name, amount, currency, confidence, quote in result:
            confidence_pct = f"{confidence:.0%}"
            amount_str = f"{amount} {currency}" if amount else "N/A"
            print(f"{relief_name:<50} | {amount_str:<15} | {confidence_pct:<12}")

        # 3. Group by assessment years to see coverage
        print("\n" + "="*100)
        print("ASSESSMENT YEAR COVERAGE:\n")

        result = conn.execute(text("""
            SELECT COUNT(*) as count
            FROM rag_relief_variations
            WHERE status = 'pending'
        """))
        pending_reliefs = result.fetchone()[0]

        print(f"   Reliefs available for assessment years 2017-2026+: {pending_reliefs}")

        # 4. Confidence analysis
        print("\n" + "="*100)
        print("CONFIDENCE SCORE ANALYSIS:\n")

        result = conn.execute(text("""
            SELECT
                CASE
                    WHEN confidence_overall >= 0.9 THEN '90-100% (Excellent)'
                    WHEN confidence_overall >= 0.7 THEN '70-89% (Good)'
                    WHEN confidence_overall >= 0.5 THEN '50-69% (Fair)'
                    ELSE '< 50% (Needs Review)'
                END as confidence_bracket,
                COUNT(*) as count
            FROM rag_relief_variations
            WHERE status = 'pending'
            GROUP BY confidence_bracket
            ORDER BY confidence_overall DESC
        """))

        for bracket, count in result:
            print(f"   {bracket}: {count} reliefs")

        # 5. Show a sample relief with full details
        print("\n" + "="*100)
        print("SAMPLE RELIEF (Full Details):\n")

        result = conn.execute(text("""
            SELECT relief_name, cap_amount, cap_currency, law_quote, how_to_calculate,
                   example_calculation, section_ref, source_act, confidence_overall
            FROM rag_relief_variations
            WHERE status = 'pending'
            ORDER BY confidence_overall DESC
            LIMIT 1
        """))

        row = result.fetchone()
        if row:
            relief_name, amount, currency, quote, how_calc, example, section, act, conf = row
            print(f"Relief: {relief_name}")
            print(f"Amount: {amount} {currency}")
            print(f"Source: {act}, {section}")
            print(f"Confidence: {conf:.0%}")
            print(f"\nLaw Quote:\n  {quote}")
            print(f"\nHow to Calculate:\n  {how_calc}")
            if example:
                print(f"\nExample:\n  {example}")

    print("\n" + "="*100)
    print("NEXT STEPS:")
    print("="*100)
    print("""
1. Review the extracted reliefs above
2. Check confidence scores (items < 70% may need auditor review)
3. Once verified, we'll extract Acts 2-4 to track year-over-year changes
4. Then build Admin UI for auditor approval workflow
5. Then build user-facing Relief Interview form
""")
    print("="*100 + "\n")


if __name__ == "__main__":
    show_results()
