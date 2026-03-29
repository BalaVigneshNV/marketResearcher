"""
planner.py - Planner agent for market research workflow.

Takes a topic and produces:
- subtopics: List of key areas to research
- search_queries: Specific search queries to execute
- source_preferences: Preferred source types or domains
- outline: Structure of the final report
"""

import os
import json
from typing import Dict, List, Any
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()


def get_openai_client() -> OpenAI:
    """Get OpenAI client instance."""
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise EnvironmentError("OPENAI_API_KEY must be set in .env")
    return OpenAI(api_key=api_key)


def plan_research(client_name: str, topic: str) -> Dict[str, Any]:
    """
    Use OpenAI to create a comprehensive research plan.

    Args:
        client_name: Name of the client company
        topic: Research topic (e.g., "market opportunity analysis", "competitive landscape")

    Returns:
        Dictionary with:
        - subtopics: List[str] - Key areas to investigate
        - search_queries: List[str] - Specific search queries
        - source_preferences: Dict - Preferred sources/domains
        - outline: str - Report structure in markdown
    """
    client = get_openai_client()

    prompt = f"""
You are a professional market research strategist. Your task is to create a comprehensive research plan for the following:

Client: {client_name}
Topic: {topic}

Generate a detailed research plan with the following components:

1. **Subtopics**: Identify 5-7 key areas to investigate. These should cover:
   - Market dynamics and trends
   - Competitive landscape
   - Growth opportunities
   - Strategic initiatives
   - Technology and innovation
   - Financial and operational metrics

2. **Search Queries**: Create 10-15 specific search queries that will find relevant information. Include:
   - General company news and announcements
   - Product launches and innovations
   - Market analysis and reports
   - Competitive intelligence
   - Industry trends affecting the client
   - Leadership and strategic changes

3. **Source Preferences**: Suggest preferred source types:
   - Authoritative news outlets
   - Industry publications
   - Research firms and analysts
   - Company official sources
   - Trade publications

4. **Report Outline**: Create a structured outline (markdown format) for the final report with:
   - Executive Summary
   - Key Findings
   - Market Analysis sections
   - Competitive Intelligence
   - Strategic Recommendations
   - Conclusion

Respond ONLY with valid JSON in this exact format:
{{
  "subtopics": ["subtopic1", "subtopic2", ...],
  "search_queries": ["query1", "query2", ...],
  "source_preferences": {{
    "preferred_domains": ["domain1.com", "domain2.com"],
    "source_types": ["news", "research", "industry"]
  }},
  "outline": "# Report Title\\n\\n## Executive Summary\\n\\n..."
}}
""".strip()

    try:
        response = client.chat.completions.create(
            model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
            messages=[
                {
                    "role": "system",
                    "content": "You are a market research planning expert. Always respond with valid JSON.",
                },
                {"role": "user", "content": prompt},
            ],
            temperature=0.3,
            response_format={"type": "json_object"},
        )

        result = json.loads(response.choices[0].message.content)

        # Validate structure
        assert "subtopics" in result
        assert "search_queries" in result
        assert "source_preferences" in result
        assert "outline" in result

        return result

    except Exception as e:
        print(f"[Planner] Error: {e}")
        # Return a basic fallback plan
        return {
            "subtopics": [
                f"Recent news about {client_name}",
                f"Product launches by {client_name}",
                f"Market trends affecting {client_name}",
                f"Competitive landscape",
                f"Strategic initiatives",
            ],
            "search_queries": [
                f"{client_name} news",
                f"{client_name} product launch",
                f"{client_name} market trends",
                f"{client_name} competition",
                f"{client_name} strategy",
            ],
            "source_preferences": {
                "preferred_domains": [],
                "source_types": ["news", "research"],
            },
            "outline": f"# Market Research Report: {client_name}\n\n## Executive Summary\n\n## Key Findings\n\n## Market Analysis\n\n## Competitive Intelligence\n\n## Recommendations\n\n## Conclusion",
        }


if __name__ == "__main__":
    # Test the planner
    plan = plan_research("Tesla Inc.", "Market opportunity analysis")
    print(json.dumps(plan, indent=2))
