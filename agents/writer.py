"""
writer.py - Writer agent for market research workflow.

Compiles the final market research report with citations from structured facts.
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


def write_report(
    session_id: int,
    client_name: str,
    topic: str,
    outline: str,
    structured_facts: List[Dict[str, Any]],
) -> Dict[str, str]:
    """
    Generate a comprehensive market research report.

    Args:
        session_id: Database session ID
        client_name: Company name
        topic: Research topic
        outline: Report outline from Planner
        structured_facts: List of facts from Analyst

    Returns:
        Dict with 'title', 'content', 'summary'
    """
    client = get_openai_client()

    log.info(f"[Writer] Generating report for {client_name}...")

    # Organize facts by type
    facts_by_type: Dict[str, List[Dict]] = {}
    for fact in structured_facts:
        fact_type = fact.get("fact_type", "general")
        if fact_type not in facts_by_type:
            facts_by_type[fact_type] = []
        facts_by_type[fact_type].append(fact)

    # Format facts for the prompt
    facts_text = ""
    for fact_type, facts in facts_by_type.items():
        facts_text += f"\n### {fact_type.replace('_', ' ').title()}\n"
        for i, fact in enumerate(facts, 1):
            facts_text += f"{i}. {fact.get('claim', '')}\n"
            if fact.get("metric"):
                facts_text += f"   Metric: {fact['metric']}\n"
            if fact.get("date"):
                facts_text += f"   Date: {fact['date']}\n"
            if fact.get("geography"):
                facts_text += f"   Geography: {fact['geography']}\n"
            facts_text += f"   Source: {fact.get('source_url', '')}\n"
            if fact.get("evidence_snippet"):
                facts_text += f"   Evidence: \"{fact['evidence_snippet'][:150]}...\"\n"
            facts_text += "\n"

    prompt = f"""
You are a professional market research report writer. Create a comprehensive, well-structured market research report.

Client: {client_name}
Topic: {topic}

Report Outline:
{outline}

Structured Facts Available:
{facts_text}

Instructions:
1. Write a professional market research report following the outline provided
2. Integrate the structured facts naturally throughout the report
3. Use proper citations with [Source: URL] format
4. Include an executive summary at the beginning
5. Provide actionable insights and recommendations
6. Focus on information relevant for lead conversion and business development
7. Use markdown formatting for headers, lists, and emphasis
8. Aim for a comprehensive report (2000-3000 words)

Generate the complete report in markdown format.
""".strip()

    try:
        response = client.chat.completions.create(
            model=os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME", "gpt-4o"),
            messages=[
                {
                    "role": "system",
                    "content": "You are an expert market research report writer. Create comprehensive, well-cited, actionable reports.",
                },
                {"role": "user", "content": prompt},
            ],
            temperature=0.4,
            max_completion_tokens=4000,
        )

        report_content = response.choices[0].message.content.strip()

        # Generate summary
        summary_prompt = f"""
Summarize the following market research report in 2-3 concise paragraphs that capture the key insights and recommendations:

{report_content[:2000]}

Provide an executive-level summary suitable for quick review.
""".strip()

        summary_response = client.chat.completions.create(
            model=os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME", "gpt-4o"),
            messages=[
                {
                    "role": "system",
                    "content": "You are an expert at creating executive summaries.",
                },
                {"role": "user", "content": summary_prompt},
            ],
            temperature=0.3,
            max_completion_tokens=500,
        )

        summary = summary_response.choices[0].message.content.strip()

        # Create title
        title = f"Market Research Report: {client_name} - {topic}"

        # Store report in database
        report_id = database_v2.add_report(
            session_id=session_id,
            title=title,
            content=report_content,
            summary=summary,
            format="markdown",
        )

        log.info(f"[Writer] Report generated and stored (ID: {report_id})")

        return {
            "title": title,
            "content": report_content,
            "summary": summary,
        }

    except Exception as e:
        log.error(f"[Writer] Error generating report: {e}")

        # Return a basic report as fallback
        fallback_content = f"""# {client_name} - {topic}

## Executive Summary

Market research report for {client_name}.

## Key Findings

Based on {len(structured_facts)} data points collected:

"""
        for i, fact in enumerate(structured_facts[:10], 1):
            fallback_content += f"{i}. {fact.get('claim', '')}\n"
            if fact.get('source_url'):
                fallback_content += f"   [Source: {fact['source_url']}]\n"
            fallback_content += "\n"

        fallback_content += "\n## Conclusion\n\nFurther analysis recommended.\n"

        return {
            "title": f"Market Research Report: {client_name}",
            "content": fallback_content,
            "summary": f"Market research report for {client_name} with {len(structured_facts)} data points.",
        }


if __name__ == "__main__":
    # Test the writer
    import database_v2

    database_v2.init_db()

    # Create a test session
    client_id = database_v2.add_client("Test Company", "Test Owner")
    session_id = database_v2.create_research_session(client_id, "Market Analysis")

    # Create some test facts
    test_facts = [
        {
            "claim": "Company reported $100M revenue in Q4 2024",
            "metric": "$100M",
            "date": "Q4 2024",
            "fact_type": "financial",
            "source_url": "https://example.com",
            "evidence_snippet": "The company's revenue reached $100M in the fourth quarter.",
        },
        {
            "claim": "Launched new AI product in North America",
            "geography": "North America",
            "fact_type": "product_launch",
            "source_url": "https://example.com",
            "evidence_snippet": "The new AI product was launched across North America.",
        },
    ]

    # Generate report
    outline = """
# Market Analysis Report

## Executive Summary

## Financial Performance

## Product Strategy

## Recommendations
"""

    report = write_report(session_id, "Test Company", "Market Analysis", outline, test_facts)

    print(f"\nTitle: {report['title']}")
    print(f"\nSummary:\n{report['summary']}")
    print(f"\nContent:\n{report['content'][:500]}...")
