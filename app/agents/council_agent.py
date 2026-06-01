"""
council_agent.py
----------------
The deliberation council — a meta-agent that synthesises the outputs of all
three specialist agents (email, memory, logistics) and produces a final,
holistic recommendation for Patrick.

Uses Groq (LLaMA 3.3-70B) as the reasoning engine.

Input  : full state dict (email_analysis + memory_context + logistics_analysis)
Output : state["council_recommendation"] (CouncilRecommendation Pydantic model)
"""

from __future__ import annotations

import json
import os

from groq import Groq
from dotenv import load_dotenv
from pydantic import BaseModel

from app.audit.audit_log import AuditLog

load_dotenv()

_client = Groq(api_key=os.getenv("GROQ_API_KEY", ""))
_MODEL = "llama-3.3-70b-versatile"
_AGENT_NAME = "council_agent"

# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------
_SYSTEM_PROMPT = (
    "You are a multi-perspective council agent that deliberates on caregiving "
    "decisions. Consider all inputs holistically. Reason through tradeoffs "
    "carefully. Respond ONLY with valid JSON."
)


# ---------------------------------------------------------------------------
# Pydantic output model
# ---------------------------------------------------------------------------
class CouncilRecommendation(BaseModel):
    recommendation: str              # the single clearest recommended action
    reasoning: list[str]             # list of reasoning steps that led to it
    tradeoffs: list[str]             # tradeoffs to be aware of
    priority_actions: list[str]      # ordered list of the highest-priority next steps
    risk_level: str                  # "low" | "medium" | "high"
    confidence_score: float          # 0.0 (uncertain) to 1.0 (very confident)


# ---------------------------------------------------------------------------
# JSON schema shown to the LLM
# ---------------------------------------------------------------------------
_SCHEMA = {
    "recommendation": "str — the single clearest recommended course of action",
    "reasoning": "list[str] — step-by-step reasoning that led to the recommendation",
    "tradeoffs": "list[str] — tradeoffs or downsides to be aware of",
    "priority_actions": "list[str] — ordered list of highest-priority next steps for Patrick",
    "risk_level": "str — one of: low | medium | high",
    "confidence_score": "float — between 0.0 (very uncertain) and 1.0 (highly confident)",
}


# ---------------------------------------------------------------------------
# Agent entry point
# ---------------------------------------------------------------------------
def run(state: dict) -> dict:
    """
    Deliberate over all agent outputs and produce a final recommendation.

    Parameters
    ----------
    state : dict
        Must contain:
        - ``state["email_analysis"]``    — from email_agent
        - ``state["memory_context"]``    — from memory_agent
        - ``state["logistics_analysis"]``— from logistics_agent

    Returns
    -------
    dict
        The same state dict extended with ``state["council_recommendation"]``
        set to the serialised :class:`CouncilRecommendation` (via ``model_dump()``).
    """
    audit = AuditLog()
    email_analysis: dict = state.get("email_analysis", {})
    memory_context: dict = state.get("memory_context", {})
    logistics_analysis: dict = state.get("logistics_analysis", {})

    # ---- pre-execution audit log ------------------------------------------
    audit.log(
        agent_name=_AGENT_NAME,
        input_summary=(
            f"Deliberating: event={email_analysis.get('event_type', 'unknown')}, "
            f"risk={logistics_analysis.get('estimated_coordination_effort', 'unknown')}"
        ),
        output_summary="starting",
        status="running",
    )

    user_prompt = (
        f"You are the council agent. Deliberate over all specialist agent outputs "
        f"and produce a final, holistic recommendation.\n\n"
        f"Email Analysis:\n{json.dumps(email_analysis, indent=2)}\n\n"
        f"Memory Context:\n{json.dumps(memory_context, indent=2)}\n\n"
        f"Logistics Analysis:\n{json.dumps(logistics_analysis, indent=2)}\n\n"
        f"Return a CouncilRecommendation JSON object using this schema:\n"
        f"{json.dumps(_SCHEMA, indent=2)}"
    )

    try:
        response = _client.chat.completions.create(
            model=_MODEL,
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.2,
        )

        raw_content = response.choices[0].message.content.strip()

        # Strip accidental markdown fences
        if raw_content.startswith("```"):
            raw_content = raw_content.split("```")[1]
            if raw_content.startswith("json"):
                raw_content = raw_content[4:]
            raw_content = raw_content.strip()

        parsed = json.loads(raw_content)
        result = CouncilRecommendation(**parsed)

        # ---- post-execution audit log -------------------------------------
        audit.log(
            agent_name=_AGENT_NAME,
            input_summary=(
                f"event={email_analysis.get('event_type')}, "
                f"conflict={logistics_analysis.get('conflict_detected')}"
            ),
            output_summary=(
                f"risk={result.risk_level}, "
                f"confidence={result.confidence_score:.2f}, "
                f"actions={len(result.priority_actions)}"
            ),
            status="success",
        )

        state["council_recommendation"] = result.model_dump()

    except Exception as exc:  # noqa: BLE001
        audit.log(
            agent_name=_AGENT_NAME,
            input_summary=f"event={email_analysis.get('event_type')}",
            output_summary=f"ERROR: {exc}",
            status="error",
        )
        raise

    return state
