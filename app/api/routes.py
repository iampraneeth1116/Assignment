"""
routes.py
---------
FastAPI router for all Maverick endpoints.

Phase 4 endpoints
-----------------
POST /process-email          Run the full MaverickWorkflow pipeline.
POST /approve                Resume a pipeline paused at awaiting_approval.
GET  /audit-logs             Retrieve all audit log entries.
GET  /audit-logs/{agent}     Retrieve audit logs for a specific agent.
GET  /memory                 Retrieve all stored patient context.
GET  /health                 Simple liveness probe.

Legacy endpoints (kept for backwards compatibility)
----------------------------------------------------
POST /query                  Original query endpoint (calls run_workflow helper).
GET  /context                Read all context.
POST /context                Set a single context key/value.
GET  /appointments/{doctor}  Get appointment history.
POST /appointments           Manually log an appointment.
GET  /audit/logs             Legacy audit log fetch.
GET  /audit/logs/{agent}     Legacy filtered audit log fetch.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.graph.workflow import MaverickWorkflow, run_workflow
from app.memory.memory_store import MemoryStore
from app.audit.audit_log import AuditLog

router = APIRouter()


# ---------------------------------------------------------------------------
# Request / Response models — Phase 4
# ---------------------------------------------------------------------------

class ProcessEmailRequest(BaseModel):
    """Input body for POST /process-email."""
    email: str
    require_approval: bool = False


class ProcessEmailResponse(BaseModel):
    """Structured response returned by POST /process-email and POST /approve."""
    email_analysis: dict = {}
    memory_context: dict = {}
    logistics_analysis: dict = {}
    council_recommendation: dict = {}
    status: str
    stages_completed: list[str] = []


class ApproveRequest(BaseModel):
    """
    Input body for POST /approve.
    Pass the full state dict returned from a previous awaiting_approval response.
    """
    raw_email: str
    status: str
    stages_completed: list[str] = []
    email_analysis: dict = {}
    memory_context: dict = {}
    logistics_analysis: dict = {}
    council_recommendation: dict = {}


class AuditLogsResponse(BaseModel):
    """Wraps audit log entries."""
    logs: list[dict]


# Legacy models
class QueryRequest(BaseModel):
    query: str


class QueryResponse(BaseModel):
    response: str
    agents_used: list[str]
    details: dict


class ContextUpdateRequest(BaseModel):
    key: str
    value: str


class AppointmentRequest(BaseModel):
    doctor: str
    date: str
    notes: str


# ---------------------------------------------------------------------------
# Phase 4 Routes
# ---------------------------------------------------------------------------

@router.post(
    "/process-email",
    response_model=ProcessEmailResponse,
    summary="Run the Maverick agent pipeline on a caregiving email",
)
async def process_email(body: ProcessEmailRequest) -> ProcessEmailResponse:
    """
    Runs ``MaverickWorkflow.run()`` on the submitted email text.

    * If ``require_approval`` is ``False`` (default), all four agents
      execute in sequence and the full council recommendation is returned.
    * If ``require_approval`` is ``True``, the pipeline pauses after the
      logistics stage and returns ``status="awaiting_approval"``. Call
      ``POST /approve`` with the returned state to resume.
    """
    if not body.email.strip():
        raise HTTPException(status_code=400, detail="Email body must not be empty.")

    workflow = MaverickWorkflow()
    state = workflow.run(raw_email=body.email, require_approval=body.require_approval)

    return ProcessEmailResponse(
        email_analysis=state.get("email_analysis") or {},
        memory_context=state.get("memory_context") or {},
        logistics_analysis=state.get("logistics_analysis") or {},
        council_recommendation=state.get("council_recommendation") or {},
        status=state.get("status", "unknown"),
        stages_completed=state.get("stages_completed") or [],
    )


@router.post(
    "/approve",
    response_model=ProcessEmailResponse,
    summary="Resume a pipeline paused at awaiting_approval",
)
async def approve(body: ApproveRequest) -> ProcessEmailResponse:
    """
    Resumes the Maverick pipeline from the council deliberation step.

    The client should pass the **full state dict** returned by a previous
    ``POST /process-email`` call that has ``status="awaiting_approval"``.
    """
    state = body.model_dump()

    if state.get("status") != "awaiting_approval":
        raise HTTPException(
            status_code=400,
            detail=f"State must have status='awaiting_approval', got '{state.get('status')}'.",
        )

    workflow = MaverickWorkflow()
    completed_state = workflow.approve_and_continue(state)

    return ProcessEmailResponse(
        email_analysis=completed_state.get("email_analysis") or {},
        memory_context=completed_state.get("memory_context") or {},
        logistics_analysis=completed_state.get("logistics_analysis") or {},
        council_recommendation=completed_state.get("council_recommendation") or {},
        status=completed_state.get("status", "unknown"),
        stages_completed=completed_state.get("stages_completed") or [],
    )


@router.get(
    "/audit-logs",
    response_model=AuditLogsResponse,
    summary="Get all audit log entries",
)
async def get_all_audit_logs() -> AuditLogsResponse:
    """Return every audit log entry, newest first."""
    return AuditLogsResponse(logs=AuditLog().get_logs())


@router.get(
    "/audit-logs/{agent_name}",
    response_model=AuditLogsResponse,
    summary="Get audit logs for a specific agent",
)
async def get_agent_audit_logs(agent_name: str) -> AuditLogsResponse:
    """Return audit log entries filtered by agent name (e.g. ``email_agent``)."""
    return AuditLogsResponse(logs=AuditLog().get_logs_for_agent(agent_name))


@router.get(
    "/memory",
    summary="Return all stored patient context",
)
async def get_memory() -> dict[str, str]:
    """Return the full patient context dictionary from MemoryStore."""
    return MemoryStore().get_all_context()


@router.get(
    "/health",
    summary="Health check",
)
async def health() -> dict[str, str]:
    """Liveness probe — returns 200 OK when the service is running."""
    return {"status": "ok", "service": "Maverick AI"}


# ---------------------------------------------------------------------------
# Legacy Routes (kept for backwards compatibility)
# ---------------------------------------------------------------------------

@router.post("/query", response_model=QueryResponse, summary="[Legacy] Send a request to Maverick")
async def handle_query(body: QueryRequest) -> QueryResponse:
    """
    Original query endpoint that wraps the full agent pipeline.
    Prefer ``POST /process-email`` for new integrations.
    """
    if not body.query.strip():
        raise HTTPException(status_code=400, detail="Query must not be empty.")
    result = run_workflow(body.query)
    return QueryResponse(**result)


@router.get("/context", summary="[Legacy] Retrieve all stored patient context")
async def get_context() -> dict[str, str]:
    """Return the full patient context dictionary. Prefer GET /memory."""
    return MemoryStore().get_all_context()


@router.post("/context", summary="[Legacy] Set or update a context value")
async def set_context(body: ContextUpdateRequest) -> dict[str, str]:
    """Insert or update a single context key/value pair."""
    store = MemoryStore()
    store.set_context(body.key, body.value)
    return {"key": body.key, "value": body.value}


@router.get("/appointments/{doctor}", summary="[Legacy] Get appointment history for a doctor")
async def get_appointments(doctor: str) -> list[dict]:
    """Return all appointments for the given doctor, newest first."""
    return MemoryStore().get_appointments(doctor)


@router.post("/appointments", summary="[Legacy] Manually log an appointment")
async def add_appointment(body: AppointmentRequest) -> dict:
    """Directly add an appointment record without going through the workflow."""
    MemoryStore().add_appointment(body.doctor, body.date, body.notes)
    return {"status": "created", "doctor": body.doctor, "date": body.date}


@router.get("/audit/logs", summary="[Legacy] Get all audit log entries")
async def get_audit_logs() -> list[dict]:
    """Return every audit log entry, newest first. Prefer GET /audit-logs."""
    return AuditLog().get_logs()


@router.get("/audit/logs/{agent_name}", summary="[Legacy] Get audit logs for a specific agent")
async def get_audit_logs_for_agent(agent_name: str) -> list[dict]:
    """Return audit log entries filtered by agent name. Prefer GET /audit-logs/{agent_name}."""
    return AuditLog().get_logs_for_agent(agent_name)
