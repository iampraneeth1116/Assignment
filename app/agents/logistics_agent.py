"""
logistics_agent.py
------------------
Analyses scheduling conflicts and logistics needs that arise from an
appointment change, using Groq (LLaMA 3.3-70B) as the reasoning engine.

Input  : state["email_analysis"]  + state["memory_context"]
Output : state["logistics_analysis"] (LogisticsAnalysis Pydantic model)
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
_MODEL = "llama-3.1-8b-instant"
_AGENT_NAME = "logistics_agent"

# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------
_SYSTEM_PROMPT = (
    "You are a family logistics coordination agent. Analyse appointment "
    "changes and their impact on family scheduling. Be practical and thorough. "
    "Respond ONLY with valid JSON."
)


# ---------------------------------------------------------------------------
# Pydantic output model
# ---------------------------------------------------------------------------
class LogisticsAnalysis(BaseModel):
    conflict_detected: bool                    # does the new time clash with anything?
    conflict_details: str                      # plain-English description of the conflict
    transportation_needs_rebooking: bool       # does transport need to be rearranged?
    transportation_action: str                 # what action to take for transport
    family_notification_required: bool         # should family members be notified?
    family_members_to_notify: list[str]        # which family members
    estimated_coordination_effort: str         # "low" | "medium" | "high"
    action_items: list[str]                    # ordered list of concrete next steps


# ---------------------------------------------------------------------------
# JSON schema shown to the LLM
# ---------------------------------------------------------------------------
_SCHEMA = {
    "conflict_detected": "bool — true if the new appointment time conflicts with existing schedule",
    "conflict_details": "str — plain-English description of the conflict (or 'none' if no conflict)",
    "transportation_needs_rebooking": "bool — true if transport must be rearranged",
    "transportation_action": "str — what to do about transport (e.g. 'rebook Medical Transport Service')",
    "family_notification_required": "bool — true if family members need to be informed",
    "family_members_to_notify": "list[str] — names of family members to notify",
    "estimated_coordination_effort": "str — one of: low | medium | high",
    "action_items": "list[str] — ordered list of concrete next steps for Patrick",
}


# ---------------------------------------------------------------------------
# Agent entry point
# ---------------------------------------------------------------------------
def run(state: dict) -> dict:
    """
    Analyse scheduling conflicts and logistics from email + memory context.

    Parameters
    ----------
    state : dict
        Must contain ``state["email_analysis"]`` and ``state["memory_context"]``.

    Returns
    -------
    dict
        The same state dict extended with ``state["logistics_analysis"]`` set
        to the serialised :class:`LogisticsAnalysis` (via ``model_dump()``).
    """
    audit = AuditLog()
    email_analysis: dict = state.get("email_analysis", {})
    memory_context: dict = state.get("memory_context", {})

    # ---- pre-execution audit log ------------------------------------------
    audit.log(
        agent_name=_AGENT_NAME,
        input_summary=(
            f"event={email_analysis.get('event_type', 'unknown')}, "
            f"urgency={email_analysis.get('urgency', 'unknown')}"
        ),
        output_summary="starting",
        status="running",
    )

    user_prompt = (
        f"Analyse the following appointment change and its logistics impact.\n\n"
        f"Email Analysis:\n{json.dumps(email_analysis, indent=2)}\n\n"
        f"Memory Context:\n{json.dumps(memory_context, indent=2)}\n\n"
        f"Return a LogisticsAnalysis JSON object using this schema:\n"
        f"{json.dumps(_SCHEMA, indent=2)}"
    )

    try:
        response = _client.chat.completions.create(
            model=_MODEL,
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.1,
        )

        raw_content = response.choices[0].message.content.strip()

        # Strip accidental markdown fences
        if raw_content.startswith("```"):
            raw_content = raw_content.split("```")[1]
            if raw_content.startswith("json"):
                raw_content = raw_content[4:]
            raw_content = raw_content.strip()

        parsed = json.loads(raw_content)
        result = LogisticsAnalysis(**parsed)

        # ---- post-execution audit log -------------------------------------
        audit.log(
            agent_name=_AGENT_NAME,
            input_summary=f"event={email_analysis.get('event_type')}, new_time={email_analysis.get('new_time')}",
            output_summary=(
                f"conflict={result.conflict_detected}, "
                f"effort={result.estimated_coordination_effort}, "
                f"action_items={len(result.action_items)}"
            ),
            status="success",
        )

        state["logistics_analysis"] = result.model_dump()

    except Exception as exc:  # noqa: BLE001
        audit.log(
            agent_name=_AGENT_NAME,
            input_summary=f"event={email_analysis.get('event_type')}",
            output_summary=f"ERROR: {exc}",
            status="error",
        )
        raise

    return state
