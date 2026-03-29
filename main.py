"""
main.py - Main orchestration script for the Client Signal Notifier POC.

Execution flow:
  1. Initialise the local SQLite database.
  2. Start the FastAPI CRM server in a background thread.
  3. Fetch the client list from http://localhost:8000/clients.
  4. For each client, search for recent news articles via DuckDuckGo.
  5. Classify each article using Azure OpenAI (market summary + P1/P2/P3 signal).
  6. Store classified articles in the database.
  7. Export unnotified articles to owner_notifications.xlsx.
  8. Mark exported articles as notified in the database.

Usage:
  python main.py

Prerequisites:
  - Copy .env.example to .env and fill in Azure OpenAI credentials.
  - pip install -r requirements.txt
"""

import json
import os
import sys
import time
import threading
import logging
from typing import Any

import requests
import uvicorn
from dotenv import load_dotenv
from duckduckgo_search import DDGS
from openai import AzureOpenAI
import pandas as pd
import sqlite3

import database

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Environment
# ---------------------------------------------------------------------------
load_dotenv()

AZURE_API_KEY = os.getenv("AZURE_OPENAI_API_KEY", "")
AZURE_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT", "")
AZURE_API_VERSION = os.getenv("AZURE_OPENAI_API_VERSION", "2024-12-01-preview")
AZURE_DEPLOYMENT = os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME", "gpt-4o")

CRM_API_URL = "http://localhost:8000/clients"
CLASSIFICATION_RULES_PATH = os.path.join(
    os.path.dirname(__file__), "classification_rules.json"
)
EXCEL_OUTPUT_PATH = os.path.join(
    os.path.dirname(__file__), "owner_notifications.xlsx"
)

# Maximum news articles to fetch per client (keeps API usage reasonable)
MAX_ARTICLES_PER_CLIENT = 3


# ---------------------------------------------------------------------------
# 1. FastAPI server (background thread)
# ---------------------------------------------------------------------------

class _UvicornThread(threading.Thread):
    """Runs the FastAPI app in a daemon thread."""

    def __init__(self):
        super().__init__(daemon=True)
        import client_api  # local import to avoid circular issues

        self._server = uvicorn.Server(
            uvicorn.Config(client_api.app, host="127.0.0.1", port=8000, log_level="warning")
        )

    def run(self):
        self._server.run()

    def stop(self):
        self._server.should_exit = True


def start_crm_server() -> _UvicornThread:
    """Start the FastAPI CRM server in a background thread and wait until ready."""
    thread = _UvicornThread()
    thread.start()
    log.info("Waiting for CRM API server to start…")
    for _ in range(20):
        time.sleep(0.5)
        try:
            resp = requests.get("http://localhost:8000/health", timeout=2)
            if resp.status_code == 200:
                log.info("CRM API server is up.")
                return thread
        except requests.ConnectionError:
            pass
    raise RuntimeError("CRM API server did not start in time.")


# ---------------------------------------------------------------------------
# 2. Fetch clients
# ---------------------------------------------------------------------------

def fetch_clients() -> list[dict]:
    """Call the local CRM API and return a list of client dicts."""
    try:
        resp = requests.get(CRM_API_URL, timeout=10)
        resp.raise_for_status()
        clients = resp.json()
        log.info(f"Fetched {len(clients)} clients from CRM API.")
        return clients
    except Exception as exc:
        log.error(f"Failed to fetch clients: {exc}")
        sys.exit(1)


# ---------------------------------------------------------------------------
# 3. News scraping
# ---------------------------------------------------------------------------

