"""Find chunks that actually contain relief definitions (no API cost)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from sqlalchemy import create_engine, text
from backend.shared.config.settings import settings

engine = create_engine(settings.database_url)

print("\n" + "="*100)
print("SEARCHING FOR RELIEF-RICH CHUNKS (No API Cost)")
print("="*100 + "\n")

with engine.connect() as conn:
    # Search for chunks with relief keywords
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

    chunks = list(result)
    print(f"Found {len(chunks)} chunks with relief keywords:\n")

    for i, (cid, text_snippet, page) in enumerate(chunks, 1):
        print(f"Chunk {i} (Page {page}, ID: {str(cid)[:8]}...):")
        print(f"  {text_snippet[:180]}\n")

    if chunks:
        print("\n✅ These chunks should be extracted (they contain actual relief data)")
        print(f"\n📊 Next step: Extract ONLY these {len(chunks)} chunks (~${len(chunks) * 0.01:.2f} cost)")
