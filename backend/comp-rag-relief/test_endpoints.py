"""Test RAG endpoints with HTTP requests."""
import sys
sys.path.insert(0, '.')

import requests
from app.services.retriever import ReliefRetriever
from app.services.retriever_state import set_retriever

BASE_URL = "http://127.0.0.1:8006"

# Initialize mock data locally (will be shared with server via global state)
mock_chunks = [
    {
        "chunk_id": "test_001",
        "text": "Personal Relief: A relief of Rs. 1,200,000 for each year of assessment. This relief is available to all resident individuals.",
        "has_relief": True,
        "has_amount": True,
        "relief_amounts": ["1200000"],
        "embedding": [0.1] * 1536,
    },
    {
        "chunk_id": "test_002",
        "text": "Employment Income Relief: For employees, a relief of Rs. 500,000 per year for contributions to approved schemes.",
        "has_relief": True,
        "has_amount": True,
        "relief_amounts": ["500000"],
        "embedding": [0.2] * 1536,
    },
    {
        "chunk_id": "test_003",
        "text": "Business Loss Relief: A taxpayer may carry forward business losses to set off against future business income.",
        "has_relief": True,
        "has_amount": False,
        "relief_amounts": [],
        "embedding": [0.3] * 1536,
    },
    {
        "chunk_id": "test_004",
        "text": "Mortgage Interest Relief: Interest paid on home loans of up to Rs. 3,000,000 is eligible for relief.",
        "has_relief": True,
        "has_amount": True,
        "relief_amounts": ["3000000"],
        "embedding": [0.4] * 1536,
    },
]

# Initialize retriever (note: this only works in this process)
# For the server, we need to use the HTTP endpoint
retriever = ReliefRetriever(mock_chunks)
set_retriever(retriever)

print("=" * 60)
print("Testing RAG Relief Component Endpoints")
print("=" * 60)

# Test 1: Health check
print("\n1. Testing /health endpoint:")
try:
    response = requests.get(f"{BASE_URL}/health", timeout=5)
    print(f"   Status: {response.status_code}")
    print(f"   Response: {response.json()}")
except Exception as e:
    print(f"   ✗ Error: {e}")

# Test 2: Retrieve search (keyword search first - no API calls needed)
print("\n2. Testing /retrieve/keyword endpoint:")
try:
    params = {"query": "personal relief cap", "top_k": 3}
    response = requests.get(f"{BASE_URL}/retrieve/keyword", params=params, timeout=10)
    print(f"   Status: {response.status_code}")
    if response.status_code == 200:
        data = response.json()
        print(f"   Results: {data.get('result_count', 0)} found")
        for i, result in enumerate(data.get('results', []), 1):
            print(f"     {i}. Score: {result['score']:.2f} - {result['text'][:50]}...")
    else:
        print(f"   Error: {response.text[:200]}")
except Exception as e:
    print(f"   ✗ Error: {e}")

# Test 3: Hybrid search (may need initialized retriever)
print("\n3. Testing /retrieve/search endpoint:")
try:
    params = {"query": "employment income relief", "top_k": 3, "alpha": 0.5}
    response = requests.post(f"{BASE_URL}/retrieve/search", params=params, timeout=30)
    print(f"   Status: {response.status_code}")
    if response.status_code == 200:
        data = response.json()
        print(f"   Results: {data.get('result_count', 0)} found")
        for i, result in enumerate(data.get('results', []), 1):
            print(f"     {i}. Score: {result['score']:.2f} - {result['text'][:50]}...")
    else:
        print(f"   Error: {response.text[:200]}")
except Exception as e:
    print(f"   ✗ Error: {e}")

# Test 4: Extract relief
print("\n4. Testing /extract/relief endpoint:")
try:
    params = {"query": "What is the personal relief cap for 2024/25"}
    response = requests.post(f"{BASE_URL}/extract/relief", params=params, timeout=30)
    print(f"   Status: {response.status_code}")
    if response.status_code == 200:
        data = response.json()
        print(f"   Status: {data.get('status')}")
        if 'extracted_relief' in data and data['extracted_relief']:
            print(f"   Relief Name: {data['extracted_relief'].get('name')}")
            print(f"   Cap Amount: {data['extracted_relief'].get('cap_amount')}")
            print(f"   Confidence: {data.get('confidence_scores', {}).get('overall', 0):.0%}")
    else:
        print(f"   Error: {response.text[:200]}")
except Exception as e:
    print(f"   ✗ Error: {e}")

print("\n" + "=" * 60)
