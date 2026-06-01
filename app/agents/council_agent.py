"""
council_agent.py
----------------
The orchestrator / "council" agent. It receives a high-level user request,
decides which specialist agents to invoke (memory, logistics, email), collects
their outputs, and synthesises a final unified response for Patrick.

Uses Groq (LLaMA 3) for both routing decisions and final synthesis.
Email agent uses mock data — no API call is made for email drafting.
"""

from __future__ import annotations

import json
import os

from groq import Groq
from dotenv import load_dotenv

from app.memory.memory_store import MemoryStore
from app.audit.audit_log import AuditLog
from app.agents import memory_agent, logistics_agent, email_agent

load_dotenv()

_client = Groq(api_key=os.getenv("GROQ_API_KEY", ""))
_MODEL = "llama-3.3-70b-versatile"
_AGENT_NAME = "council_agent"

_SYSTEM_PROMPT = """
You are the council agent — the top-level orchestrator for Maverick, a personal
assistant for Patrick who manages care coordination for his elderly father.

Your role:
1. Understand Patrick's high-level request.
2. Decide which sub-agents are needed (memory, logistics, email — or a combination).
3. Receive their outputs and compose a clear, helpful, final response for Patrick.

Sub-agents available:
- memory_agent    – reads/writes patient context (preferences, doctor, condition, schedule)
- logistics_agent – handles appointment scheduling and transport coordination
- email_agent     – drafts professional emails (uses pre-built templates, no API call)

Always be warm, organised, and proactive. If you spot scheduling conflicts or
missing information, flag them clearly.
""".strip()

# ---------------------------------------------------------------------------
# Routing: simple keyword heuristics
# ---------------------------------------------------------------------------

def _needs_memory(query: str) -> bool:
    keywords = ["remember", "context", "know", "what is", "who is",
                "preference", "transport", "condition", "doctor", "family",
                "schedule", "wednesday", "appointment"]
    q = query.lower()
    return any(k in q for k in keywords)


def _needs_logistics(query: str) -> bool:
    keywords = ["schedul", "book", "appointment", "arrange", "transport",
                "pick up", "pickup", "next", "date", "time", "when"]
    q = query.lower()
    return any(k in q for k in keywords)


def _needs_email(query: str) -> bool:
    keywords = ["email", "write", "draft", "send", "message", "notify",
                "contact", "confirm"]
    q = query.lower()
    return any(k in q for k in keywords)


def run(query: str) -> dict:
    """
    Entry point for the council agent.

    Parameters
    ----------
    query: Patrick's natural-language request.

    Returns
    -------
    A dict with:
      - ``response``    (str)        – final synthesised answer
      - ``agents_used`` (list[str])  – which sub-agents were invoked
      - ``details``     (dict)       – raw outputs from each sub-agent
    """
    store = MemoryStore()
    audit = AuditLog()
    context = store.get_all_context()

    agents_used: list[str] = []
    details: dict[str, object] = {}

    # ── Route to sub-agents ──────────────────────────────────────────────────
    if _needs_memory(query):
        agents_used.append("memory_agent")
        details["memory"] = memory_agent.run(query, context)

    if _needs_logistics(query):
        agents_used.append("logistics_agent")
        result = logistics_agent.run(query, context)
        details["logistics"] = result
        context = store.get_all_context()  # refresh after potential writes

    if _needs_email(query):
        agents_used.append("email_agent")
        # email_agent is fully mock — no Groq call made here
        details["email"] = email_agent.run(query, context)

    # Default fallback
    if not agents_used:
        agents_used.append("memory_agent")
        details["memory"] = memory_agent.run(query, context)

    # ── Synthesise final response via Groq ───────────────────────────────────
    sub_outputs = json.dumps(details, indent=2, default=str)
    synthesis_prompt = (
        f"Patrick asked: {query}\n\n"
        f"Sub-agent outputs:\n{sub_outputs}\n\n"
        "Please compose a single, friendly, well-structured response for Patrick "
        "that combines the above information. Do not repeat raw JSON."
    )

    try:
        response = _client.chat.completions.create(
            model=_MODEL,
            max_tokens=768,
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user",   "content": synthesis_prompt},
            ],
        )
        final_answer = response.choices[0].message.content.strip()
    except Exception as exc:  # noqa: BLE001
        final_answer = f"Council synthesis error: {exc}"

    audit.log(
        _AGENT_NAME,
        query,
        final_answer[:300],
        status="success" if "error" not in final_answer.lower() else "error",
    )

    return {
        "response": final_answer,
        "agents_used": agents_used,
        "details": details,
    }
