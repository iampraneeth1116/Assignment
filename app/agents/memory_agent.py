"""
memory_agent.py
---------------
Retrieves all stored context from MemoryStore and synthesises a structured
MemoryContext via Groq (LLaMA 3.3-70B), taking the current email event into
account.
"""

from __future__ import annotations

import json
import os

from groq import Groq
from dotenv import load_dotenv
from pydantic import BaseModel, field_validator

from app.memory.memory_store import MemoryStore
from app.audit.audit_log import AuditLog

load_dotenv()

_client = Groq(api_key=os.getenv("GROQ_API_KEY", ""))
_MODEL = "llama-3.1-8b-instant"
_AGENT_NAME = "memory_agent"

# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------
_SYSTEM_PROMPT = (
    "You are a memory retrieval agent. Given stored patient context and an "
    "email event, synthesize the most relevant memory context. "
    "Respond ONLY with valid JSON."
)


# ---------------------------------------------------------------------------
# Pydantic output model
# ---------------------------------------------------------------------------
class MemoryContext(BaseModel):
    doctor_known: bool               # is the doctor already recorded in context?
    preferred_transport: str         # stored transport preference
    last_appointment: str            # date of the last recorded appointment
    family_members: list[str]        # names of known family members
    wednesday_availability: str      # Patrick's Wednesday schedule
    relevant_notes: str              # any other notes relevant to the email event

    @field_validator("family_members", mode="before")
    @classmethod
    def coerce_family_members_to_list(cls, v):
        """Accept a comma-separated string OR a proper list from the LLM."""
        if isinstance(v, str):
            return [name.strip() for name in v.split(",") if name.strip()]
        return v


# ---------------------------------------------------------------------------
# JSON schema shown to the LLM
# ---------------------------------------------------------------------------
_SCHEMA = {
    "doctor_known": "bool — true if the doctor in the email matches stored context",
    "preferred_transport": "str — stored preferred transport method",
    "last_appointment": "str — date of the last recorded appointment",
    "family_members": "list[str] — list of known family member names",
    "wednesday_availability": "str — description of Patrick's Wednesday schedule",
    "relevant_notes": "str — any other stored notes relevant to this email event",
}


# ---------------------------------------------------------------------------
# Agent entry point
# ---------------------------------------------------------------------------
def run(state: dict) -> dict:
    """
    Retrieve all stored context and synthesise a MemoryContext from it.

    Parameters
    ----------
    state : dict
        Must contain ``state["email_analysis"]`` — the output of email_agent.

    Returns
    -------
    dict
        The same state dict extended with ``state["memory_context"]`` set to
        the serialised :class:`MemoryContext` (via ``model_dump()``).
    """
    audit = AuditLog()
    store = MemoryStore()
    email_analysis: dict = state.get("email_analysis", {})

    # ---- pre-execution audit log ------------------------------------------
    audit.log(
        agent_name=_AGENT_NAME,
        input_summary=f"Retrieving context for event: {email_analysis.get('event_type', 'unknown')}",
        output_summary="starting",
        status="running",
    )

    # Pull everything from SQLite
    raw_context: dict[str, str] = store.get_all_context()

    user_prompt = (
        f"Here is all the stored patient context (key-value pairs):\n"
        f"{json.dumps(raw_context, indent=2)}\n\n"
        f"Here is the current email event:\n"
        f"{json.dumps(email_analysis, indent=2)}\n\n"
        f"Synthesize a MemoryContext JSON object using this schema:\n"
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
        result = MemoryContext(**parsed)

        # ---- post-execution audit log -------------------------------------
        audit.log(
            agent_name=_AGENT_NAME,
            input_summary=f"Context keys: {list(raw_context.keys())}",
            output_summary=(
                f"doctor_known={result.doctor_known}, "
                f"transport={result.preferred_transport}"
            ),
            status="success",
        )

        state["memory_context"] = result.model_dump()

    except Exception as exc:  # noqa: BLE001
        audit.log(
            agent_name=_AGENT_NAME,
            input_summary=f"Context keys: {list(raw_context.keys())}",
            output_summary=f"ERROR: {exc}",
            status="error",
        )
        raise

    return state
