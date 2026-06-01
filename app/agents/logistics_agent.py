"""
logistics_agent.py
------------------
Agent responsible for scheduling, transport coordination, and appointment
logistics for Patrick's father. Uses Groq (LLaMA 3) to reason about the
schedule and writes appointments to the MemoryStore.
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
_AGENT_NAME = "logistics_agent"

_SYSTEM_PROMPT = """
You are a logistics and scheduling agent for a personal assistant called Maverick.
Your job is to help coordinate medical appointments, transport, and scheduling for
Patrick's father.

Key facts you should always consider:
- Patrick has client calls 9AM-12PM on Wednesdays; he is free after 1PM.
- The preferred transport provider is Medical Transport Service.
- Patrick's father sees Dr. Patel for neurological monitoring.

When asked to schedule an appointment, confirm:
1. The doctor's name
2. The proposed date and time
3. Transport needs
4. Any scheduling conflicts with Patrick's calendar

Respond concisely and confirm what has been arranged.
""".strip()


def run(query: str, context: dict[str, str] | None = None) -> dict:
    """
    Process a logistics or scheduling request.

    Parameters
    ----------
    query:   Natural-language request.
    context: Optional extra context to pass alongside stored facts.

    Returns
    -------
    A dict with keys ``response`` (str) and ``appointment`` (dict | None).
    """
    store = MemoryStore()
    audit = AuditLog()

    all_ctx = store.get_all_context()
    if context:
        all_ctx.update(context)

    context_block = json.dumps(all_ctx, indent=2)
    user_message = (
        f"Current patient context:\n{context_block}\n\n"
        f"Request: {query}\n\n"
        "If this request results in booking an appointment, include a JSON block at the end "
        "of your response in this exact format (do not include it otherwise):\n"
        "```json\n"
        '{{"doctor": "...", "date": "...", "notes": "..."}}\n'
        "```"
    )

    try:
        response = _client.chat.completions.create(
            model=_MODEL,
            max_tokens=768,
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user",   "content": user_message},
            ],
        )
        answer = response.choices[0].message.content.strip()

        # Extract structured appointment block if present
        appointment: dict | None = None
        if "```json" in answer:
            try:
                json_str = answer.split("```json")[1].split("```")[0].strip()
                appointment = json.loads(json_str)
                store.add_appointment(
                    doctor=appointment.get("doctor", "Unknown"),
                    date=appointment.get("date", ""),
                    notes=appointment.get("notes", ""),
                )
                store.set_context("last_appointment", appointment.get("date", ""))
            except (json.JSONDecodeError, IndexError):
                pass

        audit.log(_AGENT_NAME, query, answer, status="success")
        return {"response": answer, "appointment": appointment}

    except Exception as exc:  # noqa: BLE001
        err = f"LogisticsAgent error: {exc}"
        audit.log(_AGENT_NAME, query, err, status="error")
        return {"response": err, "appointment": None}
