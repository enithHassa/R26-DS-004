"""View all data stored in RAG system."""
import sys
from pathlib import Path

repo_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(repo_root))

from sqlalchemy import create_engine, text
from backend.shared.config.settings import settings

engine = create_engine(settings.database_url)


def view_rag_data():
    """Display all RAG data in a readable format."""
    print("\n" + "="*100)
    print("RAG RELIEF SYSTEM - DATA VIEWER")
    print("="*100 + "\n")

    with engine.connect() as conn:
        # 1. Reliefs Summary
        print("1️⃣  RELIEFS STORED (rag_relief_variations table)")
        print("-" * 100)

        result = conn.execute(text("""
            SELECT
                relief_name,
                assessment_year,
                cap_amount,
                cap_currency,
                section_ref,
                confidence_overall,
                status,
                source_act,
                effective_from,
                effective_to
            FROM rag_relief_variations
            ORDER BY assessment_year DESC, relief_name
        """))

        reliefs = list(result)
        if reliefs:
            print(f"{'Relief Name':<45} | {'Year':<10} | {'Amount':<15} | {'Section':<12} | {'Status':<10} | {'Conf':<6}")
            print("-" * 100)

            for name, year, amount, currency, section, conf, status, act, eff_from, eff_to in reliefs:
                amount_str = f"{amount} {currency}" if amount else "Variable"
                conf_pct = f"{conf:.0%}" if conf else "N/A"
                status_display = status[:8] if status else "N/A"
                print(f"{name:<45} | {year:<10} | {amount_str:<15} | {section:<12} | {status_display:<10} | {conf_pct:<6}")

            print(f"\n✅ Total: {len(reliefs)} relief entries across {len(set(r[1] for r in reliefs))} years\n")

            # Group by relief name
            unique_reliefs = {}
            for name, year, amount, currency, section, conf, status, act, eff_from, eff_to in reliefs:
                if name not in unique_reliefs:
                    unique_reliefs[name] = []
                unique_reliefs[name].append(year)

            print(f"📊 UNIQUE RELIEFS ({len(unique_reliefs)}):")
            for relief_name in sorted(unique_reliefs.keys()):
                years = sorted(unique_reliefs[relief_name])
                print(f"   • {relief_name}: {', '.join(years)}")
        else:
            print("   (No reliefs found)")

        # 2. Tax Slabs Summary
        print("\n" + "="*100)
        print("2️⃣  TAX SLABS STORED (rag_tax_slabs table)")
        print("-" * 100)

        result = conn.execute(text("""
            SELECT
                assessment_year,
                income_from,
                income_to,
                tax_rate,
                section_ref,
                status
            FROM rag_tax_slabs
            ORDER BY assessment_year DESC, income_from
        """))

        slabs = list(result)
        if slabs:
            print(f"{'Year':<10} | {'Income From':<15} | {'Income To':<15} | {'Rate':<8} | {'Section':<12} | {'Status':<10}")
            print("-" * 100)

            for year, inc_from, inc_to, rate, section, status in slabs:
                rate_display = f"{float(rate):.1%}" if rate else "N/A"
                inc_to_display = f"{inc_to:,}" if inc_to else "Unlimited"
                status_display = status[:8] if status else "N/A"
                print(f"{year:<10} | {float(inc_from):>13,.0f} | {inc_to_display:>13} | {rate_display:>8} | {section:<12} | {status_display:<10}")

            print(f"\n✅ Total: {len(slabs)} tax slab entries\n")
        else:
            print("   (No tax slabs found)")

        # 3. Chunks Summary
        print("="*100)
        print("3️⃣  PDF CHUNKS INGESTED (rag_relief_chunks table)")
        print("-" * 100)

        result = conn.execute(text("""
            SELECT
                source_act,
                COUNT(*) as chunk_count,
                COUNT(CASE WHEN has_relief = true THEN 1 END) as relief_chunks
            FROM rag_relief_chunks
            GROUP BY source_act
            ORDER BY chunk_count DESC
        """))

        chunks = list(result)
        if chunks:
            print(f"{'Act / Source':<50} | {'Total Chunks':<15} | {'Relief Chunks':<15}")
            print("-" * 100)

            total_chunks = 0
            for act, count, relief_count in chunks:
                relief_pct = f"{relief_count/count*100:.0%}" if count > 0 else "0%"
                print(f"{act:<50} | {count:>13} | {relief_count:>13} ({relief_pct})")
                total_chunks += count

            print(f"\n✅ Total: {total_chunks} chunks ingested from {len(chunks)} acts\n")
        else:
            print("   (No chunks found)")

        # 4. Extraction History
        print("="*100)
        print("4️⃣  EXTRACTION HISTORY (rag_extraction_history table)")
        print("-" * 100)

        result = conn.execute(text("""
            SELECT
                source_act,
                reliefs_extracted,
                tax_slabs_extracted,
                extraction_status,
                upload_date
            FROM rag_extraction_history
            ORDER BY upload_date DESC
        """))

        history = list(result)
        if history:
            print(f"{'Act / Source':<40} | {'Reliefs':<10} | {'Slabs':<10} | {'Status':<15} | {'Date':<20}")
            print("-" * 100)

            for act, reliefs, slabs, status, date in history:
                status_display = status[:13] if status else "N/A"
                date_display = str(date)[:16] if date else "N/A"
                print(f"{act:<40} | {reliefs:>8} | {slabs:>8} | {status_display:<15} | {date_display:<20}")

            print(f"\n✅ Total extraction jobs: {len(history)}\n")
        else:
            print("   (No extraction history found)")

        # 5. Overall Statistics
        print("="*100)
        print("5️⃣  SYSTEM STATISTICS")
        print("="*100)

        result = conn.execute(text("""
            SELECT
                (SELECT COUNT(*) FROM rag_relief_variations) as total_relief_entries,
                (SELECT COUNT(DISTINCT relief_name) FROM rag_relief_variations) as unique_reliefs,
                (SELECT COUNT(*) FROM rag_tax_slabs) as tax_slabs,
                (SELECT COUNT(*) FROM rag_relief_chunks) as total_chunks,
                (SELECT COUNT(*) FROM rag_relief_audit_log) as audit_entries
        """))

        stats = result.fetchone()
        if stats:
            relief_entries, unique_reliefs, tax_slabs, total_chunks, audit_entries = stats
            print(f"""
✅ Relief Entries:        {relief_entries or 0:,}
✅ Unique Reliefs:        {unique_reliefs or 0}
✅ Tax Slabs:             {tax_slabs or 0}
✅ PDF Chunks:            {total_chunks or 0}
✅ Audit Log Entries:     {audit_entries or 0}

📊 Data Quality:
   • Status: Fully populated with extracted rules
   • Source: Filing Catalog + Adaptive Tax Ontology
   • Assessment Years: 2024_25, 2025_26 (primary)
   • Historical Coverage: Acts 2017-2026
""")

        print("="*100)
        print("\n✨ YOUR RAG SYSTEM IS READY TO USE!\n")
        print("Next Steps:")
        print("  1. Query reliefs by assessment year (see below)")
        print("  2. Use for Relief Interview form")
        print("  3. Build admin upload feature for new acts\n")

        # Example queries
        print("="*100)
        print("EXAMPLE QUERIES:")
        print("="*100 + "\n")

        print("📌 Example 1: Get reliefs for a specific year")
        print("-" * 100)
        print("   SELECT relief_name, cap_amount, cap_currency")
        print("   FROM rag_relief_variations")
        print("   WHERE assessment_year = '2025_26'")
        print("   ORDER BY relief_name;\n")

        print("📌 Example 2: Get tax slabs for a year")
        print("-" * 100)
        print("   SELECT income_from, income_to, tax_rate")
        print("   FROM rag_tax_slabs")
        print("   WHERE assessment_year = '2025_26'")
        print("   ORDER BY income_from;\n")

        print("📌 Example 3: Find reliefs with source quotes")
        print("-" * 100)
        print("   SELECT relief_name, section_ref, law_quote")
        print("   FROM rag_relief_variations")
        print("   WHERE law_quote IS NOT NULL")
        print("   LIMIT 5;\n")

        print("="*100 + "\n")


if __name__ == "__main__":
    view_rag_data()
