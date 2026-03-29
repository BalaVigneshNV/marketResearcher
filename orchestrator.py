"""
orchestrator.py - Main orchestrator for LangGraph-based market research.

This is the new entry point for running market research using the 4-agent workflow:
- Planner
- Researcher
- Analyst
- Writer

Usage:
    python orchestrator.py
"""

import os
import sys
import logging
import argparse
from typing import Optional

from dotenv import load_dotenv

import database_v2
from langgraph_workflow import run_research_workflow

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


def validate_environment():
    """Check that required environment variables are set."""
    required_vars = ["OPENAI_API_KEY"]
    missing = [var for var in required_vars if not os.getenv(var)]

    if missing:
        log.error(f"Missing required environment variables: {', '.join(missing)}")
        log.error("Please copy .env.example to .env and fill in your values.")
        sys.exit(1)


def run_research_for_client(
    client_name: str,
    topic: Optional[str] = None,
) -> None:
    """
    Run the complete market research workflow for a client.

    Args:
        client_name: Name of the client company
        topic: Optional specific research topic (defaults to "Market Research Analysis")
    """
    if topic is None:
        topic = "Market Research Analysis"

    log.info("=" * 80)
    log.info(f"Starting market research workflow for: {client_name}")
    log.info(f"Topic: {topic}")
    log.info("=" * 80)

    # Get or create client in database
    clients = database_v2.list_clients()
    client = next((c for c in clients if c["name"].lower() == client_name.lower()), None)

    if not client:
        log.error(f"Client '{client_name}' not found in database.")
        log.info("Available clients:")
        for c in clients:
            log.info(f"  - {c['name']}")
        sys.exit(1)

    client_id = client["id"]

    # Create research session
    session_id = database_v2.create_research_session(client_id, topic)
    log.info(f"Created research session: {session_id}")

    # Run the LangGraph workflow
    try:
        final_state = run_research_workflow(
            client_id=client_id,
            client_name=client_name,
            topic=topic,
            session_id=session_id,
        )

        # Update session status
        database_v2.update_research_session(session_id, status="completed")

        # Display results
        log.info("=" * 80)
        log.info("WORKFLOW COMPLETED SUCCESSFULLY")
        log.info("=" * 80)

        if final_state.get("error_message"):
            log.warning(f"Errors encountered: {final_state['error_message']}")

        log.info(f"Subtopics explored: {len(final_state.get('subtopics', []))}")
        log.info(f"Search queries executed: {len(final_state.get('search_queries', []))}")
        log.info(f"Evidence collected: {len(final_state.get('raw_evidence', []))}")
        log.info(f"Facts extracted: {len(final_state.get('structured_facts', []))}")

        # Show report summary
        if final_state.get("report_content"):
            log.info("\n" + "=" * 80)
            log.info("REPORT SUMMARY")
            log.info("=" * 80)
            log.info(f"\nTitle: {final_state.get('report_title', '')}\n")
            log.info(final_state.get("report_summary", ""))
            log.info("\n" + "=" * 80)

            # Save report to file
            report_filename = f"report_{client_name.replace(' ', '_')}_{session_id}.md"
            report_path = os.path.join(os.path.dirname(__file__), report_filename)
            with open(report_path, "w", encoding="utf-8") as f:
                f.write(f"# {final_state.get('report_title', '')}\n\n")
                f.write(f"**Session ID:** {session_id}\n\n")
                f.write(f"**Summary:**\n\n{final_state.get('report_summary', '')}\n\n")
                f.write("---\n\n")
                f.write(final_state.get("report_content", ""))

            log.info(f"Full report saved to: {report_filename}")

    except Exception as e:
        log.error(f"Workflow failed: {e}", exc_info=True)
        database_v2.update_research_session(session_id, status="failed")
        sys.exit(1)


def run_all_clients(topic: Optional[str] = None):
    """Run market research for all clients in the database."""
    clients = database_v2.list_clients()

    if not clients:
        log.error("No clients found in database.")
        sys.exit(1)

    log.info(f"Running market research for {len(clients)} clients...")

    for i, client in enumerate(clients, 1):
        log.info(f"\n[{i}/{len(clients)}] Processing: {client['name']}")
        try:
            run_research_for_client(client["name"], topic)
        except Exception as e:
            log.error(f"Failed to process {client['name']}: {e}")
            continue


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="LangGraph-based Market Research Orchestrator"
    )
    parser.add_argument(
        "--client",
        "-c",
        type=str,
        help="Client name to research (e.g., 'Tesla Inc.')",
    )
    parser.add_argument(
        "--topic",
        "-t",
        type=str,
        help="Research topic (default: 'Market Research Analysis')",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Run research for all clients in database",
    )
    parser.add_argument(
        "--list-clients",
        action="store_true",
        help="List all available clients",
    )

    args = parser.parse_args()

    # Initialize database
    database_v2.init_db()

    # List clients if requested
    if args.list_clients:
        clients = database_v2.list_clients()
        log.info(f"Available clients ({len(clients)}):")
        for client in clients:
            log.info(f"  - {client['name']} (Owner: {client['owner_name']})")
        return

    # Validate environment
    validate_environment()

    # Run research
    if args.all:
        run_all_clients(args.topic)
    elif args.client:
        run_research_for_client(args.client, args.topic)
    else:
        log.error("Please specify --client <name> or --all")
        log.info("Use --list-clients to see available clients")
        sys.exit(1)


if __name__ == "__main__":
    main()
