"""
memory_agent.py
---------------
Agent responsible for reading from and writing to the patient context store.
Uses Groq (LLaMA 3) to interpret free-text requests and map them to
MemoryStore operations, then audits every call via AuditLog.
"""

from __future__ import annotations

import json
import os

from groq import Groq
from dotenv import load_dotenv

from app.memory.memory_store import MemoryStore
from app.audit.audit_log import AuditLog

load_dotenv()

_client = Groq(api_key=os.getenv("GROQ_API_KEY", ""))
_MODEL = "llama-3.3-70b-versatile"
_AGENT_NAME = "memory_agent"

_SYSTEM_PROMPT = """
You are a memory agent for a personal assistant called Maverick.
Your job is to help retrieve and update information about the patient (Patrick)
and his family from a structured context store.

When asked to look up information, respond with the relevant facts in a concise,
conversational way. When asked to update information, confirm what was saved.

You have access to the following context keys:
- preferred_transport
- father_doctor
- father_condition
- last_appointment
- family_members
- wednesday_schedule

Always be factual and only use information explicitly provided to you.
""".strip()


def run(query: str, context: dict[str, str] | None = None) -> str:
    """
    Process a natural-language memory query.

    Parameters
    ----------
    query:   The user's question or instruction.
    context: Optional extra context to inject alongside the stored facts.

    Returns
    -------
    A plain-text response from the model.
    """
    store = MemoryStore()
    audit = AuditLog()

    all_ctx = store.get_all_context()
    if context:
        all_ctx.update(context)

    context_block = json.dumps(all_ctx, indent=2)
    user_message = (
        f"Current patient context:\n{context_block}\n\n"
        f"User request: {query}"
    )

    try:
        response = _client.chat.completions.create(
            model=_MODEL,
            max_tokens=512,
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user",   "content": user_message},
            ],
        )
        answer = response.choices[0].message.content.strip()
        audit.log(_AGENT_NAME, query, answer, status="success")
        return answer
    except Exception as exc:  # noqa: BLE001
        err = f"MemoryAgent error: {exc}"
        audit.log(_AGENT_NAME, query, err, status="error")
        return err
