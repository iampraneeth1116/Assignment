"""
email_agent.py
--------------
Parses a raw caregiving email and extracts structured information from it.

Uses Groq (LLaMA 3.3-70B) to analyse the email and returns a validated
EmailAnalysis Pydantic model serialised into the shared state dict.
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
_AGENT_NAME = "email_agent"

# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------
_SYSTEM_PROMPT = (
    "You are an email parsing agent. Extract structured information from "
    "caregiving emails. Respond ONLY with valid JSON matching the schema "
    "provided. No markdown, no explanation."
)


# ---------------------------------------------------------------------------
# Pydantic output model
# ---------------------------------------------------------------------------
class EmailAnalysis(BaseModel):
    event_type: str                  # e.g. "appointment_reschedule"
    person: str                      # patient / person the email is about
    doctor: str                      # doctor's name
    old_time: str                    # original appointment time
    new_time: str                    # proposed new appointment time
    transportation_required: bool    # does transport need rebooking?
    urgency: str                     # "low" | "medium" | "high"
    summary: str                     # one-sentence plain-English summary


# ---------------------------------------------------------------------------
# JSON schema shown to the LLM so it knows exactly what to return
# ---------------------------------------------------------------------------
_SCHEMA = {
    "event_type": "str — type of event (e.g. appointment_reschedule, cancellation)",
    "person": "str — name of the patient / person the email concerns",
    "doctor": "str — name of the doctor / specialist",
    "old_time": "str — original appointment date/time",
    "new_time": "str — new proposed appointment date/time",
    "transportation_required": "bool — true if transport needs to be rearranged",
    "urgency": "str — one of: low | medium | high",
    "summary": "str — one-sentence plain-English summary of the email",
}


# ---------------------------------------------------------------------------
# Agent entry point
# ---------------------------------------------------------------------------
def run(state: dict) -> dict:
    """
    Parse the raw email stored in state and return structured EmailAnalysis.

    Parameters
    ----------
    state : dict
        Must contain ``state["raw_email"]`` — the raw text of the email.

    Returns
    -------
    dict
        The same state dict extended with ``state["email_analysis"]`` set to
        the serialised :class:`EmailAnalysis` (via ``model_dump()``).
    """
    audit = AuditLog()
    raw_email: str = state.get("raw_email", "")

    # ---- pre-execution audit log ------------------------------------------
    audit.log(
        agent_name=_AGENT_NAME,
        input_summary=f"Parsing email ({len(raw_email)} chars)",
        output_summary="starting",
        status="running",
    )

    user_prompt = (
        f"Parse the following caregiving email and return JSON matching the schema.\n\n"
        f"Schema:\n{json.dumps(_SCHEMA, indent=2)}\n\n"
        f"Email:\n{raw_email}"
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

        # Strip accidental markdown fences if the model adds them
        if raw_content.startswith("```"):
            raw_content = raw_content.split("```")[1]
            if raw_content.startswith("json"):
                raw_content = raw_content[4:]
            raw_content = raw_content.strip()

        parsed = json.loads(raw_content)
        result = EmailAnalysis(**parsed)

        # ---- post-execution audit log -------------------------------------
        audit.log(
            agent_name=_AGENT_NAME,
            input_summary=f"Email: {raw_email[:120]}...",
            output_summary=f"event_type={result.event_type}, urgency={result.urgency}",
            status="success",
        )

        state["email_analysis"] = result.model_dump()

    except Exception as exc:  # noqa: BLE001
        audit.log(
            agent_name=_AGENT_NAME,
            input_summary=f"Email: {raw_email[:120]}...",
            output_summary=f"ERROR: {exc}",
            status="error",
        )
        raise

    return state
