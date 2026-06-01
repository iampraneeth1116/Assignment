"""
workflow.py
-----------
LangGraph-style workflow definition for the Maverick agent graph.
Each node wraps a specialist agent. The council_agent acts as the router
that decides which nodes to visit and assembles the final response.
"""

from __future__ import annotations

from typing import TypedDict

from app.agents import council_agent, memory_agent, logistics_agent, email_agent
from app.memory.memory_store import MemoryStore


# ---------------------------------------------------------------------------
# State schema
# ---------------------------------------------------------------------------

class MaverickState(TypedDict, total=False):
    query: str                    # original user request
    context: dict[str, str]       # patient context snapshot
    memory_output: str | None     # output from memory_agent
    logistics_output: dict | None # output from logistics_agent
    email_output: str | None      # output from email_agent
    final_response: str           # synthesised answer for Patrick
    agents_used: list[str]        # which agents were invoked
    details: dict                 # raw sub-agent outputs


# ---------------------------------------------------------------------------
# Node functions
# ---------------------------------------------------------------------------

def node_load_context(state: MaverickState) -> MaverickState:
    """Load fresh patient context from the DB into state."""
    store = MemoryStore()
    state["context"] = store.get_all_context()
    return state


def node_memory(state: MaverickState) -> MaverickState:
    """Invoke the memory agent."""
    result = memory_agent.run(state["query"], state.get("context"))
    state["memory_output"] = result
    return state


def node_logistics(state: MaverickState) -> MaverickState:
    """Invoke the logistics / scheduling agent."""
    result = logistics_agent.run(state["query"], state.get("context"))
    state["logistics_output"] = result
    return state


def node_email(state: MaverickState) -> MaverickState:
    """Invoke the email drafting agent."""
    result = email_agent.run(state["query"], state.get("context"))
    state["email_output"] = result
    return state


def node_council(state: MaverickState) -> MaverickState:
    """
    Orchestrate sub-agents and synthesise a final response.
    This node drives the entire workflow; individual nodes above are available
    for direct invocation or future graph-based routing.
    """
    result = council_agent.run(state["query"])
    state["final_response"] = result["response"]
    state["agents_used"] = result["agents_used"]
    state["details"] = result["details"]
    return state


# ---------------------------------------------------------------------------
# Public workflow entry point
# ---------------------------------------------------------------------------

def run_workflow(query: str) -> dict:
    """
    Execute the Maverick workflow for a given user query.

    This is the primary entry point called by the API layer.

    Parameters
    ----------
    query: Patrick's natural-language request.

    Returns
    -------
    A dict with ``response``, ``agents_used``, and ``details``.
    """
    state: MaverickState = {"query": query}
    state = node_load_context(state)
    state = node_council(state)   # council handles routing internally
    return {
        "response": state.get("final_response", ""),
        "agents_used": state.get("agents_used", []),
        "details": state.get("details", {}),
    }
