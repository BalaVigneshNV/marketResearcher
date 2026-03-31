#!/usr/bin/env python3
"""
Test script to demonstrate news search integration in the market research system.

This script shows how the researcher agent now:
1. Searches for news articles using DuckDuckGo News API
2. Supplements with general web search
3. Extracts content from both sources
4. Stores them with appropriate source_type tags

The final report will contain market research based on collected news.
"""

import sys
import json
from typing import List, Dict

# Mock data to demonstrate the flow without network access
MOCK_NEWS_RESULTS = [
    {
        "url": "https://example.com/news/tesla-q4-earnings",
        "title": "Tesla Reports Record Q4 Earnings, Stock Surges",
        "snippet": "Tesla Inc. announced record earnings for Q4 2024, exceeding analyst expectations..."
    },
    {
        "url": "https://example.com/news/tesla-model-y-production",
        "title": "Tesla Expands Model Y Production in New Factory",
        "snippet": "The electric vehicle maker is ramping up Model Y production at its new facility..."
    },
    {
        "url": "https://example.com/news/tesla-fsd-update",
        "title": "Tesla Releases Major Full Self-Driving Update",
        "snippet": "Tesla has rolled out a significant update to its Full Self-Driving beta software..."
    }
]

MOCK_WEB_RESULTS = [
    {
        "url": "https://example.com/analysis/tesla-market-position",
        "title": "Tesla's Market Position in the EV Industry",
        "snippet": "An in-depth analysis of Tesla's competitive advantages in the electric vehicle market..."
    },
    {
        "url": "https://example.com/report/tesla-supply-chain",
        "title": "Tesla Supply Chain Analysis 2024",
        "snippet": "Comprehensive report on Tesla's supply chain strategy and partnerships..."
    }
]


def demonstrate_news_integration():
    """Demonstrate the new news search integration."""

    print("=" * 80)
    print("NEWS SEARCH INTEGRATION DEMONSTRATION")
    print("=" * 80)
    print()
    print("The market research system now collects news as the PRIMARY source:")
    print()

    # Step 1: Show search flow
    print("STEP 1: SEARCH FLOW")
    print("-" * 80)
    print("For each search query, the Researcher agent now:")
    print("  1. Calls search_news(query) → DuckDuckGo News API")
    print("  2. Calls search_web(query) → DuckDuckGo Text API")
    print("  3. Combines results, prioritizing news articles")
    print()

    # Step 2: Show example results
    print("STEP 2: EXAMPLE RESULTS for query: 'Tesla Inc. news'")
    print("-" * 80)
    print(f"\nNews Articles Found ({len(MOCK_NEWS_RESULTS)}):")
    for i, result in enumerate(MOCK_NEWS_RESULTS, 1):
        print(f"  [{i}] {result['title']}")
        print(f"      Source: NEWS (from DDGS.news())")
        print(f"      URL: {result['url']}")
        print(f"      Snippet: {result['snippet'][:80]}...")
        print()

    print(f"Web Results Found ({len(MOCK_WEB_RESULTS)}):")
    for i, result in enumerate(MOCK_WEB_RESULTS, 1):
        print(f"  [{i}] {result['title']}")
        print(f"      Source: WEB (from DDGS.text())")
        print(f"      URL: {result['url']}")
        print(f"      Snippet: {result['snippet'][:80]}...")
        print()

    # Step 3: Show database storage
    print("STEP 3: DATABASE STORAGE")
    print("-" * 80)
    print("Each piece of evidence is stored with metadata:")
    print()

    all_results = MOCK_NEWS_RESULTS + MOCK_WEB_RESULTS
    for i, result in enumerate(all_results, 1):
        source_type = "news" if result in MOCK_NEWS_RESULTS else "search"
        print(f"  Evidence #{i}:")
        print(f"    - source_type: '{source_type}'")
        print(f"    - title: {result['title']}")
        print(f"    - url: {result['url']}")
        print(f"    - content: [extracted via Trafilatura]")
        print()

    # Step 4: Show analyst processing
    print("STEP 4: ANALYST PROCESSING")
    print("-" * 80)
    print("The Analyst agent extracts structured facts from the evidence:")
    print("  - Identifies key claims and metrics")
    print("  - Tags with fact_type (financial, product_launch, market_trend, etc.)")
    print("  - Extracts entities (company, geography, date)")
    print("  - Provides confidence scores")
    print()

    example_facts = [
        {
            "claim": "Tesla reported record Q4 2024 earnings exceeding analyst expectations",
            "metric": "Record earnings Q4 2024",
            "fact_type": "financial",
            "company": "Tesla Inc.",
            "date": "Q4 2024",
            "confidence": 0.95,
            "source_url": MOCK_NEWS_RESULTS[0]["url"]
        },
        {
            "claim": "Tesla expanded Model Y production at new facility",
            "fact_type": "product_launch",
            "company": "Tesla Inc.",
            "date": "2024",
            "confidence": 0.90,
            "source_url": MOCK_NEWS_RESULTS[1]["url"]
        },
        {
            "claim": "Tesla released major Full Self-Driving software update",
            "fact_type": "product_launch",
            "company": "Tesla Inc.",
            "date": "2024",
            "confidence": 0.92,
            "source_url": MOCK_NEWS_RESULTS[2]["url"]
        }
    ]

    print("Example Facts Extracted:")
    for i, fact in enumerate(example_facts, 1):
        print(f"\n  Fact #{i}:")
        print(f"    Claim: {fact['claim']}")
        print(f"    Type: {fact['fact_type']}")
        if fact.get('metric'):
            print(f"    Metric: {fact['metric']}")
        print(f"    Confidence: {fact['confidence']:.0%}")
        print(f"    Source: {fact['source_url']}")
    print()

    # Step 5: Show report generation
    print("STEP 5: MARKET RESEARCH REPORT GENERATION")
    print("-" * 80)
    print("The Writer agent compiles the final market research report:")
    print("  - Integrates facts from news articles and web sources")
    print("  - Cites sources with [Source: URL] format")
    print("  - Provides executive summary")
    print("  - Includes actionable insights and recommendations")
    print("  - Focuses on lead conversion opportunities")
    print()

    print("Example Report Structure:")
    print()
    print("  # Market Research Report: Tesla Inc. - Market Analysis")
    print()
    print("  ## Executive Summary")
    print("  Tesla demonstrated strong performance in Q4 2024 with record earnings...")
    print()
    print("  ## Key Findings")
    print("  ### Financial Performance")
    print("  - Record Q4 2024 earnings exceeding analyst expectations")
    print("    [Source: https://example.com/news/tesla-q4-earnings]")
    print()
    print("  ### Product Development")
    print("  - Expanded Model Y production capacity")
    print("    [Source: https://example.com/news/tesla-model-y-production]")
    print("  - Released major FSD software update")
    print("    [Source: https://example.com/news/tesla-fsd-update]")
    print()
    print("  ## Strategic Recommendations")
    print("  Based on the news collected and market analysis...")
    print()

    # Summary
    print("=" * 80)
    print("SUMMARY OF CHANGES")
    print("=" * 80)
    print()
    print("✓ Added search_news() function using DDGS().news() API")
    print("✓ Modified research_topic() to search news FIRST, then web")
    print("✓ News articles are tagged with source_type='news'")
    print("✓ Web results are tagged with source_type='search'")
    print("✓ Combined results provide comprehensive market research")
    print("✓ Final report includes market summaries based on collected news")
    print()
    print("The system now provides market research about the NEWS collected,")
    print("not just filtered topics, with comprehensive summaries.")
    print("=" * 80)


