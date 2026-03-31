"""
langgraph_workflow.py - LangGraph workflow definition for market research system.

Implements a 4-agent workflow:
1. Planner: Creates research plan (subtopics, queries, outline)
2. Researcher: Fetches and extracts content from web sources
3. Analyst: Extracts structured facts from raw evidence
4. Writer: Compiles final report with citations
"""

from typing import TypedDict, List, Dict, Any, Annotated
import operator
from langgraph.graph import StateGraph, END


# ---------------------------------------------------------------------------
# State Definition
# ---------------------------------------------------------------------------

class ResearchState(TypedDict):
    """
    Shared state passed through the workflow.
    Each agent reads and writes to this state.
    """
    # Input
    client_id: int
    client_name: str
    topic: str
    session_id: int

    # Planner outputs
    subtopics: List[str]
    search_queries: List[str]
    source_preferences: Dict[str, Any]
    outline: str

    # Researcher outputs
    raw_evidence: Annotated[List[Dict[str, Any]], operator.add]  # Accumulate evidence

    # Analyst outputs
    structured_facts: Annotated[List[Dict[str, Any]], operator.add]  # Accumulate facts

    # Writer outputs
    report_title: str
    report_content: str
    report_summary: str

    # Workflow control
    current_stage: str
    error_message: str
    completed: bool


# ---------------------------------------------------------------------------
# Workflow Graph Builder
# ---------------------------------------------------------------------------

def create_research_workflow() -> StateGraph:
    """
    Create the LangGraph workflow for market research.

    The workflow follows this deterministic path:
    START -> Planner -> Researcher -> Analyst -> Writer -> END

    Each node corresponds to one agent stage.
    """
    workflow = StateGraph(ResearchState)

    # Add nodes (agent stages)
    workflow.add_node("planner", planner_node)
    workflow.add_node("researcher", researcher_node)
    workflow.add_node("analyst", analyst_node)
    workflow.add_node("writer", writer_node)

    # Define edges (workflow path)
    workflow.set_entry_point("planner")
    workflow.add_edge("planner", "researcher")
    workflow.add_edge("researcher", "analyst")
    workflow.add_edge("analyst", "writer")
    workflow.add_edge("writer", END)

    return workflow


# ---------------------------------------------------------------------------
# Node Implementations (Stubs - to be implemented by agent modules)
# ---------------------------------------------------------------------------

def planner_node(state: ResearchState) -> ResearchState:
    """
    Planner agent node.
    Generates: subtopics, search_queries, source_preferences, outline
    """
    from agents.planner import plan_research

    state["current_stage"] = "planner"

    try:
        plan = plan_research(
            client_name=state["client_name"],
            topic=state["topic"],
        )

        state["subtopics"] = plan["subtopics"]
        state["search_queries"] = plan["search_queries"]
        state["source_preferences"] = plan["source_preferences"]
        state["outline"] = plan["outline"]

    except Exception as e:
        state["error_message"] = f"Planner error: {str(e)}"

    return state


def researcher_node(state: ResearchState) -> ResearchState:
    """
    Researcher agent node.
    Executes searches, fetches pages, extracts content.
    Appends to raw_evidence.
    """
    from agents.researcher import research_topic

    state["current_stage"] = "researcher"

    try:
        evidence = research_topic(
            session_id=state["session_id"],
            search_queries=state["search_queries"],
            source_preferences=state.get("source_preferences", {}),
        )

        # Accumulate evidence (operator.add in state definition)
        state["raw_evidence"] = evidence

    except Exception as e:
        state["error_message"] = f"Researcher error: {str(e)}"

    return state


def analyst_node(state: ResearchState) -> ResearchState:
    """
    Analyst agent node.
    Reads raw_evidence and extracts structured facts.
    Appends to structured_facts.
    """
    from agents.analyst import analyze_evidence

    state["current_stage"] = "analyst"

    try:
        facts = analyze_evidence(
            session_id=state["session_id"],
            client_name=state["client_name"],
            raw_evidence=state.get("raw_evidence", []),
        )

        # Accumulate facts (operator.add in state definition)
        state["structured_facts"] = facts

    except Exception as e:
        state["error_message"] = f"Analyst error: {str(e)}"

    return state


def writer_node(state: ResearchState) -> ResearchState:
    """
    Writer agent node.
    Compiles final report from structured facts and outline.
    """
    from agents.writer import write_report

    state["current_stage"] = "writer"

    try:
        report = write_report(
            session_id=state["session_id"],
            client_name=state["client_name"],
            topic=state["topic"],
            outline=state.get("outline", ""),
            structured_facts=state.get("structured_facts", []),
        )

        state["report_title"] = report["title"]
        state["report_content"] = report["content"]
        state["report_summary"] = report["summary"]
        state["completed"] = True

    except Exception as e:
        state["error_message"] = f"Writer error: {str(e)}"

    return state


# ---------------------------------------------------------------------------
# Workflow Execution
# ---------------------------------------------------------------------------

def run_research_workflow(
    client_id: int,
    client_name: str,
    topic: str,
    session_id: int,
) -> ResearchState:
    """
    Execute the complete research workflow for a client.

    Args:
        client_id: Database ID of the client
        client_name: Name of the client company
        topic: Research topic/question
        session_id: Database session ID

    Returns:
        Final state with completed research
    """
    # Create workflow graph
    workflow = create_research_workflow()
    app = workflow.compile()

    # Initialize state
    initial_state: ResearchState = {
        "client_id": client_id,
        "client_name": client_name,
        "topic": topic,
        "session_id": session_id,
        "subtopics": [],
        "search_queries": [],
        "source_preferences": {},
        "outline": "",
        "raw_evidence": [],
        "structured_facts": [],
        "report_title": "",
        "report_content": "",
        "report_summary": "",
        "current_stage": "start",
        "error_message": "",
        "completed": False,
    }

    # Run workflow
    final_state = app.invoke(initial_state)

    return final_state
