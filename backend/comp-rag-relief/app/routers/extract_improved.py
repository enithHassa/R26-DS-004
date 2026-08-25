"""IMPROVED extraction with better error handling and prompt."""

import json
import logging
from typing import Any, Optional
from openai import OpenAI
try:
    from app.config import get_rag_relief_settings
except ImportError:
    from config import get_rag_relief_settings

logger = logging.getLogger(__name__)
settings = get_rag_relief_settings()

def improved_extract_relief(context: str, query: str) -> dict[str, Any]:
    """
    Improved extraction with:
    - Better error handling
    - More permissive prompt
    - Logging for debugging
    - No hard requirements on fields
    """

    # IMPROVED PROMPT: More permissive, handles unknowns better
    extraction_prompt = f"""Extract tax relief information from this text. Be generous in extraction - return what you find.

TEXT:
{context}

QUERY: {query}

Return JSON with ANY of these fields you can extract (leave out fields if not found):
- name: Relief name if mentioned
- cap_amount: Amount (number only, e.g. "500000" or "25" for percentage)
- currency: Currency type ("LKR" or "%")
- effective_from: Start date if mentioned (YYYY-MM-DD)
- assessment_years: Years if mentioned as list
- section_ref: Section number if mentioned
- quote: Exact quote containing relief info
- source_act: Act name if mentioned

Confidence scores (0.0-1.0) - be realistic:
- confidence_name: How confident relief name is stated
- confidence_amount: How confident amount is stated
- confidence_date: How confident effective date is stated

Example output:
{{"name": "Personal Relief", "cap_amount": "500000", "currency": "LKR", "confidence_name": 0.95, "confidence_amount": 0.93, "confidence_date": 0.80}}

Or if uncertain:
{{"name": "Unknown", "confidence_name": 0.3}}

Return ONLY JSON (no text before/after).
"""

    try:
        client = OpenAI(api_key=settings.OPENAI_API_KEY)

        response = client.chat.completions.create(
            model=settings.OPENAI_MODEL,
            max_tokens=1000,
            temperature=0.2,
            messages=[{"role": "user", "content": extraction_prompt}],
        )

        extraction_text = response.choices[0].message.content
        logger.info(f"Raw extraction response: {extraction_text[:200]}")

        # Parse JSON - more robust with multiline handling
        try:
            # Handle potential JSON arrays
            if extraction_text.strip().startswith("["):
                json_start = 0
                json_end = extraction_text.rfind("]") + 1
            else:
                json_start = extraction_text.find("{")
                json_end = extraction_text.rfind("}") + 1

            if json_start < 0 or json_end <= json_start:
                logger.warning("No JSON found in response")
                return {"name": "Unknown", "confidence_name": 0.0}

            json_text = extraction_text[json_start:json_end]
            # Remove line breaks within the JSON to avoid parsing issues
            json_text = json_text.replace("\n", " ").replace("\r", " ")
            # Collapse multiple spaces
            json_text = " ".join(json_text.split())

            extracted_json = json.loads(json_text)
            logger.info(f"Parsed JSON: {extracted_json}")

            # If we got an array, take the first element
            if isinstance(extracted_json, list):
                extracted_json = extracted_json[0] if extracted_json else {}

        except json.JSONDecodeError as e:
            logger.error(f"JSON parse error: {e}, response: {extraction_text[:200]}")
            return {"name": "Unknown", "confidence_name": 0.0}

        # Safely get confidence scores with defaults
        conf_name = float(extracted_json.get("confidence_name") or 0.7)
        conf_amount = float(extracted_json.get("confidence_amount") or 0.7)
        conf_date = float(extracted_json.get("confidence_date") or 0.7)

        conf_overall = (conf_name + conf_amount + conf_date) / 3

        return {
            "name": extracted_json.get("name") or "Unknown",
            "cap_amount": extracted_json.get("cap_amount"),
            "currency": extracted_json.get("currency") or "Unknown",
            "effective_from": extracted_json.get("effective_from"),
            "assessment_years": extracted_json.get("assessment_years") or [],
            "section_ref": extracted_json.get("section_ref") or "Unknown",
            "quote": extracted_json.get("quote") or "N/A",
            "source_act": extracted_json.get("source_act") or "Unknown",
            "confidence_name": min(max(conf_name, 0.0), 1.0),
            "confidence_amount": min(max(conf_amount, 0.0), 1.0),
            "confidence_date": min(max(conf_date, 0.0), 1.0),
            "confidence_overall": min(max(conf_overall, 0.0), 1.0),
        }

    except Exception as e:
        logger.error(f"Extraction error: {str(e)}", exc_info=True)
        return {"name": "Unknown", "confidence_name": 0.0, "error": str(e)}


def test_improved_extraction():
    """Test on a few samples to verify it works before scaling."""
    test_contexts = [
        "Personal Relief\nRs. 500,000 for each year of assessment under Fifth Schedule, para 2(a)",
        "Employment Income Relief\nRs. 700,000 for each year under FIFTH SCHEDULE, Section 2(b)",
        "Some random procedural text about tax calculation methods and income determination",
    ]

    print("\n" + "="*80)
    print("TESTING IMPROVED EXTRACTION")
    print("="*80 + "\n")

    for i, context in enumerate(test_contexts, 1):
        print(f"Test {i}:")
        print(f"Input: {context[:100]}...")
        result = improved_extract_relief(context, "What reliefs apply?")
        print(f"Result: {result.get('name')} - Confidence: {result.get('confidence_overall', 0):.0%}")
        print()


if __name__ == "__main__":
    test_improved_extraction()
