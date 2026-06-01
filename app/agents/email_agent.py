"""
email_agent.py
--------------
Agent responsible for drafting emails on Patrick's behalf.

NOTE: This agent uses MOCK DATA — no live API call is made.
Pre-defined email templates are matched by keyword and filled in
with values from the patient context store.
"""

from __future__ import annotations

from app.memory.memory_store import MemoryStore
from app.audit.audit_log import AuditLog

_AGENT_NAME = "email_agent"

# ---------------------------------------------------------------------------
# Mock email templates
# Keys are match keywords (checked against the lowercase purpose string).
# Templates support {placeholders} filled from patient context.
# ---------------------------------------------------------------------------
_TEMPLATES: list[dict] = [
    # More-specific intents first — checked before the generic confirm/schedule template
    {
        "keywords": ["reschedule", "change", "postpone", "move"],
        "subject": "Request to Reschedule Appointment – {father_doctor}",
        "body": (
            "Dear {father_doctor}'s Office,\n\n"
            "I am writing to request a reschedule for my father's upcoming appointment "
            "(currently on {last_appointment}).\n\n"
            "We are available most afternoons and can work around your availability. "
            "Please reply with two or three alternative slots at your earliest convenience.\n\n"
            "Thank you for your understanding.\n\n"
            "Best regards,\nPatrick\n(on behalf of my father)"
        ),
    },
    {
        "keywords": ["cancel"],
        "subject": "Appointment Cancellation – {father_doctor}",
        "body": (
            "Dear {father_doctor}'s Office,\n\n"
            "Unfortunately I need to cancel my father's appointment scheduled for {last_appointment}.\n\n"
            "I will contact your office shortly to arrange a new date. "
            "Apologies for any inconvenience caused.\n\n"
            "Best regards,\nPatrick\n(on behalf of my father)"
        ),
    },
    {
        "keywords": ["transport", "pickup", "pick up", "ride"],
        "subject": "Transport Booking Request – {last_appointment}",
        "body": (
            "Dear {preferred_transport},\n\n"
            "I would like to arrange a pickup for my father for a medical appointment "
            "on {last_appointment}.\n\n"
            "Please confirm availability and the estimated time of arrival. "
            "He requires assistance boarding the vehicle.\n\n"
            "Thank you,\nPatrick"
        ),
    },
    {
        "keywords": ["update", "condition", "progress", "report"],
        "subject": "Update on Father's Condition – {father_condition}",
        "body": (
            "Dear {father_doctor},\n\n"
            "I wanted to share a brief update on my father's condition since his last visit "
            "on {last_appointment}.\n\n"
            "He has been managing his {father_condition} and we have some new observations "
            "we would like to discuss at the next appointment. Please let us know if an earlier "
            "consultation is possible.\n\n"
            "Thank you for your time and care.\n\n"
            "Best regards,\nPatrick\n(on behalf of my father)"
        ),
    },
    # Generic appointment confirmation — checked last
    {
        "keywords": ["confirm", "appointment", "schedule"],
        "subject": "Appointment Confirmation – {father_doctor}",
        "body": (
            "Dear {father_doctor}'s Office,\n\n"
            "I am writing to confirm the upcoming appointment for my father on {last_appointment}.\n\n"
            "He will be arriving via {preferred_transport}. Please let us know if there is anything "
            "you need us to bring or prepare in advance.\n\n"
            "Thank you for your continued care.\n\n"
            "Best regards,\nPatrick\n(on behalf of my father)"
        ),
    },
]

_DEFAULT_TEMPLATE = {
    "subject": "General Inquiry – {father_doctor}",
    "body": (
        "Dear {father_doctor}'s Office,\n\n"
        "I am reaching out regarding my father's ongoing care ({father_condition}).\n\n"
        "Could you please get in touch at your earliest convenience to discuss the next steps?\n\n"
        "Thank you,\nPatrick"
    ),
}


def _match_template(purpose: str) -> dict:
    """Return the best-matching template for *purpose*, or the default."""
    p = purpose.lower()
    for tmpl in _TEMPLATES:
        if any(kw in p for kw in tmpl["keywords"]):
            return tmpl
    return _DEFAULT_TEMPLATE


def _fill(template: str, ctx: dict[str, str]) -> str:
    """Fill {placeholders} in *template* using *ctx*, leaving unknowns intact."""
    try:
        return template.format_map(ctx)
    except KeyError:
        return template


def draft_email(purpose: str, context: dict[str, str] | None = None) -> str:
    """
    Return a mock-drafted email for *purpose*.

    Parameters
    ----------
    purpose: Natural-language description of what the email should say.
    context: Optional extra context merged with the stored patient context.

    Returns
    -------
    A plain-text email string: "Subject: ...\n\n<body>"
    """
    store = MemoryStore()
    audit = AuditLog()

    ctx = store.get_all_context()
    if context:
        ctx.update(context)

    tmpl = _match_template(purpose)
    subject = _fill(tmpl["subject"], ctx)
    body = _fill(tmpl["body"], ctx)
    draft = f"Subject: {subject}\n\n{body}"

    audit.log(_AGENT_NAME, purpose, f"Subject: {subject}", status="success")
    return draft


def run(purpose: str, context: dict[str, str] | None = None) -> str:
    """Alias so the workflow can call every agent uniformly via ``run()``."""
    return draft_email(purpose, context)
