"""
researcher.py - Researcher agent for market research workflow.

Executes web searches, fetches pages, and extracts content.
Uses:
- DuckDuckGo or SearXNG for search
- requests for simple page fetching
- Playwright for JavaScript-heavy pages (when needed)
- Trafilatura for content extraction
"""

import os
import json
import logging
from typing import List, Dict, Any, Optional
from urllib.parse import urlparse

import requests
from duckduckgo_search import DDGS
import trafilatura
from playwright.sync_api import sync_playwright, Page, Browser

import database_v2

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

# Configuration
MAX_RESULTS_PER_QUERY = 3
REQUEST_TIMEOUT = 10
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"


def search_web(query: str, max_results: int = MAX_RESULTS_PER_QUERY) -> List[Dict[str, str]]:
    """
    Search the web using DuckDuckGo.

    Args:
        query: Search query string
        max_results: Maximum number of results to return

    Returns:
        List of dicts with 'url', 'title', 'snippet'
    """
    results = []
    try:
        with DDGS() as ddgs:
            search_results = ddgs.text(
                keywords=query,
                max_results=max_results,
                safesearch="moderate",
            )
            for item in search_results:
                results.append({
                    "url": item.get("href", ""),
                    "title": item.get("title", ""),
                    "snippet": item.get("body", ""),
                })
        log.info(f"[Researcher] Found {len(results)} results for: {query}")
    except Exception as e:
        log.warning(f"[Researcher] Search error for '{query}': {e}")

    return results


def search_news(query: str, max_results: int = MAX_RESULTS_PER_QUERY) -> List[Dict[str, str]]:
    """
    Search for news articles using DuckDuckGo News.

    Args:
        query: Search query string
        max_results: Maximum number of results to return

    Returns:
        List of dicts with 'url', 'title', 'snippet'
    """
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
        log.info(f"[Researcher] Found {len(results)} news articles for: {query}")
    except Exception as e:
        log.warning(f"[Researcher] News search error for '{query}': {e}")

    return results


def fetch_with_requests(url: str) -> Optional[str]:
    """
    Fetch page content using requests library.

    Args:
        url: URL to fetch

    Returns:
        HTML content or None if failed
    """
    try:
        headers = {"User-Agent": USER_AGENT}
        response = requests.get(url, headers=headers, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        return response.text
    except Exception as e:
        log.warning(f"[Researcher] requests fetch failed for {url}: {e}")
        return None


def fetch_with_playwright(url: str) -> Optional[str]:
    """
    Fetch page content using Playwright (for JavaScript-heavy pages).

    Args:
        url: URL to fetch

    Returns:
        HTML content or None if failed
    """
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(user_agent=USER_AGENT)
            page.goto(url, wait_until="networkidle", timeout=30000)
            content = page.content()
            browser.close()
            return content
    except Exception as e:
        log.warning(f"[Researcher] Playwright fetch failed for {url}: {e}")
        return None


def extract_content(html: str, url: str) -> Dict[str, str]:
    """
    Extract clean text content from HTML using Trafilatura.

    Args:
        html: HTML content
        url: Source URL (for metadata)

    Returns:
        Dict with 'content', 'title', 'snippet'
    """
    try:
        # Extract main content
        content = trafilatura.extract(
            html,
            include_comments=False,
            include_tables=True,
            include_links=False,
            output_format="txt",
        )

        if not content:
            content = ""

        # Extract metadata
        metadata = trafilatura.extract_metadata(html)
        title = metadata.title if metadata and metadata.title else ""

        # Create snippet (first 300 chars)
        snippet = content[:300] + "..." if len(content) > 300 else content

        return {
            "title": title,
            "content": content,
            "snippet": snippet,
        }
    except Exception as e:
        log.warning(f"[Researcher] Content extraction failed for {url}: {e}")
        return {"title": "", "content": "", "snippet": ""}


def fetch_and_extract(url: str, use_playwright: bool = False) -> Optional[Dict[str, str]]:
    """
    Fetch a URL and extract its content.

    Args:
        url: URL to fetch
        use_playwright: Whether to use Playwright (for JS-heavy sites)

    Returns:
        Dict with 'url', 'title', 'content', 'snippet', 'fetch_method'
    """
    log.info(f"[Researcher] Fetching: {url}")

    # Try requests first (unless playwright is explicitly requested)
    html = None
    fetch_method = "requests"

    if not use_playwright:
        html = fetch_with_requests(url)

    # Fall back to Playwright if needed
    if not html and not use_playwright:
        log.info(f"[Researcher] Falling back to Playwright for: {url}")
        html = fetch_with_playwright(url)
        fetch_method = "playwright"
    elif use_playwright:
        html = fetch_with_playwright(url)
        fetch_method = "playwright"

    if not html:
        return None

    # Extract content
    extracted = extract_content(html, url)

    if not extracted["content"]:
        return None

    return {
        "url": url,
        "title": extracted["title"],
        "content": extracted["content"],
        "snippet": extracted["snippet"],
        "fetch_method": fetch_method,
    }


def research_topic(
    session_id: int,
    search_queries: List[str],
    source_preferences: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    """
    Execute the research stage: search news and web, fetch, extract.

    Args:
        session_id: Database session ID
        search_queries: List of search queries from Planner
        source_preferences: Optional preferences for sources

    Returns:
        List of evidence dicts that were stored in database
    """
    evidence_list = []
    seen_urls = set()

    for query in search_queries:
        log.info(f"[Researcher] Searching: {query}")

        # Search news first (primary source for market research)
        news_results = search_news(query)

        # Also search the web for additional context
        web_results = search_web(query)

        # Combine results, prioritizing news
        all_results = news_results + web_results

        # Fetch and extract each result
        for result in all_results:
            url = result["url"]

            # Skip duplicates
            if url in seen_urls:
                continue
            seen_urls.add(url)

            # Fetch and extract content
            extracted = fetch_and_extract(url)

            if not extracted:
                log.warning(f"[Researcher] Failed to extract content from: {url}")
                continue

            # Determine source type based on which search returned it
            source_type = "news" if result in news_results else "search"

            # Store in database
            try:
                evidence_id = database_v2.add_raw_evidence(
                    session_id=session_id,
                    url=extracted["url"],
                    title=extracted["title"],
                    content=extracted["content"],
                    snippet=extracted["snippet"],
                    source_type=source_type,
                    fetch_method=extracted["fetch_method"],
                    metadata=json.dumps({"search_query": query}),
                )

                evidence_list.append({
                    "id": evidence_id,
                    "url": extracted["url"],
                    "title": extracted["title"],
                    "content": extracted["content"],
                    "snippet": extracted["snippet"],
                    "fetch_method": extracted["fetch_method"],
                    "source_type": source_type,
                })

                log.info(f"[Researcher] Stored {source_type} evidence: {extracted['title'][:60]}...")

            except Exception as e:
                log.error(f"[Researcher] Database error: {e}")

    log.info(f"[Researcher] Completed. Total evidence collected: {len(evidence_list)}")
    return evidence_list


if __name__ == "__main__":
    # Test the researcher
    import database_v2

    database_v2.init_db()

    # Create a test session
    client_id = database_v2.add_client("Test Company", "Test Owner")
    session_id = database_v2.create_research_session(client_id, "Test Research")

    # Test search and extraction
    queries = ["Tesla electric vehicles", "Apple AI products"]
    evidence = research_topic(session_id, queries)

    print(f"\nCollected {len(evidence)} pieces of evidence:")
    for e in evidence:
        print(f"  - {e['title'][:60]}")
