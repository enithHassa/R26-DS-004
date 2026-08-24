#!/usr/bin/env python3
"""Phase 3 Testing: Load PDF → Chunk → Embed → Retrieve"""

import sys
from pathlib import Path

# Add paths
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app.services.pdf_loader import PDFLoader
from app.services.chunker import ReliefChunker

# Test PDF path (use first IR_Act_No_24_2017_E.pdf found)
PDF_PATH = Path("models/adaptive-tax/relief-interview/review/catalog-admin-uploads/2e949afb-ec17-4a2a-afb6-00a314e4b6b7_IR_Act_No_24_2017_E.pdf")

print("=" * 80)
print("PHASE 3 TESTING: RAG Relief Component")
print("=" * 80)

# ============================================================================
# STEP 1: LOAD PDF (FREE — no API cost)
# ============================================================================
print("\n📄 STEP 1: Loading PDF...")
print(f"   Path: {PDF_PATH.name}")
if PDF_PATH.exists():
    print(f"   Size: {PDF_PATH.stat().st_size / 1024 / 1024:.2f} MB")
else:
    print(f"❌ File not found: {PDF_PATH}")
    sys.exit(1)

try:
    loader = PDFLoader()
    pdf_data = loader.load_pdf(PDF_PATH)

    print(f"✅ SUCCESS!")
    print(f"   Pages: {pdf_data['pages']}")
    print(f"   Text length: {len(pdf_data['text'])} chars")
    print(f"   First 150 chars: {pdf_data['text'][:150]}...")
except Exception as e:
    print(f"❌ FAILED: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# ============================================================================
# STEP 2: CHUNK TEXT (FREE — no API cost)
# ============================================================================
print("\n✂️  STEP 2: Chunking PDF...")
print(f"   Target chunk size: 800 tokens")

try:
    chunker = ReliefChunker()
    chunks = chunker.chunk_text(
        pdf_data["text"],
        chunk_size=800,
        overlap=100,
        by_schedule=True,
    )

    print(f"✅ SUCCESS!")
    print(f"   Total chunks: {len(chunks)}")
    print(f"\n   Sample chunks:")
    for i, chunk in enumerate(chunks[:3]):
        print(f"\n   Chunk {i+1} ({chunk['chunk_id']}):")
        print(f"   ├─ Section: {chunk.get('section', 'N/A')}")
        print(f"   ├─ Has relief: {chunk['has_relief']}")
        print(f"   ├─ Has amount: {chunk['has_amount']}")
        print(f"   ├─ Relief amounts: {chunk['relief_amounts']}")
        print(f"   └─ Text preview: {chunk['text'][:120]}...")

    print(f"\n   [Showing first 3 of {len(chunks)} chunks]")

except Exception as e:
    print(f"❌ FAILED: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# ============================================================================
# STEP 3: EMBEDDING CHECK (⚠️ WILL USE OPENAI CREDITS)
# ============================================================================
print("\n" + "=" * 80)
print("⚠️  NEXT STEP: EMBEDDING (will use your OpenAI credits)")
print("=" * 80)
print(f"\nEstimated cost:")
print(f"  - Chunks to embed: {len(chunks)}")
print(f"  - Average tokens per chunk: ~600")
print(f"  - Total tokens: ~{len(chunks) * 600:,}")
print(f"  - Estimated cost: ~${(len(chunks) * 600 * 0.02 / 1_000_000):.4f}")
print(f"\n💳 Your current credit limit: VERY LOW")
print(f"\n⏸️  STOPPING HERE for your safety!")
print(f"\nYou have 3 options:")
print(f"  1. BUY MORE OPENAI CREDITS → Then embed & test retrieval")
print(f"  2. Use free open-source embeddings (lower accuracy, but free)")
print(f"  3. Just validate chunking is working (we're done with FREE testing)")

print("\n" + "=" * 80)
print("✅ PHASE 3 SUMMARY (FREE PART)")
print("=" * 80)
print(f"✅ PDF loaded successfully: {pdf_data['pages']} pages")
print(f"✅ Chunking works: {len(chunks)} chunks created")
print(f"✅ Relief detection: {sum(1 for c in chunks if c['has_relief'])} chunks have reliefs")
print(f"✅ Amount detection: {sum(1 for c in chunks if c['has_amount'])} chunks have amounts")
print(f"\n⏸️  READY FOR EMBEDDING (awaiting your decision on credits)")
print("=" * 80)