def fetch_news_for_client(client_name: str, max_results: int = MAX_ARTICLES_PER_CLIENT) -> list[dict]:
    """
    Use DuckDuckGo to find recent news articles about *client_name*.
    Performs multiple targeted searches to capture comprehensive market research data:
    - General news
    - Product launches and innovations
    - Market trends and competitive intelligence
    """
    articles = []
    seen_urls = set()

    # Define multiple search queries for comprehensive coverage
    search_queries = [
        f"{client_name} news",
        f"{client_name} product launch innovation",
        f"{client_name} market trends competition",
        f"{client_name} leadership hiring expansion",
    ]

    # Distribute max_results across queries
    results_per_query = max(1, max_results // len(search_queries))

    for query in search_queries:
        try:
            with DDGS() as ddgs:
                results = ddgs.news(
                    keywords=query,
                    max_results=results_per_query,
                    safesearch="moderate",
                )
                for item in results:
                    url = item.get("url", "")
                    # Avoid duplicate articles from different searches
                    if url and url not in seen_urls:
                        seen_urls.add(url)
                        articles.append(
                            {
                                "url": url,
                                "title": item.get("title", ""),
                                "snippet": item.get("body", ""),
                            }
                        )
        except Exception as exc:
            log.warning(f"  [{client_name}] DuckDuckGo search error for query '{query}': {exc}")

    log.info(f"  [{client_name}] Found {len(articles)} unique articles across {len(search_queries)} searches.")
    return articles


# ---------------------------------------------------------------------------
# 4. Azure OpenAI classification
# ---------------------------------------------------------------------------

def load_classification_rules() -> dict:
    """Load P1/P2/P3 classification criteria from the JSON config file."""
    with open(CLASSIFICATION_RULES_PATH, "r", encoding="utf-8") as f:
        rules = json.load(f)
    log.info("Loaded classification rules from classification_rules.json.")
    return rules


def build_openai_client() -> AzureOpenAI:
    """Instantiate the Azure OpenAI client from environment variables."""
    if not AZURE_API_KEY or not AZURE_ENDPOINT:
        raise EnvironmentError(
            "AZURE_OPENAI_API_KEY and AZURE_OPENAI_ENDPOINT must be set in .env"
        )
    return AzureOpenAI(
        api_key=AZURE_API_KEY,
        azure_endpoint=AZURE_ENDPOINT,
        api_version=AZURE_API_VERSION,
    )


def classify_article(
    client: AzureOpenAI,
    rules: dict,
    client_name: str,
    title: str,
    snippet: str,
) -> dict[str, str]:
    """
    Ask Azure OpenAI to:
      1. Write a brief market-research summary of the article.
      2. Classify it as P1, P2, P3, P4, or P5 based on the provided rules.

    Returns a dict with keys 'market_summary' and 'signal_type'.
    """
    prompt = f"""
You are a professional market research analyst specializing in lead conversion intelligence. Given the news article below about the company "{client_name}", perform two tasks:

1. Write a concise **Market Summary** (2-3 sentences) explaining the business relevance of this news and how it could be used as a conversation starter for client conversion.
2. Classify the signal as exactly one of: P1, P2, P3, P4, or P5, using the criteria below.

Classification Criteria:
- P1: {rules.get('P1_Criteria', '')}
- P2: {rules.get('P2_Criteria', '')}
- P3: {rules.get('P3_Criteria', '')}
- P4: {rules.get('P4_Criteria', '')}
- P5: {rules.get('P5_Criteria', '')}

Article Title: {title}
Article Snippet: {snippet}

Respond in this exact JSON format (no extra text):
{{
  "market_summary": "<your summary here, focusing on lead conversion opportunities>",
  "signal_type": "<P1|P2|P3|P4|P5>"
}}
""".strip()

    try:
        response = client.chat.completions.create(
            model=AZURE_DEPLOYMENT,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
            max_tokens=400,
        )
        raw = response.choices[0].message.content.strip()
        # Strip markdown code fences if present
        if raw.startswith("```"):
            raw = "\n".join(raw.split("\n")[1:])
        if raw.endswith("```"):
            raw = "\n".join(raw.split("\n")[:-1])
        result = json.loads(raw)
        return {
            "market_summary": result.get("market_summary", ""),
            "signal_type": result.get("signal_type", "P5"),
        }
    except json.JSONDecodeError as exc:
        log.warning(f"JSON parse error from OpenAI response: {exc}. Defaulting to P5.")
        return {"market_summary": snippet[:200], "signal_type": "P5"}
    except Exception as exc:
        log.error(f"OpenAI API error: {exc}")
        return {"market_summary": snippet[:200], "signal_type": "P5"}


# ---------------------------------------------------------------------------
# 5. Database persistence
# ---------------------------------------------------------------------------

def save_article(
    client_id: int,
    url: str,
    title: str,
    snippet: str,
    signal_type: str,
    market_summary: str,
) -> None:
    """Insert a classified article into the articles table."""
    conn = database.get_connection()
    conn.execute(
        """
        INSERT INTO articles (client_id, url, title, snippet, signal_type, market_summary, notified)
        VALUES (?, ?, ?, ?, ?, ?, 0)
        """,
        (client_id, url, title, snippet, signal_type, market_summary),
    )
    conn.commit()
    conn.close()


# ---------------------------------------------------------------------------
# 6. Excel export
# ---------------------------------------------------------------------------

def export_to_excel() -> int:
    """
    Query all unnotified articles, write them to an Excel file grouped by owner,
    then mark them as notified.

    Returns the count of articles exported.
    """
    conn = database.get_connection()
    try:
        rows = conn.execute(
            """
            SELECT
                a.id            AS article_id,
                c.name          AS client_name,
                c.owner_name    AS owner_name,
                a.signal_type,
                a.title,
                a.market_summary,
                a.url,
                a.snippet
            FROM articles a
            JOIN clients  c ON c.id = a.client_id
            WHERE a.notified = 0
            ORDER BY
                CASE a.signal_type
                    WHEN 'P1' THEN 1
                    WHEN 'P2' THEN 2
                    WHEN 'P3' THEN 3
                    WHEN 'P4' THEN 4
                    WHEN 'P5' THEN 5
                    ELSE 6
                END,
                c.owner_name,
                c.name
            """
        ).fetchall()

        if not rows:
            log.info("No unnotified articles to export.")
            return 0

        df = pd.DataFrame(
            [dict(r) for r in rows],
            columns=[
                "article_id",
                "client_name",
                "owner_name",
                "signal_type",
                "title",
                "market_summary",
                "url",
                "snippet",
            ],
        )

        # Write to Excel with one sheet per owner
        with pd.ExcelWriter(EXCEL_OUTPUT_PATH, engine="openpyxl") as writer:
            # Summary sheet (all signals, sorted by priority)
            df_display = df.drop(columns=["article_id", "snippet"])
            df_display.to_excel(writer, sheet_name="All Signals", index=False)

            # Per-owner sheets
            for owner, group in df_display.groupby("owner_name"):
                sheet_name = owner[:31]  # Excel sheet name max length is 31
                group.to_excel(writer, sheet_name=sheet_name, index=False)

        # Mark as notified
        article_ids = [r["article_id"] for r in rows]
        placeholders = ",".join("?" * len(article_ids))
        conn.execute(
            "UPDATE articles SET notified = 1 WHERE id IN (" + placeholders + ")",
            article_ids,
        )
        conn.commit()

        log.info(
            f"Exported {len(rows)} articles to {EXCEL_OUTPUT_PATH} "
            f"({len(df['owner_name'].unique())} owner sheets)."
        )
        return len(rows)
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    log.info("=== Client Signal Notifier POC ===")

    # Initialise DB
    database.init_db()

    # Start CRM API
    server_thread = start_crm_server()

    # Load rules
    rules = load_classification_rules()

    # Build OpenAI client
    try:
        openai_client = build_openai_client()
    except EnvironmentError as exc:
        log.error(str(exc))
        server_thread.stop()
        sys.exit(1)

    # Fetch clients
    clients = fetch_clients()

    # Process each client
    for client in clients:
        client_id = client["id"]
        client_name = client["name"]
        log.info(f"Processing client: {client_name}")

        articles = fetch_news_for_client(client_name)
        for article in articles:
            log.info(f"  Classifying: {article['title'][:60]}…")
            result = classify_article(
                client=openai_client,
                rules=rules,
                client_name=client_name,
                title=article["title"],
                snippet=article["snippet"],
            )
            save_article(
                client_id=client_id,
                url=article["url"],
                title=article["title"],
                snippet=article["snippet"],
                signal_type=result["signal_type"],
                market_summary=result["market_summary"],
            )
            log.info(f"  → Signal: {result['signal_type']}")

    # Export to Excel
    count = export_to_excel()
    log.info(f"Done. {count} signals written to '{EXCEL_OUTPUT_PATH}'.")

    server_thread.stop()


if __name__ == "__main__":
    main()
