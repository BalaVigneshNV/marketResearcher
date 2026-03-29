"""
demo.py - Standalone demo script for the Client Signal Notifier POC.

Purpose:
  Provides a fully self-contained demonstration WITHOUT requiring:
    - A live Azure OpenAI key
    - An active internet connection (DuckDuckGo news)
    - The FastAPI server to be running

It inserts rich sample data directly into the SQLite database (clients +
pre-classified articles), then generates 'owner_notifications.xlsx' so you
can immediately see the output format and review it for stakeholder demos.

Usage:
  python demo.py [--reset]

  --reset   Wipe existing demo data before inserting fresh records.
"""

import argparse
import os
import sqlite3
import logging

import pandas as pd

import database

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

EXCEL_OUTPUT_PATH = os.path.join(os.path.dirname(__file__), "owner_notifications.xlsx")

# ---------------------------------------------------------------------------
# Sample demo articles
# Articles reference clients by *name* so they work regardless of the auto-
# assigned database ID. IDs are resolved at insertion time.
# ---------------------------------------------------------------------------

DEMO_ARTICLES = [
    # --- P1 signals (critical) ---
    {
        "client_name": "Tesla Inc.",
        "title": "Tesla CEO Elon Musk Steps Down as CEO, Appoints New Leadership",
        "snippet": (
            "In a stunning move, Tesla's board announced that Elon Musk will transition from the "
            "CEO role to Executive Chairman, with a new CEO appointed effective immediately."
        ),
        "signal_type": "P1",
        "market_summary": (
            "A leadership transition at Tesla's top level represents a critical risk event. "
            "CEO changes often trigger significant stock volatility and strategic uncertainty. "
            "Immediate stakeholder engagement is recommended."
        ),
        "url": "https://example.com/tesla-ceo-change",
    },
    {
        "client_name": "Amazon.com Inc.",
        "title": "Amazon Faces $2B Antitrust Fine from EU Regulators",
        "snippet": (
            "European regulators have slapped Amazon with a record $2 billion antitrust fine, "
            "citing anti-competitive practices in its marketplace. The company plans to appeal."
        ),
        "signal_type": "P1",
        "market_summary": (
            "A $2B regulatory fine represents a significant financial and reputational risk for Amazon. "
            "The precedent could affect its marketplace operations across the EU. "
            "This is a critical signal requiring immediate owner attention."
        ),
        "url": "https://example.com/amazon-antitrust-fine",
    },
    {
        "client_name": "Meta Platforms Inc.",
        "title": "Meta Stock Drops 15% Following Data Breach Disclosure",
        "snippet": (
            "Meta Platforms disclosed a major data breach affecting over 400 million user records. "
            "The stock fell 15% in after-hours trading following the announcement."
        ),
        "signal_type": "P1",
        "market_summary": (
            "A 15% stock drop combined with a large-scale data breach signals severe reputational "
            "and regulatory risk for Meta. Regulatory fines and user trust erosion are likely "
            "near-term consequences."
        ),
        "url": "https://example.com/meta-data-breach",
    },
    {
        "client_name": "Palantir Technologies",
        "title": "Palantir Faces Congressional Scrutiny Over Government Contract Practices",
        "snippet": (
            "A Senate committee has launched an investigation into Palantir's government contracting "
            "practices, citing concerns about data privacy and contract transparency."
        ),
        "signal_type": "P1",
        "market_summary": (
            "Congressional investigations pose significant business continuity risk for Palantir, "
            "which derives a substantial portion of revenue from government contracts. "
            "This could jeopardise existing and future federal agreements."
        ),
        "url": "https://example.com/palantir-congress",
    },
    # --- P2 signals (significant) ---
    {
        "client_name": "Apple Inc.",
        "title": "Apple Announces $3 Billion Acquisition of AI Startup Luminary AI",
        "snippet": (
            "Apple has agreed to acquire Luminary AI, a generative AI startup, for $3 billion "
            "in an all-cash deal. The acquisition is expected to close in Q2 2025."
        ),
        "signal_type": "P2",
        "market_summary": (
            "Apple's $3B acquisition of an AI startup signals a strategic push to embed advanced "
            "AI capabilities directly into its ecosystem. This positions Apple as a stronger "
            "competitor in the generative AI space."
        ),
        "url": "https://example.com/apple-ai-acquisition",
    },
    {
        "client_name": "Microsoft Corporation",
        "title": "Microsoft Closes $10B Strategic Partnership with SAP for Cloud Services",
        "snippet": (
            "Microsoft and SAP have announced a landmark $10 billion, five-year cloud partnership "
            "that will see SAP's enterprise software suite natively integrated with Azure."
        ),
        "signal_type": "P2",
        "market_summary": (
            "The SAP-Azure partnership significantly expands Microsoft's enterprise cloud footprint. "
            "This is a major contract win that reinforces Azure's position as the leading "
            "platform for enterprise ERP workloads."
        ),
        "url": "https://example.com/microsoft-sap-partnership",
    },
    {
        "client_name": "NVIDIA Corporation",
        "title": "NVIDIA Raises $5B in Secondary Offering to Fund AI Infrastructure Expansion",
        "snippet": (
            "NVIDIA has completed a $5 billion secondary stock offering to fund accelerated "
            "expansion of its AI training infrastructure and R&D pipeline."
        ),
        "signal_type": "P2",
        "market_summary": (
            "NVIDIA's capital raise signals aggressive reinvestment in AI infrastructure, "
            "supporting continued dominance in the GPU market. This could accelerate product "
            "timelines and widen its competitive moat."
        ),
        "url": "https://example.com/nvidia-offering",
    },
    {
        "client_name": "OpenAI",
        "title": "OpenAI Secures Series F Funding of $6.6 Billion at $157 Billion Valuation",
        "snippet": (
            "OpenAI has closed its Series F funding round raising $6.6 billion, valuing the "
            "company at $157 billion. Investors include Microsoft, Thrive Capital, and Tiger Global."
        ),
        "signal_type": "P2",
        "market_summary": (
            "OpenAI's historic Series F round underscores investor confidence in its AI leadership. "
            "The $157B valuation cements its position as the most valuable AI company globally "
            "and will fund significant product and infrastructure investment."
        ),
        "url": "https://example.com/openai-series-f",
    },
    {
        "client_name": "Alphabet Inc.",
        "title": "Alphabet Expands Google Cloud to 10 New Regions in Asia-Pacific",
        "snippet": (
            "Alphabet announced the expansion of Google Cloud infrastructure to 10 new regions "
            "across Asia-Pacific, investing over $2 billion in local data centres."
        ),
        "signal_type": "P2",
        "market_summary": (
            "Google Cloud's Asia-Pacific expansion represents a significant geographic growth "
            "initiative that positions Alphabet to capture surging cloud demand in high-growth "
            "emerging markets."
        ),
        "url": "https://example.com/google-cloud-apac",
    },
    # --- P3 signals (routine) ---
    {
        "client_name": "Apple Inc.",
        "title": "Apple Wins 'Best Smartphone Camera' Award at CES 2025",
        "snippet": (
            "Apple's iPhone 16 Pro won the Best Smartphone Camera award at CES 2025, "
            "praised for its photonic engine and computational photography features."
        ),
        "signal_type": "P3",
        "market_summary": (
            "An industry award reinforces Apple's brand leadership in smartphone imaging. "
            "While positive for brand perception, this is routine recognition with limited "
            "immediate financial impact."
        ),
        "url": "https://example.com/apple-ces-award",
    },
    {
        "client_name": "Microsoft Corporation",
        "title": "Microsoft Releases Patch Tuesday Security Updates for January 2025",
        "snippet": (
            "Microsoft released its monthly Patch Tuesday updates, addressing 72 vulnerabilities "
            "across Windows, Office, and Azure services."
        ),
        "signal_type": "P3",
        "market_summary": (
            "Routine monthly security patching is standard practice for Microsoft. "
            "This reflects normal operational cadence with no significant business impact "
            "unless a critical zero-day is included."
        ),
        "url": "https://example.com/microsoft-patch-tuesday",
    },
    {
        "client_name": "Salesforce Inc.",
        "title": "Salesforce Launches Minor Update to Einstein Analytics Dashboard",
        "snippet": (
            "Salesforce released a minor update to its Einstein Analytics product, adding "
            "improved chart customisation options and a refreshed user interface."
        ),
        "signal_type": "P3",
        "market_summary": (
            "This minor product update represents incremental improvement to Salesforce's "
            "analytics offering. It is unlikely to drive significant revenue changes but "
            "contributes to customer experience quality."
        ),
        "url": "https://example.com/salesforce-einstein-update",
    },
    {
        "client_name": "Tesla Inc.",
        "title": "Tesla Opens New Service Centre in Austin, Texas",
        "snippet": (
            "Tesla has opened a new service and delivery centre in Austin, Texas, "
            "expanding its after-sales network ahead of increased Cybertruck deliveries."
        ),
        "signal_type": "P3",
        "market_summary": (
            "A new service centre opening is part of Tesla's routine infrastructure expansion. "
            "It signals operational scaling to support growing vehicle delivery volumes in "
            "the Texas market."
        ),
        "url": "https://example.com/tesla-austin-service",
    },
    {
        "client_name": "NVIDIA Corporation",
        "title": "NVIDIA Publishes Annual Sustainability Report Highlighting Carbon Reduction Goals",
        "snippet": (
            "NVIDIA released its 2024 Corporate Sustainability Report, outlining goals to "
            "reduce Scope 1 and Scope 2 carbon emissions by 50% by 2030."
        ),
        "signal_type": "P3",
        "market_summary": (
            "Sustainability reporting is increasingly important for institutional investors. "
            "NVIDIA's carbon reduction goals align with ESG investment criteria but represent "
            "a longer-term commitment rather than an immediate market-moving event."
        ),
        "url": "https://example.com/nvidia-sustainability",
    },
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def reset_demo_data(conn: sqlite3.Connection) -> None:
    """Remove all previously inserted demo articles."""
    conn.execute("DELETE FROM articles")
    log.info("Cleared existing articles from database.")


def insert_demo_data(conn: sqlite3.Connection) -> None:
    """Insert demo articles using client names resolved to DB IDs."""
    # Build name→id lookup from whatever clients are currently in the DB
    rows = conn.execute("SELECT id, name FROM clients").fetchall()
    name_to_id = {row["name"]: row["id"] for row in rows}

    inserted = 0
    skipped = 0
    for article in DEMO_ARTICLES:
        client_name = article["client_name"]
        client_id = name_to_id.get(client_name)
        if client_id is None:
            log.warning(
                f"  Skipping article '{article['title'][:50]}…' — "
                f"client '{client_name}' not found in DB. "
                f"Add it to clients.csv and re-run database.py first."
            )
            skipped += 1
            continue
        conn.execute(
            """
            INSERT INTO articles (client_id, url, title, snippet, signal_type, market_summary, notified)
            VALUES (?, ?, ?, ?, ?, ?, 0)
            """,
            (
                client_id,
                article["url"],
                article["title"],
                article["snippet"],
                article["signal_type"],
                article["market_summary"],
            ),
        )
        inserted += 1

    conn.commit()
    log.info(
        f"Inserted {inserted} demo articles "
        + (f"({skipped} skipped — client not in DB)." if skipped else "for all clients.")
    )


def export_demo_excel(conn: sqlite3.Connection) -> None:
    """Export all unnotified demo articles to Excel, grouped by owner."""
    rows = conn.execute(
        """
        SELECT
            a.id            AS article_id,
            c.name          AS client_name,
            c.owner_name    AS owner_name,
            a.signal_type,
            a.title,
            a.market_summary,
            a.url
        FROM articles a
        JOIN clients c ON c.id = a.client_id
        WHERE a.notified = 0
        ORDER BY
            CASE a.signal_type WHEN 'P1' THEN 1 WHEN 'P2' THEN 2 ELSE 3 END,
            c.owner_name,
            c.name
        """
    ).fetchall()

    if not rows:
        log.info("No unnotified articles to export.")
        return

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
        ],
    )

    signal_counts = df["signal_type"].value_counts().to_dict()
    log.info(
        f"Signal breakdown – P1: {signal_counts.get('P1', 0)}, "
        f"P2: {signal_counts.get('P2', 0)}, "
        f"P3: {signal_counts.get('P3', 0)}"
    )

    with pd.ExcelWriter(EXCEL_OUTPUT_PATH, engine="openpyxl") as writer:
        # Summary sheet
        df.drop(columns=["article_id"]).to_excel(writer, sheet_name="All Signals", index=False)

        # Per-owner sheets
        for owner, group in df.drop(columns=["article_id"]).groupby("owner_name"):
            sheet_name = str(owner)[:31]
            group.to_excel(writer, sheet_name=sheet_name, index=False)

    # Mark as notified
    article_ids = [r["article_id"] for r in rows]
    placeholders = ",".join("?" * len(article_ids))
    conn.execute(
        "UPDATE articles SET notified = 1 WHERE id IN (" + placeholders + ")",
        article_ids,
    )
    conn.commit()

    log.info(f"Exported {len(rows)} demo articles to '{EXCEL_OUTPUT_PATH}'.")
    log.info(f"Sheets: 'All Signals' + one sheet per owner ({df['owner_name'].nunique()} total).")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Demo script: inserts sample data and generates owner_notifications.xlsx"
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Clear all existing articles before inserting demo data.",
    )
    args = parser.parse_args()

    log.info("=== Client Signal Notifier – Demo Mode ===")

    database.init_db()
    conn = database.get_connection()

    try:
        if args.reset:
            reset_demo_data(conn)

        insert_demo_data(conn)
        export_demo_excel(conn)
    finally:
        conn.close()

    log.info("Demo complete. Open 'owner_notifications.xlsx' to review the output.")


if __name__ == "__main__":
    main()