def show_code_changes():
    """Show the key code changes made."""
    print()
    print("=" * 80)
    print("KEY CODE CHANGES")
    print("=" * 80)
    print()

    print("1. NEW FUNCTION: search_news()")
    print("-" * 80)
    print("""
def search_news(query: str, max_results: int = MAX_RESULTS_PER_QUERY):
    '''Search for news articles using DuckDuckGo News.'''
    results = []
    try:
        with DDGS() as ddgs:
            news_results = ddgs.news(
                keywords=query,
                max_results=max_results,
                safesearch="moderate",
            )
            for item in news_results:
                results.append({
                    "url": item.get("url", ""),
                    "title": item.get("title", ""),
                    "snippet": item.get("body", ""),
                })
        log.info(f"[Researcher] Found {len(results)} news articles")
    except Exception as e:
        log.warning(f"[Researcher] News search error: {e}")
    return results
""")

    print("\n2. MODIFIED FUNCTION: research_topic()")
    print("-" * 80)
    print("""
def research_topic(session_id, search_queries, source_preferences):
    '''Execute research stage: search news and web, fetch, extract.'''
    evidence_list = []
    seen_urls = set()

    for query in search_queries:
        # Search news first (primary source for market research)
        news_results = search_news(query)

        # Also search the web for additional context
        web_results = search_web(query)

        # Combine results, prioritizing news
        all_results = news_results + web_results

        for result in all_results:
            # ... fetch and extract content ...
            source_type = "news" if result in news_results else "search"
            # ... store with source_type tag ...
""")

    print("\n3. UPDATED DOCUMENTATION")
    print("-" * 80)
    print("Updated researcher.py header to reflect news search integration:")
    print("  - DuckDuckGo News API for news articles (primary source)")
    print("  - DuckDuckGo Text API for general web search (supplementary)")
    print()


if __name__ == "__main__":
    demonstrate_news_integration()
    show_code_changes()

    print()
    print("✓ Test/demonstration completed successfully!")
    print()
    print("To run the actual system with Azure OpenAI credentials:")
    print("  1. Copy .env.example to .env")
    print("  2. Fill in Azure OpenAI credentials")
    print("  3. Run: python orchestrator.py --client 'Tesla Inc.'")
    print()
