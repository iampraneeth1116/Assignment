"""
workflow.py
-----------
Sequential pipeline definition for the Maverick agent workflow.
Each agent is called in sequence, passing the state dictionary down the line.
"""

from __future__ import annotations

from typing import TypedDict

from app.agents import council_agent, memory_agent, logistics_agent, email_agent


# ---------------------------------------------------------------------------
# State schema
# ---------------------------------------------------------------------------

class MaverickState(TypedDict, total=False):
    query: str                          # original user request
    raw_email: str                      # raw email text sent to email_agent
    email_analysis: dict | None         # structured output from email_agent
    memory_context: dict | None         # synthesized context from memory_agent
    logistics_analysis: dict | None     # logistics output from logistics_agent
    council_recommendation: dict | None # final output from council_agent
    final_response: str                 # synthesised answer for Patrick
    agents_used: list[str]              # which agents were invoked
    details: dict                       # raw sub-agent outputs


# ---------------------------------------------------------------------------
# Public workflow entry point
# ---------------------------------------------------------------------------

def run_workflow(query: str) -> dict:
    """
    Execute the Maverick workflow for a given user query.

    All 4 agents are run in sequence, passing the state dictionary down the line:
    1. email_agent
    2. memory_agent
    3. logistics_agent
    4. council_agent

    Parameters
    ----------
    query: Patrick's natural-language request.

    Returns
    -------
    A dict with ``response``, ``agents_used``, and ``details``.
    """
    # Initialize the shared state dictionary
    state: MaverickState = {
        "query": query,
        "raw_email": query,  # The query is treated as the incoming caregiving text/email
    }

    # 1. Run Email Agent
    state = email_agent.run(state)

    # 2. Run Memory Agent
    state = memory_agent.run(state)

    # 3. Run Logistics Agent
    state = logistics_agent.run(state)

    # 4. Run Council Agent
    state = council_agent.run(state)

    # Format the final response for Patrick based on Council recommendation
    rec = state.get("council_recommendation") or {}
    recommendation = rec.get("recommendation", "No recommendation provided.")
    
    # Construct a beautifully formatted response
    response_parts = [recommendation]
    
    if rec.get("reasoning"):
        response_parts.append("**Reasoning:**\n" + "\n".join(f"- {r}" for r in rec["reasoning"]))
        
    if rec.get("tradeoffs"):
        response_parts.append("**Tradeoffs:**\n" + "\n".join(f"- {r}" for r in rec["tradeoffs"]))
        
    if rec.get("priority_actions"):
        response_parts.append("**Priority Next Steps:**\n" + "\n".join(f"{i+1}. {a}" for i, a in enumerate(rec["priority_actions"])))
        
    final_response = "\n\n".join(response_parts)

    return {
        "response": final_response,
        "agents_used": ["email_agent", "memory_agent", "logistics_agent", "council_agent"],
        "details": {
            "email_analysis": state.get("email_analysis"),
            "memory_context": state.get("memory_context"),
            "logistics_analysis": state.get("logistics_analysis"),
            "council_recommendation": state.get("council_recommendation"),
        },
    }

