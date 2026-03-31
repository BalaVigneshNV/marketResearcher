"""
analyst.py - Analyst agent for market research workflow.

Reads raw evidence and extracts structured facts:
- claim: The factual statement
- metric: Quantifiable data (if any)
- company: Company name mentioned
- geography: Geographic region (if relevant)
- date: Time reference (if any)
- source: Source URL
- evidence_snippet: Supporting text
"""

import os
import json
import logging
from typing import List, Dict, Any
from openai import AzureOpenAI
from dotenv import load_dotenv

import database_v2

load_dotenv()
logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)


def get_openai_client() -> AzureOpenAI:
    """Get Azure OpenAI client instance."""
    api_key = os.getenv("AZURE_OPENAI_API_KEY")
    endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
    api_version = os.getenv("AZURE_OPENAI_API_VERSION")

    if not api_key:
        raise EnvironmentError("AZURE_OPENAI_API_KEY must be set in .env")
    if not endpoint:
        raise EnvironmentError("AZURE_OPENAI_ENDPOINT must be set in .env")
    if not api_version:
        raise EnvironmentError("AZURE_OPENAI_API_VERSION must be set in .env")

    return AzureOpenAI(
        api_key=api_key,
        azure_endpoint=endpoint,
        api_version=api_version,
    )


def extract_facts_from_content(
    client_name: str,
    content: str,
    source_url: str,
    max_facts: int = 5,
) -> List[Dict[str, Any]]:
    """
    Use OpenAI to extract structured facts from content.

    Args:
        client_name: Company being researched
        content: Text content to analyze
        source_url: Source URL for citation
        max_facts: Maximum number of facts to extract

    Returns:
        List of fact dictionaries
    """
    client = get_openai_client()

    # Truncate content to avoid token limits (keep first 3000 chars)
    truncated_content = content[:3000] + ("..." if len(content) > 3000 else "")

    prompt = f"""
You are a professional market research analyst. Extract structured facts from the following content about {client_name}.

For each significant fact, identify:
- claim: A clear, factual statement
- metric: Any quantifiable data (revenue, growth %, market share, number of products, etc.)
- company: Company name (could be {client_name} or competitors)
- geography: Geographic region if mentioned (e.g., "United States", "Europe", "Global")
- date: Time reference if mentioned (e.g., "Q4 2024", "2025", "March 2024")
- fact_type: Category (e.g., "market_size", "growth_rate", "product_launch", "partnership", "financial", "strategic")
- confidence: How confident are you in this fact (0.0-1.0)

Extract up to {max_facts} significant facts that would be valuable for market research and lead conversion.

Content:
{truncated_content}

Source URL: {source_url}

Respond ONLY with valid JSON in this exact format:
{{
  "facts": [
    {{
      "claim": "The claim text",
      "metric": "Specific number or null",
      "company": "Company name",
      "geography": "Region or null",
      "date": "Time reference or null",
      "evidence_snippet": "Relevant quote from content",
      "fact_type": "category",
      "confidence": 0.9
    }},
    ...
  ]
}}
""".strip()

    try:
        response = client.chat.completions.create(
            model=os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME", "gpt-4o"),
            messages=[
                {
                    "role": "system",
                    "content": "You are a market research analyst expert at extracting structured facts. Always respond with valid JSON.",
                },
                {"role": "user", "content": prompt},
            ],
            temperature=0.2,
            response_format={"type": "json_object"},
        )

        result = json.loads(response.choices[0].message.content)
        facts = result.get("facts", [])

        # Add source URL to each fact
        for fact in facts:
            fact["source_url"] = source_url

        return facts

    except Exception as e:
        log.warning(f"[Analyst] Error extracting facts: {e}")
        return []


def analyze_evidence(
    session_id: int,
    client_name: str,
    raw_evidence: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """
    Analyze all raw evidence and extract structured facts.

    Args:
        session_id: Database session ID
        client_name: Company being researched
        raw_evidence: List of evidence from Researcher

    Returns:
        List of structured facts that were stored in database
    """
    all_facts = []

    log.info(f"[Analyst] Analyzing {len(raw_evidence)} pieces of evidence...")

    for evidence in raw_evidence:
        log.info(f"[Analyst] Processing: {evidence.get('title', '')[:60]}...")

        # Extract facts from this evidence
        facts = extract_facts_from_content(
            client_name=client_name,
            content=evidence.get("content", ""),
            source_url=evidence.get("url", ""),
            max_facts=5,
        )

        # Store each fact in database
        for fact in facts:
            try:
                fact_id = database_v2.add_structured_fact(
                    session_id=session_id,
                    evidence_id=evidence.get("id"),
                    claim=fact.get("claim", ""),
                    metric=fact.get("metric"),
                    company=fact.get("company"),
                    geography=fact.get("geography"),
                    date=fact.get("date"),
                    source_url=fact.get("source_url"),
                    evidence_snippet=fact.get("evidence_snippet", ""),
                    fact_type=fact.get("fact_type", "general"),
                    confidence=fact.get("confidence", 0.8),
                )

                fact["id"] = fact_id
                all_facts.append(fact)

                log.info(f"[Analyst]   → Fact: {fact.get('claim', '')[:80]}...")

            except Exception as e:
                log.error(f"[Analyst] Database error storing fact: {e}")

    log.info(f"[Analyst] Completed. Total facts extracted: {len(all_facts)}")
    return all_facts


if __name__ == "__main__":
    # Test the analyst
    import database_v2

    database_v2.init_db()

    # Create a test session
    client_id = database_v2.add_client("Test Company", "Test Owner")
    session_id = database_v2.create_research_session(client_id, "Test Research")

    # Add some test evidence
    evidence_id = database_v2.add_raw_evidence(
        session_id=session_id,
        url="https://example.com/article",
        title="Test Article",
        content="Tesla reported $96.8 billion in revenue for 2023, representing 19% year-over-year growth. The company delivered over 1.8 million vehicles globally.",
        snippet="Tesla reported strong financial results...",
        source_type="search",
        fetch_method="requests",
    )

    evidence = [
        {
            "id": evidence_id,
            "url": "https://example.com/article",
            "title": "Test Article",
            "content": "Tesla reported $96.8 billion in revenue for 2023, representing 19% year-over-year growth. The company delivered over 1.8 million vehicles globally.",
        }
    ]

    # Test fact extraction
    facts = analyze_evidence(session_id, "Tesla Inc.", evidence)

    print(f"\nExtracted {len(facts)} facts:")
    for fact in facts:
        print(f"  - {fact['claim']}")
